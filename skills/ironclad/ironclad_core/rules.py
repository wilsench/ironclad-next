"""`ironclad rules` — make the rule set readable without reading the source.

A rule nobody can inspect is a rule nobody can trust, and a rule whose severity is
mysterious is one people switch off. Both commands here exist so a user can answer
"what will this do to my repo" *before* `check` prints 200 lines at them:

  rules list             every rule, the severity it has in the active preset, why
  rules explain ID       what it looks for, what it does not, where it is decided

The severity shown is the *effective* one: config layering already decided it, so
this command reads the same resolution `check` does instead of re-deriving it. A
list that disagrees with the run is worse than no list.
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import normalise_severity
from .config import load_config, parse_simple_yaml
from .domains import load_all
from .engine import Registry

# What each rule refuses to decide, in its own words. Kept next to the command
# rather than in the domain so the text a user reads is a single file to review —
# a rule's docstring explains the code, this explains the *consequence*.
LIMITS = {
    "DB-01": "Does not judge whether an enum is the right modelling choice — only that "
             "a status-like column uses one. A non-status enum is not reported.",
    "DB-02": "Only finds magic numbers compared to a status-like field. A number "
             "compared to something else is left alone.",
    "DB-03": "Asks for a FK or CHECK on a status code. It cannot tell whether the "
             "lookup table exists but is joined elsewhere.",
    "DB-04": "Reports text status columns. It does not read the app to see whether "
             "the strings are validated against a fixed list.",
    "DB-05": "Uses an allowlist (is_active, is_deleted, ...). A boolean named for a "
             "non-binary concept outside that list needs an exception entry.",
    "DB-06": "Money as binary float. It does not check the scale of a decimal — "
             "numeric(18,6) and numeric(18,2) both pass.",
    "DB-07": "Timestamps without timezone. Laravel's created_at/updated_at are "
             "exempt because the framework writes them.",
    "DB-08": "Project-wide. One concept stored two ways. It cannot know two different "
             "column names mean the same concept.",
    "API-01": "Path style mixed within one router. It has no opinion on which style; "
              "a project that is consistently camelCase passes.",
    "API-02": "Error payload under a 2xx. It does not validate the payload shape.",
    "API-07": "The same method+path declared twice. Mount prefixes are accounted for; "
              "a duplicate created by a middleware rewrite is not visible.",
    "SEC-01": "Credential in a file git could ship. Whether the value is still live is "
              "not knowable from here — rotation is a human decision.",
    "SEC-02": "Credential literal in source. It will not see one assembled at runtime "
              "from pieces.",
    "SEC-03": "`.env` keys missing from `.env.example`. Not a leak; a documentation "
              "drift that breaks the next clone.",
    "ARCH-01": "Import cycles among project files. It does not follow packages, and it "
               "skips type-only imports because the compiler erases them.",
    "ARCH-02": "Relative import with no target file. A bundler alias configured outside "
               "tsconfig/jsconfig is left alone rather than guessed.",
}

DOMAIN_ORDER = ("database", "api", "security", "architecture", "testing")


def _registry() -> Registry:
    return load_all()


def _effective(preset_dir: Path, preset: str | None, config: str | None, targets):
    cfg, source = load_config(preset, config, targets, preset_dir=preset_dir)
    return cfg, source


def list_rules(preset_dir: Path, args) -> int:
    here = args.paths[0] if args.paths else "."
    cfg, source = _effective(preset_dir, args.preset, args.config, [here])
    if cfg is None:
        return 2
    reg = _registry()

    rules = []
    for rule in (*reg.file_rules, *reg.project_rules):
        rid = rule.meta.id
        configured = cfg.get("rules", {}).get(rid)
        sev = normalise_severity(configured if configured is not None
                                 else rule.meta.default_severity)
        rules.append((rule.meta.domain, rid, sev, rule.meta.title,
                      rule.meta.scope, configured is not None))

    rules.sort(key=lambda r: (DOMAIN_ORDER.index(r[0]) if r[0] in DOMAIN_ORDER else 99, r[1]))
    width = max(len(r[1]) for r in rules) if rules else 4
    title_w = max(len(r[3]) for r in rules) if rules else 10

    print(f"preset: {cfg.get('name', 'balanced')} ({source})")
    if args.domain:
        rules = [r for r in rules if r[0] == args.domain]
    current = None
    for domain, rid, sev, title, scope, explicit in rules:
        if domain != current:
            print(f"\n{domain}")
            current = domain
        marker = "" if explicit else "  (default)"
        sc = " project" if scope == "project" else ""
        print(f"  {rid:<{width}}  {sev:<5}  {title:<{title_w}}{sc}{marker}")

    off = [r[1] for r in rules if r[2] == "off"]
    if off:
        print(f"\n  off in this preset: {', '.join(off)}")
    print(f"\n{len(rules)} rule(s). `ironclad rules explain <ID>` for what each one "
          f"refuses to decide.")
    return 0


def explain_rule(preset_dir: Path, rid: str, args) -> int:
    reg = _registry()
    found = None
    for rule in (*reg.file_rules, *reg.project_rules):
        if rule.meta.id.lower() == rid.lower():
            found = rule
            break
    if found is None:
        known = ", ".join(sorted(r.meta.id for r in (*reg.file_rules, *reg.project_rules)))
        print(f"ironclad: no rule {rid!r}. Known: {known}", file=sys.stderr)
        return 2

    cfg, source = _effective(preset_dir, args.preset, args.config,
                             [args.paths[0] if args.paths else "."])
    if cfg is None:
        return 2
    configured = cfg.get("rules", {}).get(found.meta.id)
    sev = normalise_severity(configured if configured is not None
                             else found.meta.default_severity)

    m = found.meta
    print(f"{m.id}  {m.title}")
    print(f"  domain  : {m.domain}")
    print(f"  scope   : {m.scope}")
    print(f"  severity: {sev} in {cfg.get('name','balanced')}"
          f"{' (set by your config)' if configured is not None else ' (rule default)'}")
    print(f"  reads   : {', '.join(getattr(found, 'extensions', ()) or ('-',))}")
    limit = LIMITS.get(m.id)
    if limit:
        print("\n  What it will not decide:")
        for line in _wrap(limit, 74):
            print(f"    {line}")
    print("\n  Where it is decided:")
    print(f"    skills/ironclad/ironclad_core/domains/{m.domain}.py")
    print("\n  Every other preset's severity for this rule:")
    for p in sorted(preset_dir.glob("*.yml")):
        data = parse_simple_yaml(p.read_text())
        v = (data.get("rules") or {}).get(m.id, "(default)")
        print(f"    {p.stem:<16} {normalise_severity(v) if v != '(default)' else v}")
    print("\n  Turn it down without turning it off:")
    print(f"    in .agent/standards.yml →  rules:\n      {m.id}: warn")
    return 0


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def rules_main(argv=None, preset_dir: Path | None = None) -> int:
    """Entry point for `check_schema.py rules ...`.

    Lives here as well as in `cli.py` so the checker shim has one predictable
    import: `ironclad_core.rules.rules_main`. The argparse lives in `cli.py`
    because that is where every other parser is; this only forwards.
    """
    from .cli import rules_main as _impl
    return _impl(argv, preset_dir=preset_dir)
