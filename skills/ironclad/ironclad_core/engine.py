"""The engine: run every registered rule over every file, then aggregate.

It knows about rules, files, and results. It does not know what a status column
is. That line is the whole point of Phase 1 — the database domain is the first
client of this interface, not a special case inside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import Finding, RuleMeta, is_silent
from .discovery import find_unsupported, iter_files
from .report import Result


@dataclass
class FileContext:
    """The only way a rule touches a file.

    A rule gets text and a path, never an open file handle, so it can be tested
    with a string literal. Parsers are attached by the caller as the domains
    that need them arrive; `parser()` returning None is normal and every rule
    must cope with it.
    """
    path: Path
    text: str
    language: str
    _parsers: dict = field(default_factory=dict)

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()

    def parser(self, name: str):
        return self._parsers.get(name)


class Rule:
    """Base class. Subclasses set `meta` and implement `check`.

    `applies` exists so "is this file relevant" is separate from "is this file
    wrong". Without it, every rule re-implements the same extension test, and a
    project-scoped rule has no place to say it should run once.
    """
    meta: RuleMeta
    extensions: tuple[str, ...] = ()

    def applies(self, ctx: FileContext) -> bool:
        return not self.extensions or ctx.path.suffix in self.extensions

    def check(self, ctx: FileContext, cfg: dict) -> list[Finding]:
        raise NotImplementedError


class ProjectRule:
    """A rule that judges the project, not a file. Runs once, after all files."""
    meta: RuleMeta

    def check(self, contexts: list[FileContext], cfg: dict) -> list[Finding]:
        raise NotImplementedError


class Registry:
    def __init__(self) -> None:
        self.file_rules: list[Rule] = []
        self.project_rules: list[ProjectRule] = []

    def add(self, rule) -> None:
        if isinstance(rule, ProjectRule) or rule.meta.scope == "project":
            self.project_rules.append(rule)
        else:
            self.file_rules.append(rule)

    def rule_ids(self) -> list[str]:
        return [r.meta.id for r in (*self.file_rules, *self.project_rules)]


def _language_of(path: Path) -> str:
    return {".sql": "sql", ".php": "php", ".prisma": "prisma"}.get(path.suffix, "unknown")


def _severity_of(rule_id: str, cfg: dict, default: str) -> str:
    return cfg.get("rules", {}).get(rule_id, default)


def run(registry: Registry, cfg: dict, targets, source: str = "") -> Result:
    """Execute every applicable rule and collect the result."""
    files = list(iter_files(targets, cfg.get("exceptions") or ()))
    result = Result(files_checked=len(files),
                    preset=cfg.get("name", "balanced"),
                    source=source or "builtin:balanced",
                    sources=cfg.get("sources") or [source or "builtin:balanced"])

    contexts = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            # An unreadable file is a finding, not a silent skip: the run must
            # not look clean because a permission bit was wrong.
            result.findings.append(Finding(
                rule="IO", severity="error", file=str(path),
                message=f"unreadable: {exc}"))
            continue
        contexts.append(FileContext(path=path, text=text, language=_language_of(path)))

    for ctx in contexts:
        file_findings = []
        for rule in registry.file_rules:
            if not rule.applies(ctx):
                continue
            sev = _severity_of(rule.meta.id, cfg, rule.meta.default_severity)
            if is_silent(sev):
                continue
            for finding in rule.check(ctx, cfg):
                # The engine owns severity, not the rule: a repo's config must be
                # able to demote a rule without the rule agreeing.
                file_findings.append(Finding(
                    rule=finding.rule,
                    severity=sev,
                    file=finding.file,
                    position=finding.position,
                    message=finding.message,
                    domain=finding.domain,
                ))
        # Reading order, not rule order. 0.10.2 checked every rule per line, so
        # its output follows the file; iterating per rule instead would print all
        # the DB-01s, then all the DB-02s, which is harder to act on and would
        # change the output of every existing CI log for no benefit.
        rank = {rid: i for i, rid in enumerate(registry.rule_ids())}
        file_findings.sort(key=lambda f: (f.position.line, rank.get(f.rule, 999)))
        result.findings.extend(file_findings)

    for rule in registry.project_rules:
        sev = _severity_of(rule.meta.id, cfg, rule.meta.default_severity)
        if is_silent(sev):
            continue
        for finding in rule.check(contexts, cfg):
            result.findings.append(Finding(
                rule=finding.rule,
                severity=sev,
                file=finding.file,
                position=finding.position,
                message=finding.message,
                domain=finding.domain,
            ))

    return result


def coverage_warning(result: Result, targets) -> list[str]:
    """The lines printed when nothing could be read. Kept here, not in the CLI,
    so every front-end (bash wrapper, npx shim, CI) says the same thing."""
    unsupported = find_unsupported(targets)
    if not unsupported:
        return []
    exts = ", ".join(sorted(unsupported))
    lines = ["", f"This repo does have schema files this checker cannot read: {exts}.",
             "Nothing was checked. Do not treat this as a pass."]
    for ext, paths in sorted(unsupported.items()):
        more = f" (+{len(paths)-1} more)" if len(paths) > 1 else ""
        lines.append(f"  {ext}: {paths[0]}{more}")
    lines += ["", "Until support exists, enforce the same rules by hand or with your",
              "framework's own migrations review — see",
              "https://wilsench.my.id/ironclad/troubleshooting/"]
    return lines
