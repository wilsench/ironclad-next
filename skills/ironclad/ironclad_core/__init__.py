"""The result model every domain shares.

Before Phase 1 a finding was an anonymous dict built in eleven places, so no
reporter, test, or new domain could rely on its keys. `Finding` fixes the shape
once. It serialises back to exactly the old dict (see `to_dict`), because the
JSON output is a contract with other people's CI — additive keys only.

Fields deliberately absent:
  - `fingerprint` — needed for stable baselines, but nothing consumes it yet and
    a hash computed before the span rule is settled would have to change.
  - `remediation` — same reason.
Both arrive with the domain that first needs them, not speculatively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Severities are strings on purpose: presets are YAML edited by hand, and users
# write `off` / `ignore` / `none` interchangeably. Normalising happens once here.
SEVERITIES = ("error", "warn", "info", "off")
_SILENT = ("off", "ignore", "none", "disabled", "false")


def normalise_severity(value: Any, default: str = "warn") -> str:
    """Map whatever a config file said onto one of SEVERITIES."""
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in _SILENT:
        return "off"
    if s in ("error", "err", "block", "blocking", "fail"):
        return "error"
    if s in ("warn", "warning"):
        return "warn"
    if s in ("info", "note", "hint"):
        return "info"
    return default


def is_silent(value: Any) -> bool:
    return normalise_severity(value, default="warn") == "off"


@dataclass(frozen=True)
class Position:
    """Where a finding sits. A line is always known; a column is not (yet).

    The column exists now rather than later because every parser-based domain —
    API, security, architecture — will have it, and adding a field to a frozen
    dataclass later means touching every construction site.
    """
    line: int = 1
    column: int | None = None


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    message: str
    file: str
    position: Position = field(default_factory=Position)
    domain: str = "database"

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", normalise_severity(self.severity))

    @property
    def blocks(self) -> bool:
        """Does this finding fail the build?"""
        return self.severity == "error"

    def to_dict(self) -> dict[str, Any]:
        """The exact shape the JSON output has always had.

        Key names are `msg` and `line`, not `message` and `position`, because
        someone's CI may read this. New keys may be added; old ones may not go.
        """
        return {
            "rule": self.rule,
            "severity": self.severity,
            "line": self.position.line,
            "msg": self.message,
            "file": self.file,
        }


@dataclass
class RuleMeta:
    """Everything about a rule that is not its implementation."""
    id: str
    domain: str
    title: str
    default_severity: str = "warn"
    scope: str = "file"        # "file" or "project"
    deprecated: bool = False
