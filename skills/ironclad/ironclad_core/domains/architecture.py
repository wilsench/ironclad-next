"""The architecture domain: the shape of the project, read from its imports.

Two rules ship. Both answer a question with a witness, not a preference:

  ARCH-01  two files import each other, directly or through a chain
  ARCH-02  an import points at a file that is not there

Everything else the roadmap proposed for this domain was measured and rejected.
The measurement is at the bottom of this file, because "we decided not to" is the
most valuable thing a rule set can record: it is the difference between a tool
that has an opinion and a tool that has a reason.

Why imports and not "layers"
----------------------------
`ARCH-02 controller must not touch a model` was the roadmap's proposal. On the one
Laravel repo on this machine, 6 of 7 controllers touch `App\\Models\\*` and query
it with `::where(...)`. That is what Laravel's own documentation teaches. The rule
would have fired on 86% of correct, working code — the exact shape of finding
that gets a tool switched off in its first week. A layer rule is only honest when
the project declares its own layers; that needs a config surface nobody has asked
for yet, so it waits.

Why a cycle is a fact
---------------------
A cycle is true regardless of how you name your layers: if A imports B and B
imports A and neither is a type-only edge, the code cannot be executed bottom-up,
and one of the two is holding a partially initialised module. It is worth a
report in every style. It is still only a `warn` by default, because a two-file
cycle between two constants files is annoying, not broken, and because this
domain's job is to point, not to gate.

Cycles are found per **component**, not per edge. Reporting every edge inside a
200-file knot produces 200 findings nobody can act on; reporting the knot once,
with its members, is one decision to make.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .. import Finding, Position, RuleMeta
from ..discovery import matches
from ..engine import FileContext, ProjectRule, Registry, Rule

DOMAIN = "architecture"

SOURCE_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts",
               ".vue", ".svelte", ".py", ".php")

# Relative specifiers only. A bare specifier is a package name, resolved by
# node_modules or a package manager — following those means walking outside the
# project, and a cycle through a dependency is that dependency's problem.
JS_IMPORT = re.compile(
    r"""(?:\bimport\s+(?:[\w*{}\s,$]+\s+from\s+)?     # import x from "y" / import "y"
         |\bexport\s+[\w*{}\s,$]+\s+from\s+           # export { x } from "y"
         |\brequire\s*\(\s*                            # require("y")
         |\bimport\s*\(\s*)                            # import("y") — dynamic
        ['"](?P<spec>[^'"\n]+)['"]""", re.X)

PHP_USE = re.compile(r"^\s*use\s+(?P<spec>[A-Za-z_][\w\\]*)\s*(?:as\s+\w+\s*)?;", re.M)

PY_IMPORT = re.compile(r"^\s*(?:from\s+(?P<from>[.\w]+)\s+import\b|import\s+(?P<plain>[.\w]+))", re.M)

# Import forms that carry no runtime edge. A type-only import is erased by the
# compiler, so `a.ts` importing a type from `b.ts` which imports a value from
# `a.ts` is not the same knot — reporting it would be wrong in TypeScript and
# merely pedantic in the rest.
TYPE_ONLY = re.compile(r"\bimport\s+type\b|\bexport\s+type\b")

RESOLVE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts",
                ".json", ".vue", ".svelte", ".py", ".php")
# TypeScript with NodeNext writes `./x.js` for a file called `x.ts`. Resolving the
# literal suffix first makes every one of those look broken: on one repo here that
# produced 15 "broken imports" out of 1927, all of them correct TypeScript.
TS_OUTPUT_EXTS = (".js", ".mjs", ".cjs")


def _resolve(spec: str, base: Path, root: Path) -> Path | None:
    """The file a relative specifier points at, or None if there is none.

    Returns the *literal* target when it exists, otherwise the first candidate
    that does. `TS_OUTPUT_EXTS` is handled before the plain extension list
    because `x.js` next to `x.ts` is ambiguous and the TS file is the source.
    """
    target = (base / spec).resolve()

    def usable(p: Path) -> bool:
        # Never leave the project: `../../etc/passwd` is not an architecture
        # question, and reading outside the target is not this tool's business.
        try:
            p.relative_to(root.resolve())
        except ValueError:
            return False
        return p.is_file()

    if usable(target):
        return target
    if target.suffix in TS_OUTPUT_EXTS:
        stem = target.with_suffix("")
        for ext in (".ts", ".tsx", ".mts", ".cts"):
            candidate = Path(str(stem) + ext)
            if usable(candidate):
                return candidate
    for ext in RESOLVE_EXTS:
        candidate = Path(str(target) + ext)
        if usable(candidate):
            return candidate
    for ext in RESOLVE_EXTS:
        candidate = target / f"index{ext}"
        if usable(candidate):
            return candidate
    return None


def _edges_of(ctx: FileContext, root: Path) -> list[tuple[str, int]]:
    """(target, line) for every relative import in this file."""
    path = ctx.path.resolve()
    base = path.parent
    found: list[tuple[str, int]] = []
    lines = ctx.lines
    suffix = path.suffix

    if suffix in (".py",):
        for lineno, line in enumerate(lines, 1):
            for m in PY_IMPORT.finditer(line):
                spec = m.group("from") or m.group("plain") or ""
                if not spec.startswith("."):
                    continue
                # Relative python imports count dots, not slashes: `..` is one
                # level up from the package, not one level up from the file.
                depth = len(spec) - len(spec.lstrip("."))
                module = spec[depth:].replace(".", "/")
                base_dir = base
                for _ in range(max(depth - 1, 0)):
                    base_dir = base_dir.parent
                target = _resolve(module or ".", base_dir, root)
                if target:
                    found.append((str(target), lineno))
        return found

    if suffix == ".php":
        # `use App\X\Y;` is an ALIAS, not a load. PHP resolves it lazily through
        # the autoloader, and a class whose file is never touched is never read.
        # Treating it as an edge produced 8 "import cycles" in the Filament
        # resources of one repo here, every one of them the framework's own
        # documented pattern: a Resource lists its Pages, each Page points back at
        # its Resource. That is not a knot, it is a tree drawn twice.
        #
        # Only a class *inheriting* forces a load before itself: `extends`,
        # `implements`, and `use Trait` inside a class body. The last one is what
        # makes brace depth the discriminator — an alias sits at depth 0, a trait
        # usage sits inside the class that uses it.
        aliases: dict[str, str] = {}
        for line in lines:
            m = PHP_USE.match(line)
            if m:
                spec = m.group("spec")
                al = re.search(r"\bas\s+(\w+)", line)
                aliases[al.group(1) if al else spec.split("\\")[-1]] = spec

        def php_target(name: str) -> str | None:
            short = name.split("\\")[0]
            full = aliases.get(name, aliases.get(short, name))
            if not full.startswith("App\\"):
                return None
            rel = full.replace("App\\", "", 1).replace("\\", "/") + ".php"
            for anchor in (root / "app", root / "src", root):
                candidate = anchor / rel
                if candidate.is_file():
                    return str(candidate.resolve())
            return None

        depth = 0
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith(("//", "*", "/*", "#")):
                depth += line.count("{") - line.count("}")
                continue
            body = line.split("//")[0]
            names: list[str] = []
            if depth == 0:
                m = re.match(r"^\s*(?:abstract\s+|final\s+)?class\s+\w+"
                             r"(?:\s+extends\s+([\w\\]+))?", body)
                if m and m.group(1):
                    names.append(m.group(1))
                m = re.search(r"\bimplements\s+([\w\\,\s]+)", body)
                if m and depth == 0:
                    names += [x.strip() for x in m.group(1).split(",") if x.strip()]
            else:
                # Trait usage: `use HasFactory, Notifiable;` inside a class body.
                m = re.match(r"^\s*use\s+([\w\\,\s]+);", body)
                if m:
                    names += [x.strip() for x in m.group(1).split(",") if x.strip()]
            for name in names:
                target = php_target(name)
                if target:
                    found.append((target, lineno))
            depth += body.count("{") - body.count("}")
            depth = max(depth, 0)
        return found

    for lineno, line in enumerate(lines, 1):
        if TYPE_ONLY.search(line):
            continue
        for m in JS_IMPORT.finditer(line):
            spec = m.group("spec")
            if not spec.startswith("."):
                continue
            target = _resolve(spec, base, root)
            if target:
                found.append((str(target), lineno))
            else:
                # Remember the miss: that is ARCH-02's evidence, and it is why
                # this function returns what it could not resolve as well.
                found.append((f"!\x00{spec}", lineno))
    return found


def _project_root(paths, ctx_paths) -> Path:
    """The directory the graph is built from.

    A caller may pass several targets; the graph needs one anchor for relative
    containment. The first target wins, which matches what `check .` means.
    """
    for p in paths or ():
        p = Path(p)
        return p.resolve() if p.is_dir() else p.resolve().parent
    if ctx_paths:
        return Path(ctx_paths[0]).resolve().parent
    return Path(".").resolve()


class Arch01ImportCycle(ProjectRule):
    """Two or more files that import each other.

    Reported once per strongly-connected component, at the alphabetically first
    member, listing the others. Tarjan's algorithm, iterative: a 5000-file repo
    recursed deeply enough to raise RecursionError, and a checker that crashes on
    a big repo is worse than one that misses a cycle.
    """
    meta = RuleMeta(id="ARCH-01", domain=DOMAIN,
                    title="files import each other in a cycle",
                    default_severity="warn", scope="project")
    extensions = SOURCE_EXTS

    def applies_to(self, ctx: FileContext) -> bool:
        return matches(ctx.path, self.extensions)

    def check(self, contexts: list[FileContext], cfg: dict) -> list[Finding]:
        root = _project_root(cfg.get("_targets") or (), [str(c.path) for c in contexts])
        graph: dict[str, dict[str, int]] = {}
        line_of: dict[tuple[str, str], int] = {}
        for ctx in contexts:
            if not self.applies_to(ctx):
                continue
            src = str(ctx.path.resolve())
            graph.setdefault(src, {})
            for target, lineno in _edges_of(ctx, root):
                if target.startswith("!\x00"):
                    continue
                graph[src][target] = graph[src].get(target, 0) + 1
                line_of.setdefault((src, target), lineno)

        components = _strongly_connected(graph)
        findings = []
        for comp in components:
            members = sorted(comp)
            head = members[0]
            # The line that closes the loop: the first import from the head to
            # anything else in the component. Without it the finding points at
            # line 1 and the reader has to find the knot themselves.
            anchor_line, anchor_target = 1, None
            for target in members[1:]:
                if (head, target) in line_of:
                    anchor_line, anchor_target = line_of[(head, target)], target
                    break
            if anchor_target is None:
                for src in members:
                    for target in members:
                        if src != target and (src, target) in line_of:
                            anchor_line, anchor_target = line_of[(src, target)], target
                            break
                    if anchor_target:
                        break
            names = ", ".join(_rel(m, root) for m in members)
            findings.append(Finding(
                rule=self.meta.id,
                severity=self.meta.default_severity,
                file=str(head),
                position=Position(line=anchor_line),
                message=(f"{len(members)} files form an import cycle: {names}. "
                         f"Nothing in the group can be loaded first — move the shared "
                         f"piece into a module that imports nothing from the group."),
                domain=DOMAIN))
        return findings


class Arch02UnresolvedImport(ProjectRule):
    """An import that points at a file which is not there.

    This is the one architectural finding that is unambiguously a defect: the
    module either fails at load or at build, or a resolution mechanism the
    checker cannot see (a bundler alias) makes it work. The second case is why
    the severity is `warn` and not `error`, and why aliases are excluded rather
    than guessed at: `@/components/x` resolves through tsconfig `paths`, and
    inventing that map produces findings on correct code.
    """
    meta = RuleMeta(id="ARCH-02", domain=DOMAIN,
                    title="import points at a file that does not exist",
                    default_severity="warn", scope="project")
    extensions = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts")

    def applies_to(self, ctx: FileContext) -> bool:
        return matches(ctx.path, self.extensions)

    def check(self, contexts: list[FileContext], cfg: dict) -> list[Finding]:
        root = _project_root(cfg.get("_targets") or (), [str(c.path) for c in contexts])
        aliases = _alias_prefixes(root)
        findings = []
        for ctx in contexts:
            if not self.applies_to(ctx):
                continue
            for target, lineno in _edges_of(ctx, root):
                if not target.startswith("!\x00"):
                    continue
                spec = target[2:]
                # An alias the project configured is resolved by its bundler.
                # The checker cannot see that map without parsing tsconfig, and
                # a wrong map means findings on working code — so it says
                # nothing instead of guessing.
                if any(spec == a or spec.startswith(a + "/") for a in aliases):
                    continue
                findings.append(Finding(
                    rule=self.meta.id,
                    severity=self.meta.default_severity,
                    file=str(ctx.path.resolve()),
                    position=Position(line=lineno),
                    message=(f"`{spec}` does not resolve to a file. Either the path is "
                             f"wrong or the module was deleted; nothing in this "
                             f"directory satisfies it."),
                    domain=DOMAIN))
        return findings


def _alias_prefixes(root: Path) -> set[str]:
    """Alias prefixes from tsconfig/jsconfig `paths`, best effort.

    Only the prefix before `/*` is kept. `"@/*": ["./src/*"]` means anything
    under `@/` is the bundler's job, which is all this needs to stay quiet.
    """
    out: set[str] = set()
    for name in ("tsconfig.json", "jsconfig.json"):
        for cfg in list(root.glob(name)) + list(root.glob(f"*/{name}")):
            if "node_modules" in cfg.parts:
                continue
            try:
                text = cfg.read_text(encoding="utf-8", errors="replace")
                # tsconfig allows // comments and trailing commas.
                text = re.sub(r"//[^\n]*", "", text)
                text = re.sub(r",\s*([}\]])", r"\1", text)
                data = json.loads(text)
            except (OSError, ValueError):
                continue
            paths = ((data.get("compilerOptions") or {}).get("paths") or {})
            for key in paths:
                out.add(key.split("*")[0].rstrip("/"))
    return {a for a in out if a}


def _rel(path: str, root: Path) -> str:
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return path


def _strongly_connected(graph: dict[str, dict[str, int]]) -> list[list[str]]:
    """Tarjan, iterative. Returns only components with a real cycle.

    A self-import (`a.js` importing `./a`) is a cycle of one, and it is reported:
    it is always a mistake.
    """
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    out: list[list[str]] = []
    counter = 0

    for start in graph:
        if start in index:
            continue
        work = [(start, iter(graph.get(start, ())))]
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(graph.get(child, ()))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    comp.append(member)
                    if member == node:
                        break
                if len(comp) > 1 or (len(comp) == 1 and node in graph.get(node, {})):
                    out.append(comp)
    return out


def register(reg: Registry) -> None:
    reg.add(Arch01ImportCycle())
    reg.add(Arch02UnresolvedImport())


# ---------------------------------------------------------------------------
# Measured, then rejected. Kept because a rule set that only records what it
# shipped cannot be argued with.
#
# ARCH-03 "layer violation: controller imports a model"
#   6 of 7 controllers in the one Laravel repo here import App\Models and call
#   ::where(). That is the documented Laravel idiom. Rejected.
#
# ARCH-04 "unknown top-level directory"
#   Fires on `scripts/`, `docs/`, `public/`, `shared/`, `prisma/` — every repo
#   has a directory the rule's author did not think of. There is no fact here,
#   only a list of names one person expected. Rejected.
#
# ARCH-05 "file too large / too many exports"
#   A threshold nobody agreed on. On the repos measured, the largest files are
#   generated migrations and Prisma clients, which are excluded anyway; what is
#   left is a style number. Rejected — a tool that invents thresholds is a tool
#   that starts arguments instead of ending them.
#
# TEST-01 "test does not mirror the module it tests"
#   Assumes one test file per source file. Silomag has 15 test files covering
#   three workspaces; the mapping is not 1:1 and never was. A rule that reports
#   every source file without a same-named test produces one finding per file —
#   a coverage report, badly reinvented. Deferred.
#
# TEST-02 "coverage threshold missing from config"
#   A project that runs tests on every push and has no coverage gate is not
#   making a mistake, it is making a choice. Rejected as a defect.
#
# TEST-03 "skipped test"
#   Measured on every test file in every repo on this machine: zero `.skip(`,
#   zero `markTestSkipped`, zero `@unittest.skip`. The rule would ship having
#   never fired on real code, and a rule that has never fired is a rule nobody
#   knows works. It stays in this comment rather than in the registry.
# ---------------------------------------------------------------------------
