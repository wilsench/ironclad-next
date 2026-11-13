"""The `check` command, built on the engine.

This is the only place that knows about argparse, stdout, and exit codes. The
engine returns a Result; this turns it into the exact bytes 0.10.2 printed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import is_silent
from .config import BUILTIN_PRESET, load_config, parse_simple_yaml
from .domains import load_all
from .engine import coverage_warning, run
from .report import render_json, render_text


def list_presets(preset_dir: Path) -> int:
    for p in sorted(preset_dir.glob("*.yml")):
        data = parse_simple_yaml(p.read_text())
        n_err = sum(1 for v in data["rules"].values() if v == "error")
        n_warn = sum(1 for v in data["rules"].values() if v == "warn")
        print(f"{p.stem:18} errors={n_err} warns={n_warn}  {data.get('title','')}")
    return 0


def build_parser(preset_dir: Path) -> argparse.ArgumentParser:
    names = ", ".join(sorted(p.stem for p in preset_dir.glob("*.yml")))
    ap = argparse.ArgumentParser(
        description="Company schema convention checker",
        epilog=f"presets: {names}")
    ap.add_argument("paths", nargs="*", default=[".", ])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--preset", help=f"preset name ({names})")
    ap.add_argument("--config", help="explicit config file (overrides --preset)")
    ap.add_argument("--strict", action="store_true",
                    help="escalate every warn to an error (legacy flag, still supported)")
    ap.add_argument("--list-presets", action="store_true")
    return ap


def build_rules_parser(preset_dir: Path) -> argparse.ArgumentParser:
    names = ", ".join(sorted(p.stem for p in preset_dir.glob("*.yml")))
    ap = argparse.ArgumentParser(prog="ironclad rules",
                                 description="what the rules are, and what they refuse to decide")
    ap.add_argument("action", nargs="?", default="list", choices=("list", "explain"))
    ap.add_argument("rule_id", nargs="?")
    ap.add_argument("--preset", help=f"preset name ({names})")
    ap.add_argument("--config", help="explicit config file")
    ap.add_argument("--domain", help="only this domain")
    ap.add_argument("paths", nargs="*", default=[".", ])
    return ap


def rules_main(argv=None, preset_dir: Path | None = None) -> int:
    """`ironclad rules list` / `ironclad rules explain DB-01`."""
    from .rules import explain_rule, list_rules

    if preset_dir is None:
        raise ValueError("preset_dir is required")
    args = build_rules_parser(preset_dir).parse_args(argv)
    if args.action == "explain":
        if not args.rule_id:
            print("ironclad: explain needs a rule id, e.g. `ironclad rules explain DB-01`",
                  file=sys.stderr)
            return 2
        return explain_rule(preset_dir, args.rule_id, args)
    return list_rules(preset_dir, args)


def main(argv=None, preset_dir: Path | None = None) -> int:
    if preset_dir is None:
        raise ValueError("preset_dir is required: the entry point owns the search path")

    args = build_parser(preset_dir).parse_args(argv)

    if args.list_presets:
        return list_presets(preset_dir)

    targets = args.paths or ["."]
    cfg, source = load_config(args.preset, args.config, targets, preset_dir=preset_dir)
    if cfg is None:
        return 2

    registry = load_all()
    result = run(registry, cfg, targets, source=source or "builtin:balanced")

    if result.files_checked == 0:
        # Name what the loaded domains actually read, not a hard-coded list. The
        # message said ".sql/.php/.prisma" while the API domain was also reading
        # .js/.ts, which told the user their JS repo had nothing to check.
        exts = ", ".join(sorted(registry.extensions()))
        print(f"no files any rule can read found (looked for: {exts})", file=sys.stderr)
        for line in coverage_warning(result, targets):
            print(line, file=sys.stderr)
        return 2

    # The legacy --strict flag escalates after the fact, exactly as before: it
    # overrides whatever the preset said, including `off`.
    if args.strict:
        from dataclasses import replace
        result.findings = [replace(f, severity="error") for f in result.findings]

    print(render_json(result) if args.json else render_text(result))
    return result.exit_code


# Re-exported for callers that only need the built-in defaults.
DEFAULT_CONFIG = BUILTIN_PRESET

__all__ = ["main", "build_parser", "list_presets", "rules_main",
           "build_rules_parser", "DEFAULT_CONFIG"]
