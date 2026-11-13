"""`ironclad doctor` — one command for "why did this not work?".

Every failure this tool has produced in its own history was a silent one: a preset
that was read but not applied, an engine that was missing so the checker exited 3
without anyone noticing, a `.env` that was never scanned because its suffix is
empty. Each of those took longer to diagnose than to fix.

So `doctor` answers, in order, the questions a person actually asks:

  1. Is the install complete, and which version is it?
  2. What is this repo's policy, and does it agree with what will run?
  3. What files will be read, and what *cannot* be read?
  4. Which rules will fire, and which are off — and why?

It never writes. It never fixes. A diagnostic that changes state cannot be run
when you are trying to find out what changed.

Exit codes are the same contract as `check`, plus one addition:

  0  everything needed is present and the repo is understandable
  1  the install is fine but this repo cannot be fully checked (nothing readable,
     or a schema stack that is unreadable)
  3  the install itself is broken — the engine is missing or the payload is short
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import normalise_severity
from .config import BUILTIN_PRESET, layering_report, load_config, parse_simple_yaml
from .discovery import find_unsupported, iter_files
from .domains import load_all
from .engine import SCHEMA_DOMAINS

OK = "  ok    "
WARN = "  warn  "
BAD = "  FAIL  "


def _hr(title: str) -> None:
    print(f"\n{title}")


def doctor(preset_dir: Path, paths, preset: str | None, config: str | None,
           registry=None) -> int:
    reg = registry or load_all()
    problems: list[str] = []
    failures = 0

    _hr("install")
    print(f"  python  {sys.version.split()[0]}")
    print(f"  assets  {preset_dir}")
    if not preset_dir.is_dir():
        print(f"{BAD}preset directory is missing ({preset_dir})")
        failures += 1
    else:
        n = len(list(preset_dir.glob("*.yml")))
        print(f"{OK}{n} preset(s): {', '.join(sorted(p.stem for p in preset_dir.glob('*.yml')))}")
        if n == 0:
            failures += 1
            problems.append("no presets shipped — the install is incomplete")

    _hr("engine")
    print(f"{OK}{len(reg.file_rules)} file rule(s), {len(reg.project_rules)} project rule(s)")
    by_domain: dict[str, int] = {}
    for rule in (*reg.file_rules, *reg.project_rules):
        by_domain[rule.meta.domain] = by_domain.get(rule.meta.domain, 0) + 1
    for domain, count in sorted(by_domain.items()):
        print(f"        {domain:<14} {count} rule(s)")
    if not reg.file_rules and not reg.project_rules:
        print(f"{BAD}no rules loaded — nothing can be checked")
        failures += 1
        problems.append("the engine loaded zero rules")

    _hr("policy")
    cfg, source = load_config(preset, config, paths, preset_dir=preset_dir)
    if cfg is None:
        print(f"{BAD}the config could not be read")
        problems.append("config could not be resolved")
        return _finish(problems, 3)

    print(f"  preset  {cfg.get('name', 'balanced')}")
    for line in layering_report(cfg, source):
        print(f"        {line}")

    # The single most useful check in this command: does the file on disk say the
    # same thing the run will use? A preset that was read but not applied is the
    # exact bug that made `check --preset strict` pass what it was asked to block.
    declared = None
    for target in paths:
        candidate = Path(target) / ".agent" / "standards.yml"
        if candidate.is_file():
            declared = parse_simple_yaml(candidate.read_text())
            break
    if declared:
        want = declared.get("name")
        got = cfg.get("name")
        if want and got and want != got:
            print(f"{WARN}.agent/standards.yml says {want!r} but the run uses {got!r}")
            problems.append(f"policy mismatch: file says {want}, run uses {got}")
        else:
            print(f"{OK}.agent/standards.yml is being used")
        n_exc = len(declared.get("exceptions") or [])
        if n_exc:
            print(f"        {n_exc} exception(s) applied")
    else:
        print(f"{WARN}no .agent/standards.yml here — using the built-in preset")
        print("        run `ironclad init` to make this repo's rules explicit")

    _hr("files")
    extensions = reg.extensions() or None
    files = list(iter_files(paths, cfg.get("exceptions") or (), extensions))
    print(f"  readable: {len(files)} file(s)")
    if files:
        by_ext: dict[str, int] = {}
        for f in files:
            by_ext[f.suffix or f.name] = by_ext.get(f.suffix or f.name, 0) + 1
        shown = ", ".join(f"{e}×{n}" for e, n in sorted(by_ext.items(), key=lambda x: -x[1])[:8])
        print(f"        {shown}")
    unsupported = find_unsupported(paths)
    if unsupported:
        print(f"{WARN}schema this tool cannot read:")
        for ext, found in sorted(unsupported.items()):
            more = f" (+{len(found) - 1} more)" if len(found) > 1 else ""
            print(f"        {ext}: {found[0]}{more}")
        problems.append("this repo contains schema in an unsupported stack")
    if not files:
        print(f"{BAD}no file matched any rule's extension")
        problems.append("no files could be read at all")

    _hr("rules that will run")
    for domain in sorted(by_domain):
        rows = []
        for rule in (*reg.file_rules, *reg.project_rules):
            if rule.meta.domain != domain:
                continue
            configured = cfg.get("rules", {}).get(rule.meta.id)
            sev = normalise_severity(configured if configured is not None
                                     else rule.meta.default_severity)
            rows.append(f"{rule.meta.id}={sev}")
        print(f"        {domain:<14} {' '.join(rows)}")
    off = [r.meta.id for r in (*reg.file_rules, *reg.project_rules)
           if normalise_severity(cfg.get("rules", {}).get(r.meta.id,
                                                          r.meta.default_severity)) == "off"]
    if off:
        print(f"{OK}off in this preset: {', '.join(sorted(off))}")
        print("        (turn one on with `rules: {ID: warn}` in .agent/standards.yml)")

    # Can this run promise anything about a schema at all?
    schema_rules = [r for r in reg.file_rules if r.meta.domain in SCHEMA_DOMAINS]
    if schema_rules:
        print(f"\n  schema rules: {len(schema_rules)} — exit 2 means none of them could look")
    else:
        print(f"\n{WARN}no schema-domain rules loaded; exit 2 will never fire")

    code = 3 if failures else (1 if problems else 0)
    return _finish(problems, code, failures)


def _finish(problems: list[str], code: int, failures: int = 0) -> int:
    if not problems:
        print("\nNo problems found.")
        return 0
    print("\nWhat is wrong, in the order that matters:")
    for p in problems:
        print(f"  - {p}")
    if failures:
        print("\nThe install itself is broken. Re-run it:")
        print("  curl -fsSL https://wilsench.my.id/ironclad/install.sh | bash")
    else:
        print("\nThe install is fine; this repo needs attention.")
        print("  `ironclad check .` shows the findings themselves.")
    return code


def doctor_main(argv=None, preset_dir: Path | None = None) -> int:
    import argparse

    if preset_dir is None:
        raise ValueError("preset_dir is required")
    ap = argparse.ArgumentParser(prog="ironclad doctor",
                                 description="why is this not doing what I expected?")
    ap.add_argument("paths", nargs="*", default=[".", ])
    ap.add_argument("--preset")
    ap.add_argument("--config")
    args = ap.parse_args(argv)
    return doctor(preset_dir, args.paths or ["."], args.preset, args.config)
