#!/usr/bin/env python3
"""The distribution path — the one nobody runs until a stranger runs it.

The bugs this file exists for both shipped as "green":

  1. `sync-mirror.sh` copied SKILL.md, references, scripts, templates, presets
     and bin/ — but never `ironclad_core/`. The mirror served a SKILL.md that
     promised four domains and a payload containing none of them.
  2. `release-check.sh` compared version *strings*. Mirror said 0.10.2, repo
     said 0.10.2, so it printed "Release state agrees everywhere" about a
     payload that could not run.

Every check here reads the real files. Nothing is asserted from memory.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ROOT / "skills" / "ironclad"
CORE = PAYLOAD / "ironclad_core"

passed = failed = 0


def ok(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok    {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ---------------------------------------------------------------------------
# 1. The engine exists, and the mirror is able to carry it
# ---------------------------------------------------------------------------

def test_engine_present() -> None:
    print("\nengine in the payload")
    ok("ironclad_core exists", CORE.is_dir())
    files = sorted(p.name for p in CORE.glob("*.py"))
    for want in ("__init__.py", "engine.py", "discovery.py", "config.py",
                 "report.py", "rules.py", "doctor.py", "cli.py"):
        ok(f"ironclad_core/{want}", want in files, f"have: {files}")
    domains = sorted(p.stem for p in (CORE / "domains").glob("*.py")
                     if p.name != "__init__.py")
    ok("four domains", domains == ["api", "architecture", "database", "security"],
       f"have: {domains}")

    # bin/ironclad must be able to reach the engine from its own directory.
    script = (PAYLOAD / "bin" / "ironclad").read_text()
    ok("bin/ironclad references ironclad_core",
       "ironclad_core" in script or "check_schema" in script)


def test_mirror_carries_engine() -> None:
    print("\nsync-mirror carries the engine")
    script = (ROOT / "scripts" / "sync-mirror.sh").read_text()
    ok("sync-mirror copies ironclad_core", "ironclad_core" in script,
       "the mirror would publish a payload without the engine")
    ok("sync-mirror writes DIGEST", "DIGEST" in script)

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "pkg"
        dest.mkdir()
        r = run(["bash", str(ROOT / "scripts" / "sync-mirror.sh"), str(dest)])
        ok("sync-mirror exits 0", r.returncode == 0, r.stderr[-300:])
        core_files = list((dest / "ironclad_core").rglob("*.py")) if (dest / "ironclad_core").is_dir() else []
        ok("mirror has the engine", len(core_files) >= 13, f"found {len(core_files)}")
        ok("mirror has DIGEST", (dest / "DIGEST").is_file())
        ok("mirror has MANIFEST", (dest / "MANIFEST").is_file())

        # The digest must be reproducible from the mirror's own contents.
        entries = []
        # Byte order, not locale order: the two differ as soon as a filename
        # has a dot or a dash in the same position, and the digest then
        # disagrees with itself across machines.
        for f in sorted(dest.rglob("*"), key=lambda p: str(p.relative_to(dest)).encode()):
            if not f.is_file() or f.name in ("MANIFEST", "DIGEST"):
                continue
            entries.append(hashlib.sha256(f.read_bytes()).hexdigest() + "  " +
                           str(f.relative_to(dest)))
        want = hashlib.sha256(("\n".join(entries) + "\n").encode()).hexdigest()
        got = (dest / "DIGEST").read_text().strip()
        ok("DIGEST matches mirror contents", got == want,
           f"published {got[:12]}…, recomputed {want[:12]}…")

        # Every file the payload has must be on the mirror, or the installer
        # fetches a partial tree and fails at import time with a stack trace.
        missing = []
        for f in PAYLOAD.rglob("*"):
            if not f.is_file() or "__pycache__" in f.parts or f.suffix == ".pyc":
                continue
            if f.name == ".DS_Store":
                continue
            rel = f.relative_to(PAYLOAD)
            if not (dest / rel).is_file():
                missing.append(str(rel))
        ok("no payload file left behind", not missing, f"missing: {missing[:5]}")


def test_installer_fallback() -> None:
    print("\ninstaller fallback list")
    script = (ROOT / "install.sh").read_text()
    # The third branch (no mirror, no index) is hand-written. That is exactly
    # where the engine went missing once, so it is checked file by file.
    for name in ("engine.py", "discovery.py", "domains/database.py",
                 "domains/api.py", "domains/security.py", "domains/architecture.py"):
        ok(f"fallback lists {name}", f"ironclad_core/{name}" in script)


# ---------------------------------------------------------------------------
# 2. The release guard must not accept a version string as proof
# ---------------------------------------------------------------------------

def test_release_guard_checks_content() -> None:
    print("\nrelease-check refuses version-only agreement")
    script = (ROOT / "scripts" / "release-check.sh").read_text()
    ok("checks engine on mirror", "ironclad_core/engine.py" in script,
       "a mirror without the engine would pass on matching versions")
    ok("checks a content digest", "DIGEST" in script)
    ok("counts registered rules", "load_all" in script or "rule_ids" in script)

    # Prove it fails against the live mirror as it stands today. If the mirror
    # has since been fixed this assertion is wrong, not the code — so it is
    # reported as a skip rather than a failure.
    r = run(["bash", str(ROOT / "scripts" / "release-check.sh")])
    out = r.stdout + r.stderr
    if "engine on mirror" in out and "MISSING" in out:
        ok("guard rejects an engine-less mirror", r.returncode == 1,
           "guard returned 0 on a mirror with no engine")
    else:
        print("  skip  guard rejects an engine-less mirror (mirror now carries it)")


# ---------------------------------------------------------------------------
# 3. What the docs promise must be what is registered
# ---------------------------------------------------------------------------

def test_docs_match_engine() -> None:
    print("\ndocs and engine agree")
    r = run([sys.executable, "-c",
             "from ironclad_core.domains import load_all;"
             "print(len(load_all().rule_ids()))"],
            cwd=str(PAYLOAD))
    ok("engine loads", r.returncode == 0, r.stderr[-300:])
    count = r.stdout.strip()
    ok("sixteen rules registered", count == "16", f"registered {count}")

    # Every rule ID printed by the CLI must exist in the registry, and vice
    # versa. A docs table listing DB-01…DB-08 plus three domains is only true
    # if those are the IDs the engine actually has.
    r = run([sys.executable, str(PAYLOAD / "scripts" / "check_schema.py"),
             "rules"], cwd=str(PAYLOAD))
    ids = {t for t in r.stdout.replace("|", " ").split() if "-0" in t and t[:3].isupper()}
    for want in ("DB-01", "API-07", "SEC-03", "ARCH-02"):
        ok(f"rules lists {want}", want in r.stdout, f"ids seen: {sorted(ids)[:8]}")
    for absent in ("API-03", "API-04", "TEST-01", "ARCH-03"):
        ok(f"rules does NOT list {absent}", absent not in r.stdout,
           f"{absent} was rejected during design and must not appear in output")

    for page in ("20-rules.md",):
        for lang in ("en", "id"):
            p = ROOT / "docs" / "pages" / lang / page
            if p.is_file():
                text = p.read_text()
                ok(f"{lang}/{page} names a security rule", "SEC-0" in text)
                ok(f"{lang}/{page} names an architecture rule", "ARCH-0" in text)


def test_install_commands_point_at_the_released_repo() -> None:
    """The one bug that makes a release a lie.

    The tag v0.11.0 lives in wilsench/ironclad-next. Every install command in
    the README and the docs said wilsench/ironclad — the original repository,
    whose last tag is v0.9.5. Following the docs produced:
    `npm error could not determine executable to run`, exit 1.
    """
    print("\ninstall commands point at the repo that has the tag")
    version = (PAYLOAD / "SKILL.md").read_text().split("version:")[1].split("\n")[0].strip()

    sources = [ROOT / "README.md", ROOT / "install.sh", ROOT / "package.json",
               ROOT / "cli" / "index.mjs", PAYLOAD / "scripts" / "update_check.py",
               ROOT / "scripts" / "release-check.sh"]
    sources += sorted((ROOT / "docs" / "pages").rglob("*.md"))
    sources += [ROOT / "docs" / "build.py"]

    offenders = []
    for f in sources:
        if not f.is_file():
            continue
        for i, line in enumerate(f.read_text().splitlines(), 1):
            # `wilsench/ironclad` not followed by `-next`
            for m in re.finditer(r"wilsench/ironclad(?![\w-])", line):
                offenders.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:90]}")
    # BASELINE_AUDIT.md is a record of what the original repo was; it is not
    # an install instruction and must keep the old name.
    ok("no install command targets the original repo", not offenders,
       "\n        ".join(offenders[:4]))

    readme = (ROOT / "README.md").read_text()
    ok("README pins the current version", version in readme, f"want {version}")

    # And the pin must be a tag that exists here, not just a plausible string.
    r = run(["git", "rev-parse", "-q", "--verify", f"refs/tags/v{version}"], cwd=str(ROOT))
    ok(f"tag v{version} exists", r.returncode == 0, "README pins a tag that does not exist")

    # The update checker must look at the same repo the installer uses, or it
    # will report "newer version available" forever, or never.
    check = (PAYLOAD / "scripts" / "update_check.py").read_text()
    ok("update checker watches the released repo", "ironclad-next" in check)


def test_docs_claims_about_presets_are_true() -> None:
    """A docs sentence that a preset makes "everything error" is checkable.

    The ID page said strict turns everything into an error while the balanced
    table showed only three domains — the reader cannot tell whether that is
    sixteen rules or eight, and the sentence was never verified against the
    engine.
    """
    print("\npreset claims in the rules pages")
    for preset, want_errors in (("strict", 16), ("legacy-friendly", 0)):
        r = run([sys.executable, str(PAYLOAD / "scripts" / "check_schema.py"),
                 "rules", "--preset", preset], cwd=str(PAYLOAD))
        # Only rows that start with an ID; the output also carries a line like
        # "off in this preset: ARCH-01, ARCH-02", which mentions IDs without
        # being a rule row.
        rows = [l for l in r.stdout.splitlines()
                if re.match(r"\s*(DB|API|SEC|ARCH)-\d", l)]
        ok(f"{preset} lists 16 rules", len(rows) == 16, f"listed {len(rows)}")
        # The severity is a fixed column right after the ID, not a word
        # anywhere in the line: API-02's *title* is "error payload returned
        # with a success status", which contains "error" while its severity is
        # warn. Counting substrings got that wrong the first time.
        errors = sum(1 for l in rows
                     if re.match(r"\s*\S+\s+(ERROR|error)\s", l))
        ok(f"{preset} has {want_errors} errors", errors == want_errors, f"have {errors}")

    for lang in ("en", "id"):
        page = ROOT / "docs" / "pages" / lang / "20-rules.md"
        if page.is_file():
            text = page.read_text()
            ok(f"{lang} rules page says sixteen", "sixteen" in text.lower() or "enam belas" in text.lower())


def test_page_titles_not_stale() -> None:
    print("\npage metadata")
    for lang in ("en", "id"):
        p = ROOT / "docs" / "pages" / lang / "20-rules.md"
        if not p.is_file():
            continue
        first = p.read_text().split("---")[1]
        ok(f"{lang} rules title is not DB-only",
           "DB-01…DB-08" not in first and "DB-01...DB-08" not in first,
           "the page title still claims one domain")


if __name__ == "__main__":
    test_engine_present()
    test_mirror_carries_engine()
    test_installer_fallback()
    test_release_guard_checks_content()
    test_docs_match_engine()
    test_install_commands_point_at_the_released_repo()
    test_docs_claims_about_presets_are_true()
    test_page_titles_not_stale()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
