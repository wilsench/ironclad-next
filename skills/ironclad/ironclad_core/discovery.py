"""Which files to look at, and which ones we cannot read.

Two responsibilities that must stay together, because the whole honesty policy
is the link between them: `iter_files` returns what will be scanned, and
`find_unsupported` returns what is unambiguously schema but in a stack this
checker cannot parse. If only the first existed, a repo full of Django models
would report "0 findings" and look clean.

Neither list is hard-coded here. A domain declares what it can read
(`extensions`) and what it knows it cannot (`unreadable`), and the engine unions
those declarations. When the extension list lived in this module, adding a
domain meant editing the core — the one thing the architecture says must not
happen.
"""

from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".next",
             "storage", "__pycache__", ".venv", "venv", ".terraform", "coverage"}

# Stacks whose files are schema we cannot parse yet. Kept here rather than in the
# database domain because these are all schema-ish file types, and the warning is
# about the repo as a whole ("half of this was not looked at"), not about a rule.
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


def iter_files(paths, exceptions=(), extensions=None):
    """Yield the files that will actually be read.

    `extensions` is the union of what the loaded domains declared. Passing None
    keeps the historical database-only behaviour, so a caller that has not been
    taught about domains still checks what it always checked.
    """
    if extensions is None:
        extensions = (".sql", ".php", ".prisma")
    wanted = {e if e.startswith(".") else f".{e}" for e in extensions}
    exc = [e.rstrip("/") for e in exceptions]
    for p in paths:
        p = Path(p)
        if p.is_file() and p.suffix in wanted:
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.suffix not in wanted:
                    continue
                if set(f.parts) & SKIP_DIRS:
                    continue
                if _is_nested_dependency(p, f):
                    continue
                s = str(f)
                if any(e in s for e in exc):
                    continue
                yield f


def _is_nested_dependency(root: Path, candidate: Path) -> bool:
    """True when the file sits inside *another* project's dependency tree.

    A repo that vendors a PHP package should not be judged by that package's
    coding style. `set(parts) & SKIP_DIRS` already catches this for the current
    path, but `rglob` hands back absolute parts, so it depends on where the repo
    lives — `/home/vendor-app/` would silently skip everything.
    """
    try:
        rel = candidate.relative_to(root)
    except ValueError:
        return False
    return bool(set(rel.parts[:-1]) & SKIP_DIRS)


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
            if set(f.parts) & SKIP_DIRS or _is_nested_dependency(root, f):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if UNSUPPORTED_HINTS[f.suffix].search(text):
                hits.setdefault(f.suffix, []).append(str(f))
    return hits
