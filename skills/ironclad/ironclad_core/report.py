"""Reporters: one for humans, one for machines.

Kept separate from the engine so a third format (SARIF) can be added later
without touching rule execution. Both take the same Result object.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import Finding


@dataclass
class Result:
    findings: list[Finding] = field(default_factory=list)
    files_checked: int = 0
    preset: str = "balanced"
    source: str = "builtin:balanced"
    sources: list[str] = field(default_factory=lambda: ["builtin:balanced"])

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warn"]

    @property
    def exit_code(self) -> int:
        return 1 if self.errors else 0


def render_text(result: Result) -> str:
    out = []
    for f in result.findings:
        tag = "ERROR" if f.severity == "error" else "warn "
        out.append(f"{f.file}:{f.position.line}: [{f.rule}] {tag} {f.message}")
    if result.findings:
        out.append("")
    out.append(f"preset: {result.preset} ({result.source})")
    out.append(f"{result.files_checked} file(s), {len(result.errors)} error(s), "
               f"{len(result.warnings)} warning(s)")
    if result.warnings and not result.errors:
        out.append("warnings do not fail the build; use --strict to escalate")
    return "\n".join(out)


def render_json(result: Result) -> str:
    # Key order and names match 0.10.2 exactly; `sources` is additive.
    return json.dumps({
        "preset": result.preset,
        "source": result.source,
        "sources": result.sources,
        "files": result.files_checked,
        "findings": [f.to_dict() for f in result.findings],
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }, indent=2, ensure_ascii=False)
