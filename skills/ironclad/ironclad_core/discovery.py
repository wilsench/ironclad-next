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
    # Anchored on real declaration shapes, not on the word. A test file that
    # *mentions* `models.Model` inside a fixture string is not a Django model —
    # this tool's own test suite was reported as an unreadable schema stack
    # because of exactly that.
    ".py": re.compile(r"^\s*class\s+\w+\s*\(\s*(?:\w+\.)?Model\s*\)\s*:|"
                      r"^\s*\w+\s*=\s*(?:models|db)\.\w+Field\s*\(", re.M),
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
    # A dotfile has an empty suffix: `Path(".env").suffix == ""`, so it can never
    # match `.env` in an extension set. Every claim is also tried as a whole file
    # name. Dotted families count too: claiming ".env" must also claim
    # ".env.example", or the one file a repo is supposed to ship is invisible.
    names = set(extensions)
    exc = [e.rstrip("/") for e in exceptions]
    for p in paths:
        p = Path(p)
        if p.is_file() and (p.suffix in wanted or matches(p, names)):
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.suffix not in wanted and not matches(f, names):
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


def matches(path: Path, extensions) -> bool:
    """Does this domain claim this file?

    Three ways to be claimed: the suffix, the exact name, or membership in a
    dotted name family. The third is what makes ".env" cover ".env.example" and
    ".env.production" — `Path(".env.example").suffix` is ".example", so the
    suffix test alone silently lost the one file a repo is meant to commit.
    """
    exts = tuple(extensions or ())
    if path.suffix in exts or path.name in exts:
        return True
    return any(path.name.startswith(f"{e}.") for e in exts if e.startswith("."))


# Generated and vendored assets are not source. A docs bundle that *describes*
# Sequelize models matched `DataTypes.` and made a Next.js repo claim it was full
# of unreadable schema — the same class of bug as scanning the tool's own
# `.agent/standards.yml`: text about a thing is not the thing.
_ASSET_PATH = re.compile(r"(?:^|/)(?:public|static|assets|dist|build|out|"
                         r"_next|coverage|vendor|node_modules)/", re.I)
_ASSET_NAME = re.compile(r"\.(?:min|bundle|chunk)\.[cm]?js$|\.map$", re.I)


_PY_TRIPLE = re.compile(r'"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\'')


def _strip_strings(text: str) -> str:
    """Remove triple-quoted blocks so a fixture that quotes code is not code.

    Deliberately not a parser: this only has to be good enough that a docstring
    containing `class A(models.Model)` does not make a repo look like Django. It
    preserves newlines so line numbers stay meaningful.
    """
    return _PY_TRIPLE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


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
                rel = str(f.relative_to(root))
            except ValueError:
                rel = str(f)
            if _ASSET_PATH.search(rel.replace("\\", "/")) or _ASSET_NAME.search(f.name):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # A declaration inside a docstring or a fixture string is text about
            # code, not code. Without this, this tool's own test suite — which
            # contains `class Fake(models.Model)` as a fixture — was reported as
            # an unreadable Django schema.
            probe = _strip_strings(text) if f.suffix == ".py" else text
            if UNSUPPORTED_HINTS[f.suffix].search(probe):
                hits.setdefault(f.suffix, []).append(str(f))
    return hits
