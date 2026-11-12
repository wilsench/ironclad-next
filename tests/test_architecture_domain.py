"""Architecture domain: what it must catch, and what it must stay quiet about.

Half of this file is negative. A rule that fires on correct code is worse than no
rule, and every rejection in `domains/architecture.py` came from a measurement on
a real repository — so each one gets a fixture that would have tripped a naive
implementation.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import textwrap
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "ironclad"
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
            print(textwrap.indent(str(detail), "        "))


def run(root: Path, *args, preset="balanced"):
    r = subprocess.run([sys.executable, str(CHECKER), str(root), "--preset", preset, *args],
                       capture_output=True, text=True)
    return r


def findings(out: str, rule: str) -> list[str]:
    return [l for l in out.splitlines() if f"[{rule}]" in l]


class Repo:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp())

    def write(self, rel: str, text: str):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text).lstrip())
        return p

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


print("ARCH-01 — cycles")
r = Repo()
r.write("src/a.js", "import { b } from './b';\nexport const a = 1;")
r.write("src/b.js", "import { c } from './c';\nexport const b = 2;")
r.write("src/c.js", "import { a } from './a';\nexport const c = 3;")
res = run(r.root)
got = findings(res.stdout, "ARCH-01")
check("a 3-file cycle is reported once", len(got) == 1, res.stdout)
check("the message names all three files",
      all(n in got[0] for n in ("a.js", "b.js", "c.js")) if got else False, got)
check("a cycle does not fail the build by default", res.returncode == 0, res.returncode)
strict = run(r.root, preset="strict")
check("strict turns the cycle into an error",
      any("ARCH-01" in l and "ERROR" in l for l in strict.stdout.splitlines()), strict.stdout)
r.close()

r = Repo()
r.write("src/self.js", "import './self';")
res = run(r.root)
check("a file importing itself is a cycle",
      len(findings(res.stdout, "ARCH-01")) == 1, res.stdout)
r.close()

r = Repo()
r.write("src/a.js", "import './b';")
r.write("src/b.js", "import './c';")
r.write("src/c.js", "export const c = 1;")
res = run(r.root)
check("a DAG is not a cycle", findings(res.stdout, "ARCH-01") == [], res.stdout)
r.close()

r = Repo()
r.write("src/index.ts", "import type { A } from './a';\nexport const x = 1;")
r.write("src/a.ts", "import { x } from './index';\nexport type A = number;")
res = run(r.root)
check("a type-only import does not close a cycle", findings(res.stdout, "ARCH-01") == [],
      res.stdout)
r.close()

r = Repo()
r.write("app/A.php", "<?php\nnamespace App;\nuse App\\B;\nclass A extends B {}\n")
r.write("app/B.php", "<?php\nnamespace App;\nuse App\\A;\nclass B extends A {}\n")
res = run(r.root)
check("mutual PHP inheritance is a cycle", len(findings(res.stdout, "ARCH-01")) == 1,
      res.stdout)
r.close()

r = Repo()
r.write("app/Res.php", "<?php\nnamespace App;\nuse App\\Page;\nclass Res { public $p = Page::class; }\n")
r.write("app/Page.php", "<?php\nnamespace App;\nuse App\\Res;\nclass Page extends Base {}\n")
r.write("app/Base.php", "<?php\nnamespace App;\nclass Base {}\n")
res = run(r.root)
check("PHP `use` alone is an alias, not an edge (Laravel Resource/Page shape)",
      findings(res.stdout, "ARCH-01") == [], res.stdout)
r.close()

r = Repo()
r.write("app/Kid.php", "<?php\nnamespace App;\nclass Kid extends Base { use HasThing; }\n")
r.write("app/HasThing.php", "<?php\nnamespace App;\ntrait HasThing {}\n")
r.write("app/Base.php", "<?php\nnamespace App;\nclass Base { use HasThing; }\n")
res = run(r.root)
check("a trait used by both parent and child is not a cycle",
      findings(res.stdout, "ARCH-01") == [], res.stdout)
r.close()

r = Repo()
r.write("lib/main.py", "from .helper import go\n")
r.write("lib/helper.py", "from .main import go\n")
res = run(r.root)
check("relative python imports form a cycle", len(findings(res.stdout, "ARCH-01")) == 1,
      res.stdout)
r.close()

print("\nARCH-02 — broken imports")
r = Repo()
r.write("src/main.ts", "import { a } from './present';\nimport { b } from './gone';\n")
r.write("src/present.ts", "export const a = 1;")
res = run(r.root)
got = findings(res.stdout, "ARCH-02")
check("a missing target is reported", len(got) == 1, res.stdout)
check("the existing target is not reported", "gone" in got[0] and "present" not in got[0], got)
r.close()

r = Repo()
r.write("src/a.ts", "import { b } from './b.js';")
r.write("src/b.ts", "export const b = 1;")
res = run(r.root)
check("./b.js resolving to b.ts is correct TypeScript, not a broken import",
      findings(res.stdout, "ARCH-02") == [], res.stdout)
r.close()

r = Repo()
r.write("src/a.ts", "import { x } from '@/components/x';\nimport { y } from 'react';")
r.write("src/components/x.ts", "export const x = 1;")
r.write("tsconfig.json", '{"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./src/*"]}}}')
res = run(r.root)
check("a configured alias is left to the bundler", findings(res.stdout, "ARCH-02") == [],
      res.stdout)
r.close()

r = Repo()
r.write("src/a.ts", "import './missing';")
res = run(r.root)
check("a missing import in a repo with no tsconfig is still reported",
      len(findings(res.stdout, "ARCH-02")) == 1, res.stdout)
r.close()

r = Repo()
r.write("src/a.ts", "import './a';")
res = run(r.root)
check("importing your own file is a cycle of one, not a broken import",
      len(findings(res.stdout, "ARCH-01")) == 1 and not findings(res.stdout, "ARCH-02"),
      res.stdout)
r.close()

r = Repo()
r.write("src/a.ts", "import '../../../../etc/passwd';")
res = run(r.root)
check("an import escaping the project is not followed",
      all("ARCH-01" not in l for l in res.stdout.splitlines()), res.stdout)
r.close()

print("\nCoverage honesty")
r = Repo()
r.write("src/a.ts", "import './b';")
r.write("src/b.ts", "export const b = 1;")
res = run(r.root)
check("a clean JS repo exits 0, not 2", res.returncode == 0, res.stdout + res.stderr)
check("and reports the files it read", re.search(r"^[1-9]\d* file\(s\)", res.stdout, re.M)
      is not None, res.stdout)
r.close()

r = Repo()
r.write("app/models.py", "from django.db import models\nclass A(models.Model):\n    n = models.IntegerField()\n")
r.write("src/a.js", "export const a = 1;")
res = run(r.root)
check("a Django repo still refuses to look clean", res.returncode == 2, res.stdout + res.stderr)
check("and says so out loud", "do not treat this as a pass" in res.stderr.lower(), res.stderr)
r.close()

r = Repo()
r.write("public/dump.js", "Some bundled doc mentioning Sequelize DataTypes.INTEGER and pgTable")
r.write("src/a.ts", "export const a = 1;")
res = run(r.root)
check("a built asset describing an ORM is not schema",
      res.returncode == 0, res.stdout + res.stderr)
r.close()

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
