#!/usr/bin/env python3
"""Record the checker's exact observable behaviour, so a refactor can be proven
not to change it.

Phase 1 moves the engine out of check_schema.py and into a package. That is only
safe if the observable surface — stdout, stderr, exit code — is identical
afterwards. "The selftest still passes" is not enough: the selftest checks
verdicts, not wording, ordering, or the shape of --json.

Usage:
  python3 tests/capture_behaviour.py before > baseline.json
  python3 tests/capture_behaviour.py after  > after.json
  python3 tests/capture_behaviour.py diff baseline.json after.json

The 'diff' mode prints every case that changed and exits 1 if any did.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "ironclad"
CHECKER = SKILL / "scripts" / "check_schema.py"

# Every case is (name, argv, workdir-key). Workdirs are built fresh below so the
# captured output cannot depend on where this happens to run.
FIXTURES = {
    "clean": {
        "users.sql": """\
CREATE TABLE users (
  id BIGINT PRIMARY KEY,
  status_code SMALLINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  amount NUMERIC(14,2) NOT NULL,
  FOREIGN KEY (status_code) REFERENCES user_status(code)
);
""",
    },
    "dirty": {
        "users.sql": """\
CREATE TABLE users (
  id BIGINT PRIMARY KEY,
  status ENUM('active','banned'),
  stock_state VARCHAR(32),
  departure_at TIMESTAMP,
  total FLOAT,
  is_status BOOLEAN
);
-- status = 3
UPDATE users SET status_code = 2;
SELECT * FROM users WHERE status = 1;
""",
    },
    "mixed": {
        "a.sql": "CREATE TABLE a (id INT, status ENUM('open'));\n",
        "b.sql": "CREATE TABLE b (id INT, status INT, FOREIGN KEY (status) REFERENCES s(id));\n",
        "c.sql": "CREATE TABLE c (id INT, state VARCHAR(20));\n",
    },
    "no_schema": {
        "README.md": "no schema here\n",
    },
    "unsupported": {
        "models.py": "from django.db import models\nstatus = models.IntegerField()\n",
    },
    "http_codes": {
        "Client.php": "<?php\nif ($res.status === 404) { return; }\n$xhr.status == 500;\n",
    },
    "laravel": {
        "database/migrations/2024_01_01_000000_create_orders_table.php": """\
<?php
Schema::create('orders', function (Blueprint $table) {
    $table->enum('status', ['new', 'paid']);
    $table->string('departure_status');
    $table->timestamp('expected_at');
    $table->float('total_price');
});
""",
    },
    "exception": {
        "app.sql": "CREATE TABLE t (id INT, status TEXT);\n",
        "vendor.sql": "CREATE TABLE v (id INT, status ENUM('a','b'));\n",
        ".agent/standards.yml": "name: balanced\nexceptions:\n  - vendor.sql\n",
    },
    "coherence_repo": {
        "a.sql": "CREATE TABLE a (id INT, status ENUM('open'));\n",
        "b.sql": "CREATE TABLE b (id INT, status INT, FOREIGN KEY (status) REFERENCES s(id));\n",
        ".agent/standards.yml": "name: coherence\n",
    },
    "name_only_strict": {
        "a.sql": "CREATE TABLE a (id INT, status TEXT);\n",
        ".agent/standards.yml": "name: strict\n",
    },
}

ARGVS = [
    [],
    ["--json"],
    ["--preset", "balanced"],
    ["--preset", "strict"],
    ["--preset", "legacy-friendly"],
    ["--preset", "coherence"],
    ["--strict"],
    ["--json", "--preset", "strict"],
]

FLAGS = [
    ["--list-presets"],
    ["--preset", "nope"],
    ["--config", "missing.yml"],
]


def build(root: Path) -> None:
    for name, files in FIXTURES.items():
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        for rel, body in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)


def run_case(cwd: Path, argv: list[str]) -> dict:
    p = subprocess.run([sys.executable, str(CHECKER), *argv],
                       cwd=cwd, capture_output=True, text=True)
    # Paths in the output are absolute and machine-specific; normalise them so
    # two runs in different temp dirs stay comparable.
    def norm(s: str) -> str:
        return s.replace(str(cwd), "<CWD>")
    return {"exit": p.returncode, "stdout": norm(p.stdout), "stderr": norm(p.stderr)}


def capture() -> dict:
    out = {}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        build(root)

        for fixture in sorted(FIXTURES):
            cwd = root / fixture
            for argv in ARGVS:
                key = f"{fixture} :: {' '.join(argv) or '<none>'}"
                out[key] = run_case(cwd, argv)
            for extra in FIXTURES[fixture]:
                if extra.endswith((".sql", ".php", ".prisma")):
                    for argv in ([], ["--json"]):
                        key = f"{fixture}/{extra} :: {' '.join(argv) or '<none>'}"
                        out[key] = run_case(cwd, [extra, *argv])

        # Repo-level flags run from an empty dir.
        empty = root / "empty"
        empty.mkdir()
        for argv in FLAGS:
            key = f"<empty> :: {' '.join(argv)}"
            out[key] = run_case(empty, argv)

        # A subdirectory target, to exercise the walk-up config lookup.
        out["mixed/subdir target :: <none>"] = run_case(root / "mixed", ["a.sql"])
    return out


def diff(old: dict, new: dict) -> int:
    changed = 0
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if a == b:
            continue
        changed += 1
        print(f"\n### {key}")
        if a is None:
            print("  only in new")
            continue
        if b is None:
            print("  only in old")
            continue
        for field in ("exit", "stdout", "stderr"):
            if a[field] != b[field]:
                print(f"  {field}:")
                print(f"    before: {a[field]!r}")
                print(f"    after : {b[field]!r}")
    print(f"\n{len(old)} cases, {changed} changed")
    return 1 if changed else 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "before"
    if mode == "diff":
        old = json.loads(Path(sys.argv[2]).read_text())
        new = json.loads(Path(sys.argv[3]).read_text())
        return diff(old, new)
    print(json.dumps(capture(), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
