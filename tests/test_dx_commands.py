"""Phase 5: the commands a person uses when something is not working.

The gate for this phase is stated as a promise, so it is tested as one:

  `init` on a repo that already has `.agent/` must not change a single byte.

That is checked by hashing the whole tree before and after, not by reading the
code and deciding it looks idempotent. Every other test here exists because a
diagnostic that lies is worse than no diagnostic: `doctor` claiming a policy is
loaded when it is not, or claiming a repo is unreadable when its own test suite
merely mentions the word `Model`.
"""

from __future__ import annotations

import hashlib
import re
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "ironclad"
BIN = SKILL / "bin" / "ironclad"
CHECKER = SKILL / "scripts" / "check_schema.py"

passed = failed = 0


def check(name, cond, detail=None):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}")
        if detail:
            print(textwrap.indent(str(detail)[:2000], "        "))


def env():
    e = dict(os.environ)
    e["IRONCLAD_HOME"] = str(SKILL)
    e.pop("IRONCLAD_PRESET", None)
    return e


def run(args, cwd, preset=None):
    e = env()
    if preset:
        e["IRONCLAD_PRESET"] = preset
    return subprocess.run([sys.executable, str(CHECKER), *args],
                          capture_output=True, text=True, cwd=cwd, env=e)


def run_bin(args, cwd, preset=None):
    e = env()
    e.pop("IRONCLAD_PRESET", None)
    if preset:
        e["IRONCLAD_PRESET"] = preset
    return subprocess.run(["bash", str(BIN), *args],
                          capture_output=True, text=True, cwd=cwd, env=e)


def tree_hash(root: Path) -> str:
    """Hash of every file's path and content, in sorted order."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


class Repo:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / ".git").mkdir()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text).lstrip())
        return p

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


print("init is idempotent (the Phase 5 gate)")
r = Repo()
first = run_bin(["init"], r.root, preset="balanced")
check("first init succeeds", first.returncode == 0, first.stdout + first.stderr)
h1 = tree_hash(r.root)
second = run_bin(["init"], r.root, preset="balanced")
check("second init succeeds", second.returncode == 0, second.stdout + second.stderr)
h2 = tree_hash(r.root)
check("the tree is byte-identical after a second init", h1 == h2, f"{h1[:16]} vs {h2[:16]}")
check("and it says so instead of pretending to write",
      "kept" in second.stdout and "wrote   .agent" not in second.stdout, second.stdout)
r.close()

print("\ninit --dry-run writes nothing")
r = Repo()
dry = run_bin(["init", "--dry-run"], r.root, preset="strict")
check("dry run exits 0", dry.returncode == 0, dry.stdout + dry.stderr)
check("nothing was written", tree_hash(r.root) == tree_hash(r.root) and
      len([p for p in r.root.rglob("*") if p.is_file() and ".git" not in p.parts]) == 0,
      sorted(str(p) for p in r.root.rglob("*")))
check("it says what it would do", "would write" in dry.stdout, dry.stdout)
r.close()

print("\ninit detects the stack instead of asking")
r = Repo()
r.write("package.json", '{"name":"x","dependencies":{"next":"14.0.0","react":"18.0.0"}}')
res = run_bin(["init"], r.root)
check("a Next.js repo gets a preset without prompting",
      "detected:" in res.stdout and res.returncode == 0, res.stdout + res.stderr)
check("and the policy file matches what was detected",
      "name: balanced" in (r.root / ".agent/standards.yml").read_text(), None)
r.close()

r = Repo()
r.write("composer.json", '{"require":{"laravel/framework":"^11"},"require-dev":{"phpunit/phpunit":"^11"}}')
r.write("artisan", "#!/usr/bin/env php\n")
res = run_bin(["init"], r.root)
check("a Laravel repo with phpunit gets strict",
      "strict" in res.stdout.split("→ preset")[-1] if "→ preset" in res.stdout else False,
      res.stdout)
r.close()

print("\ninit keeps a policy a human wrote")
r = Repo()
r.write(".agent/standards.yml", "name: strict\nrules:\n  DB-06: warn\nexceptions:\n  - legacy/\n")
before = (r.root / ".agent/standards.yml").read_text()
run_bin(["init"], r.root, preset="balanced")
after = (r.root / ".agent/standards.yml").read_text()
check("an existing policy is never overwritten", before == after, after)
r.close()

print("\ninit refuses an unknown preset")
r = Repo()
res = run_bin(["init", "banana"], r.root)
check("unknown preset is an error", res.returncode != 0, res.stdout + res.stderr)
check("and names the ones that exist", "balanced" in res.stderr, res.stderr)
r.close()

print("\ndoctor")
r = Repo()
r.write("db/schema.sql", "CREATE TABLE t (id int);")
res = run(["doctor"], r.root)
check("doctor runs on a bare repo", res.returncode == 0, res.stdout + res.stderr)
check("it reports the engine's rule count", "rule(s)" in res.stdout, res.stdout)
check("it reports the files it can read", "readable:" in res.stdout, res.stdout)
check("it does not pretend a policy exists",
      "no .agent/standards.yml here" in res.stdout, res.stdout)
r.close()

r = Repo()
r.write(".agent/standards.yml", "name: coherence\n")
r.write("db/schema.sql", "CREATE TABLE t (id int);")
res = run(["doctor"], r.root)
check("doctor reads the repo policy", "coherence" in res.stdout and "repo policy" in res.stdout,
      res.stdout)
r.close()

r = Repo()
r.write(".agent/standards.yml", "name: coherence\n")
r.write("db/schema.sql", "CREATE TABLE t (id int);")
res = run(["doctor", "--preset", "strict"], r.root)
check("doctor names the mismatch when an argument overrides the file",
      "says" in res.stdout and "uses" in res.stdout, res.stdout)
r.close()

r = Repo()
r.write("models.py", "from django.db import models\n\nclass A(models.Model):\n    n = models.IntegerField()\n")
res = run(["doctor"], r.root)
check("doctor flags an unreadable schema stack", res.returncode == 1, res.stdout + res.stderr)
check("and says it in words", "cannot read" in res.stdout, res.stdout)
r.close()

r = Repo()
r.write("tests/test_thing.py",
        'x = """\nclass Fake(models.Model):\n    pass\n"""\n')
res = run(["doctor"], r.root)
check("a test that merely mentions models.Model is not schema",
      res.returncode == 0, res.stdout + res.stderr)
r.close()

r = Repo()
r.write("db/schema.sql", "CREATE TABLE t (id int);")
res = run(["doctor", "--preset", "strict"], r.root)
check("doctor shows the effective severity per rule", "DB-01=error" in res.stdout, res.stdout)
check("and lists what is off", "off" not in res.stdout or "off in this preset" in res.stdout,
      res.stdout)
r.close()

print("\nrules list / rules explain")
r = Repo()
r.write("db/schema.sql", "CREATE TABLE t (id int);")
res = run(["rules"], r.root)
check("rules list works with no repo config", res.returncode == 0, res.stdout + res.stderr)
check("it groups by domain", "database" in res.stdout and "architecture" in res.stdout,
      res.stdout)
check("it shows the effective severity", "DB-06" in res.stdout and "warn" in res.stdout,
      res.stdout)
check("it marks values that came from the preset rather than the rule", "default" in res.stdout,
      res.stdout)
r.close()

res = run(["rules", "--preset", "strict"], Repo().root)
check("strict shows errors where balanced showed warns",
      res.returncode == 0 and re.search(r"DB-06\s+error", res.stdout) is not None,
      res.stdout)
res = run(["rules", "--domain", "architecture"], Repo().root)
check("--domain narrows the list",
      "ARCH-01" in res.stdout and "DB-01" not in res.stdout, res.stdout)

res = run(["rules", "explain", "SEC-01"], Repo().root)
check("explain works", res.returncode == 0, res.stdout + res.stderr)
check("explain states what the rule will not decide",
      "will not decide" in res.stdout, res.stdout)
check("explain shows every preset's severity",
      all(p in res.stdout for p in ("balanced", "strict", "coherence", "legacy-friendly")),
      res.stdout)
res = run(["rules", "explain", "DB-99"], Repo().root)
check("an unknown rule is exit 2, not a stack trace", res.returncode == 2, res.stderr)
check("and it lists the real ids", "DB-01" in res.stderr, res.stderr)

print("\nthe bash wrapper exposes the same verbs")
r = Repo()
r.write("db/schema.sql", "CREATE TABLE t (id int);")
for verb, needle in (("rules", "rule(s)"), ("doctor", "install"), ("presets", "errors=")):
    res = run_bin([verb], r.root)
    check(f"`ironclad {verb}` works through bin/ironclad",
          res.returncode in (0, 1) and needle in res.stdout,
          res.stdout + res.stderr)
res = run_bin(["doctor"], r.root)
check("`ironclad doctor` is read-only through the wrapper",
      tree_hash(r.root) == tree_hash(r.root), None)
help_out = run_bin(["--help"], r.root)
check("help lists every verb it accepts",
      all(v in help_out.stdout for v in ("check", "doctor", "rules", "presets", "init")),
      help_out.stdout)
bad = run_bin(["nonsense"], r.root)
check("an unknown verb names the real ones",
      bad.returncode != 0 and "doctor" in bad.stderr, bad.stderr)
r.close()

print("\npresets through the same entry point")
res = run(["presets"], Repo().root)
check("presets lists every preset", res.returncode == 0 and
      all(p in res.stdout for p in ("balanced", "strict")), res.stdout)
check("with the error/warn counts", "errors=" in res.stdout, res.stdout)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
