"""Which files to look at, and which ones we cannot read.

Two responsibilities that must stay together, because the whole honesty policy
is the link between them: `iter_files` returns what will be scanned, and
`find_unsupported` returns what is unambiguously schema but in a stack this
checker cannot parse. If only the first existed, a repo full of Django models
would report "0 findings" and look clean.
"""

from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".next",
             "storage", "__pycache__", ".venv", "venv"}

TARGETS = {".sql", ".php", ".prisma"}

# Stacks this checker cannot read yet, but whose files are unambiguously schema.
# Staying silent about them is the worst failure mode available: the run is
# green, the CI badge is green, and half the repo was never looked at.
UNSUPPORTED_HINTS = {
    ".py": re.compile(r"\bmodels\.(?:Model|CharField|IntegerField|FloatField|DecimalField|"
                      r"ForeignKey|SmallIntegerField)\b|\bColumn\(\s*(?:Integer|String|Float)"),
    ".rb": re.compile(r"\bcreate_table\b|\bt\.(?:integer|string|decimal|float)\b"),
    ".ts": re.compile(r"\bpgTable\b|@Entity\b|\bDataTypes\.", re.I),
    ".js": re.compile(r"\bpgTable\b|\bDataTypes\.|\bSequelize\b|\bModel\.init\b"),
    ".go": re.compile(r"\bgorm:\""),
    ".java": re.compile(r"@Entity\b"),
    ".kt": re.compile(r"@Entity\b"),
    ".cs": re.compile(r"\[Table\(|\bDbSet<"),
    ".rs": re.compile(r"#\[(?:derive\(.*?(?:sqlx|diesel)|table_name)"),
}


def iter_files(paths, exceptions=()):
    """Yield the schema files that will actually be read."""
    exc = [e.rstrip("/") for e in exceptions]
    for p in paths:
        p = Path(p)
        if p.is_file() and p.suffix in TARGETS:
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.suffix not in TARGETS:
                    continue
                if set(f.parts) & SKIP_DIRS:
                    continue
                s = str(f)
                if any(e in s for e in exc):
                    continue
                yield f


def find_unsupported(paths) -> dict:
    """Schema files in stacks we cannot parse. Reported, never silently skipped."""
    hits: dict = {}
    for p in paths:
        root = Path(p)
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if f.suffix not in UNSUPPORTED_HINTS:
                continue
            if set(f.parts) & SKIP_DIRS:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if UNSUPPORTED_HINTS[f.suffix].search(text):
                hits.setdefault(f.suffix, []).append(str(f))
    return hits
