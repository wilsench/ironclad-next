#!/usr/bin/env python3
"""Regression tests for the two ways Ironclad used to pass when it should have failed.

Both were found by auditing 0.10.2, and both share a shape worth naming: the tool
reported success while doing something other than what it was asked.

  BUG-A  `curl | bash` installed a payload missing scripts/update_check.py and
         assets/presets/coherence.yml, because install.sh kept a hand-written list
         of files next to a payload directory that already knew the answer.

  BUG-B  `ironclad check --preset strict` ran as balanced. The wrapper appended the
         repo preset *after* the user's arguments, and argparse keeps the last value.

  BUG-C  A repo whose .agent/standards.yml named `coherence` could not be checked at
         all through the wrapper: the wrapper passed --preset coherence, which made
         the checker skip its own repo-config lookup and reject the name.

Run:  python3 tests/test_regressions.py        (exit 0 = all passed)
No third-party dependencies, same as the tool itself.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "ironclad"
CHECKER = SKILL / "scripts" / "check_schema.py"
INSTALL = ROOT / "install.sh"

passed = 0
failed = 0


def ok(name: str) -> None:
    global passed
    passed += 1
    print(f"  PASS  {name}")


def bad(name: str, detail: str = "") -> None:
    global failed
    failed += 1
    print(f"  FAIL  {name}")
    if detail:
        for line in str(detail).strip().splitlines()[:12]:
            print(f"        {line}")


def run(args, cwd=None, env=None, timeout=120):
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=timeout)


def check(paths, preset=None, cwd=None, env=None):
    cmd = [sys.executable, str(CHECKER), *paths]
    if preset:
        cmd += ["--preset", preset]
    return run(cmd, cwd=cwd, env=env)


# --------------------------------------------------------------------------- BUG-B / C
BAD_SQL = """\
CREATE TABLE users (
  id INT PRIMARY KEY,
  status ENUM('active','banned')
);
"""

GOOD_SQL = """\
CREATE TABLE users (
  id INT PRIMARY KEY,
  status INT NOT NULL,
  FOREIGN KEY (status) REFERENCES statuses(id)
);
"""


def test_preset_flag_wins_over_repo():
    """An explicit --preset must change the verdict, not be swallowed."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "bad.sql").write_text(BAD_SQL)
        (d / ".agent").mkdir()
        (d / ".agent" / "standards.yml").write_text("name: legacy-friendly\n")

        # legacy-friendly says nothing blocks: that is the repo's committed choice.
        r = check(["."], cwd=d)
        if r.returncode != 0:
            bad("repo preset alone is honoured", f"exit {r.returncode}: {r.stderr}")
        else:
            ok("repo preset alone is honoured")

        # Asking for strict must be stricter than the repo, not ignored.
        r = check(["."], preset="strict", cwd=d)
        if r.returncode != 1:
            bad("--preset strict outranks the repo preset",
                f"expected exit 1, got {r.returncode}. This is BUG-B returning.")
        else:
            ok("--preset strict outranks the repo preset")

        # And a caller may also relax a strict repo deliberately.
        (d / ".agent" / "standards.yml").write_text("name: strict\n")
        r = check(["."], preset="legacy-friendly", cwd=d)
        if r.returncode != 0:
            bad("--preset legacy-friendly outranks a strict repo",
                f"expected exit 0, got {r.returncode}")
        else:
            ok("--preset legacy-friendly outranks a strict repo")


def test_repo_preset_layers_with_flag():
    """The repo's exceptions and allowlists must survive an explicit --preset."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "skip.sql").write_text(BAD_SQL)
        (d / "keep.sql").write_text("CREATE TABLE t (id INT, status TEXT);\n")
        (d / ".agent").mkdir()
        (d / ".agent" / "standards.yml").write_text(
            "name: balanced\nexceptions:\n  - skip.sql\n")
        r = check(["."], preset="strict", cwd=d)

        flagged = [ln for ln in r.stdout.splitlines() if "skip.sql:" in ln]
        checked = [ln for ln in r.stdout.splitlines() if "keep.sql:" in ln]
        if flagged:
            bad("repo exceptions survive an explicit --preset",
                f"skip.sql was excepted but still reported:\n{flagged[:3]}")
        elif not checked:
            bad("repo exceptions survive an explicit --preset",
                f"keep.sql should still be checked under strict:\n{r.stdout}{r.stderr}")
        else:
            ok("repo exceptions survive an explicit --preset")

        # The parser must keep the whole list, not just its first entry.
        (d / ".agent" / "standards.yml").write_text(
            "name: balanced\nexceptions:\n  - skip.sql\n  - keep.sql\n")
        r = check([".", ], cwd=d)
        # Both entries honoured means neither file is looked at, so the run must
        # refuse to look clean. This was briefly relaxed while `.agent/standards.yml`
        # was itself being scanned as application source; the fix belonged in the
        # security domain, not in this assertion.
        leaked = [ln for ln in r.stdout.splitlines()
                  if re.search(r"\b(skip|keep)\.sql:", ln)]
        if leaked:
            bad("multi-entry exceptions are all honoured",
                f"excepted files were still reported:\n{leaked[:3]}")
        elif r.returncode != 2:
            bad("multi-entry exceptions are all honoured",
                f"expected exit 2 with nothing left to check, got {r.returncode}:\n"
                f"{r.stdout}{r.stderr}")
        else:
            ok("multi-entry exceptions are all honoured")


def test_coherence_repo_is_checkable():
    """A repo that committed `coherence` must not become uncheckable (BUG-C)."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "a.sql").write_text("CREATE TABLE a (id INT, status ENUM('open'));\n")
        (d / "b.sql").write_text(
            "CREATE TABLE b (id INT, status INT, FOREIGN KEY (status) REFERENCES s(id));\n")
        (d / ".agent").mkdir()
        (d / ".agent" / "standards.yml").write_text(
            "name: coherence\nrules:\n  DB-01: off\n  DB-08: error\n")

        r = check(["."], cwd=d)
        if r.returncode == 1 and "DB-08" in r.stdout:
            ok("coherence repo: DB-08 fires, exit 1")
        else:
            bad("coherence repo: DB-08 fires, exit 1", f"exit {r.returncode}\n{r.stdout}{r.stderr}")

        # And --preset strict on top must not crash on its own name.
        r = check(["."], preset="strict", cwd=d)
        if "unknown preset" in r.stderr:
            bad("coherence repo + --preset strict does not crash",
                "the checker rejected its own preset name")
        else:
            ok("coherence repo + --preset strict does not crash")


# --------------------------------------------------------------------------- BUG-A
def _installer_function(name: str) -> str:
    """Pull one shell function out of install.sh so it can be tested directly."""
    src = INSTALL.read_text()
    marker = f"{name}() {{"
    start = src.index(marker)
    depth, i = 0, src.index("{", start)
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise ValueError(f"unbalanced braces in {name}")


def test_manifest_matches_payload():
    """The installer's fetch list must cover every file the skill ships."""
    payload = SKILL
    on_disk = {
        str(p.relative_to(payload))
        for p in payload.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }
    # Ask the installer itself what it would fetch, from a checkout.
    script = (
        "SKILL_NAME=ironclad\n"
        f"SELF_PAYLOAD={shlex.quote(str(payload))}\n"
        f"MIRROR={shlex.quote(str(INSTALL.parent / 'nonexistent-mirror'))}\n"
        f"{_installer_function('_manifest')}\n"
        "_manifest\n"
    )
    r = run(["bash", "-c", script])
    listed = set(r.stdout.split())
    missing = on_disk - listed
    extra = listed - on_disk
    if missing or extra:
        bad("installer manifest == payload on disk",
            f"missing from manifest: {sorted(missing)}\n"
            f"listed but absent: {sorted(extra)}\n{r.stderr}")
    else:
        ok(f"installer manifest == payload on disk ({len(listed)} files)")

    for required in ("scripts/update_check.py", "assets/presets/coherence.yml"):
        if required in on_disk and required not in listed:
            bad(f"manifest carries {required}", "this is BUG-A returning")
        else:
            ok(f"manifest carries {required}")


def test_curl_only_install_gets_full_payload():
    """Install from a lone script + a payload index, the way curl|bash does."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        mirror = d / "pkg"
        shutil.copytree(SKILL, mirror,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        # MANIFEST is what sync-mirror.sh publishes; simulate it.
        entries = sorted(
            str(p.relative_to(mirror)) for p in mirror.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
        (mirror / "MANIFEST").write_text("\n".join(entries) + "\n")

        lone = d / "install.sh"
        shutil.copy(INSTALL, lone)          # script only, no skills/ beside it
        home = d / "home"
        (home / ".claude").mkdir(parents=True)

        env = dict(os.environ, HOME=str(home),
                   IRONCLAD_MIRROR=f"file://{mirror}")
        r = run(["bash", str(lone)], cwd=d, env=env, timeout=240)
        skill_dir = home / ".agents" / "skills" / "ironclad"

        if not skill_dir.is_dir():
            bad("curl-only install creates the skill", r.stdout + r.stderr)
            return

        for required in ("scripts/update_check.py", "assets/presets/coherence.yml",
                         "scripts/check_schema.py", "scripts/drill.py"):
            if not (skill_dir / required).is_file():
                bad(f"curl-only install ships {required}",
                    "this is BUG-A returning: " + r.stdout[-800:])
            else:
                ok(f"curl-only install ships {required}")

        # `bin/` is deliberately not installed into the skill dir (install.sh
        # removes it); the command lands in ~/.local/bin instead, with
        # IRONCLAD_HOME baked in. Assert the real thing, not the payload copy.
        ic = home / ".local" / "bin" / "ironclad"
        if not ic.is_file():
            bad("curl-only install writes ~/.local/bin/ironclad", r.stdout[-800:])
            return
        ok("curl-only install writes ~/.local/bin/ironclad")

        if str(skill_dir) not in ic.read_text():
            bad("the installed command points at the installed skill",
                f"IRONCLAD_HOME not baked in: {ic.read_text().splitlines()[:3]}")
        else:
            ok("the installed command points at the installed skill")

        # The two commands that used to be broken must work.
        r = run([str(ic), "update", "--check"], cwd=d, env=env)
        if "is missing" in (r.stdout + r.stderr):
            bad("curl-only install: `ironclad update` runs", r.stdout + r.stderr)
        else:
            ok("curl-only install: `ironclad update` runs")

        (d / "proj").mkdir()
        r = run([str(ic), "init", "coherence"], cwd=d / "proj", env=env)
        if "unknown preset" in (r.stdout + r.stderr):
            bad("curl-only install: `ironclad init coherence` works",
                r.stdout + r.stderr)
        else:
            ok("curl-only install: `ironclad init coherence` works")


def test_wrapper_does_not_append_preset():
    """Guards the shape of the fix, so a future edit cannot reintroduce BUG-B."""
    src = (SKILL / "bin" / "ironclad").read_text()
    line = next((ln for ln in src.splitlines()
                 if "python3 \"$CHECKER\"" in ln), "")
    if "--preset" in line:
        bad("wrapper passes checker args through untouched",
            f"wrapper still appends --preset: {line.strip()}")
    else:
        ok("wrapper passes checker args through untouched")


def test_package_ships_with_the_checker():
    """check_schema.py is an entry point; without ironclad_core it exits 3.

    Every path that copies the checker somewhere — the install payload, the
    front matter of `ironclad init`, `--with-checker` — must copy the package
    too, or that copy is dead on arrival.
    """
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        repo = d / "repo"
        repo.mkdir()
        (repo / "a.sql").write_text("CREATE TABLE a (id INT, status ENUM('x'));\n")

        env = dict(os.environ, USERPROFILE=str(repo))     # Windows-safe, unused here
        r = run([sys.executable, str(SKILL / "scripts" / "init_standards.py"),
                 str(repo), "--preset", "strict", "--with-checker"], env=env)
        core = repo / "scripts" / "ironclad_core"
        if not core.is_dir():
            bad("--with-checker copies ironclad_core/", r.stdout + r.stderr)
            return
        ok("--with-checker copies ironclad_core/")

        r = run([sys.executable, "scripts/check_schema.py", "."], cwd=repo)
        if r.returncode == 3 or "engine is missing" in (r.stdout + r.stderr):
            bad("the copied checker runs", r.stdout + r.stderr)
        elif r.returncode != 1:
            bad("the copied checker runs", f"expected exit 1, got {r.returncode}\n"
                                           f"{r.stdout}{r.stderr}")
        else:
            ok("the copied checker runs")

        # And the same copy must work with the skill gone from disk.
        r = run([sys.executable, "scripts/check_schema.py", "."], cwd=repo,
                env={k: v for k, v in os.environ.items() if k != "IRONCLAD_HOME"})
        if r.returncode != 1:
            bad("the copied checker works without the skill on disk",
                f"exit {r.returncode}\n{r.stdout}{r.stderr}")
        else:
            ok("the copied checker works without the skill on disk")


def main() -> int:
    print("Regression tests — false passes found by the 0.10.2 audit\n")
    for fn in (test_preset_flag_wins_over_repo,
               test_repo_preset_layers_with_flag,
               test_coherence_repo_is_checkable,
               test_manifest_matches_payload,
               test_curl_only_install_gets_full_payload,
               test_package_ships_with_the_checker,
               test_wrapper_does_not_append_preset):
        print(f"{fn.__name__}:")
        try:
            fn()
        except Exception as exc:                    # noqa: BLE001
            bad(fn.__name__, f"{type(exc).__name__}: {exc}")
    print(f"\n{passed} passed, {failed} failed")
    if failed:
        print("\nThese are the failures this file exists to catch. Do not ship.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
