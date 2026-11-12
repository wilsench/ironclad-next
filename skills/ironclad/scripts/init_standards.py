#!/usr/bin/env python3
"""Bootstrap the company standards policy file into a repo.

Writes two things:

  .agent/standards.md   human-readable policy (rules with IDs)
  .agent/standards.yml  machine-readable severity config the checker reads

The YAML is what makes the guardrails adjustable: pick a preset now, edit the
YAML later, no code change and no re-install.

Usage:
  python3 scripts/init_standards.py              # interactive wizard
  python3 scripts/init_standards.py --preset strict --yes
  python3 scripts/init_standards.py /repo --preset legacy-friendly --with-checker
  python3 scripts/init_standards.py --list-presets
"""

import argparse
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PRESET_DIR = SKILL_DIR / "assets" / "presets"
TEMPLATE = SKILL_DIR / "templates" / "standards.md"
CHECKER = SKILL_DIR / "scripts" / "check_schema.py"
PRESET_SRC = SKILL_DIR / "assets" / "presets"

FALLBACK_PRESETS = ["balanced"]
DEFAULT_PRESET = "balanced"


def available_presets():
    names = sorted(p.stem for p in PRESET_DIR.glob("*.yml"))
    return names or FALLBACK_PRESETS


def preset_title(name):
    f = PRESET_DIR / f"{name}.yml"
    if not f.is_file():
        return ""
    for line in f.read_text().splitlines():
        if line.startswith("title:"):
            return line.split(":", 1)[1].strip()
    return ""


def preset_rules(name):
    """Minimal `rules:` block extraction — same dependency-free approach as the checker."""
    f = PRESET_DIR / f"{name}.yml"
    if not f.is_file():
        return {}
    rules, in_rules = {}, False
    for raw in f.read_text().splitlines():
        line = raw.rstrip()
        if line.startswith("rules:"):
            in_rules = True
            continue
        if in_rules:
            if line and not line.startswith((" ", "\t")):
                break
            if ":" in line:
                k, _, v = line.partition(":")
                rules[k.strip()] = v.split("#")[0].strip()
    return rules


def ask(prompt, default=None, valid=None):
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            answer = input(f"{prompt}{suffix}: ").strip()
        except EOFError:
            return default
        if not answer:
            if default is not None:
                return default
            continue
        if valid and answer not in valid:
            print(f"  choose one of: {', '.join(valid)}")
            continue
        return answer


def wizard(presets):
    print("\nIronclad — engineering standards setup\n")
    print("Pick the guardrail level. This is the default; you can change it later")
    print("by editing .agent/standards.yml — no reinstall, no code change.\n")
    for i, name in enumerate(presets, 1):
        rules = preset_rules(name)
        errs = sum(1 for v in rules.values() if v == "error")
        warns = sum(1 for v in rules.values() if v == "warn")
        tag = "  (default)" if name == DEFAULT_PRESET else ""
        print(f"  {i}) {name:16} {preset_title(name)}{tag}")
        print(f"     {'':16} {errs} rule(s) block, {warns} warn only")
    print()
    choice = ask("Choice", default=str(presets.index(DEFAULT_PRESET) + 1 if DEFAULT_PRESET in presets else 1),
                 valid=[str(i) for i in range(1, len(presets) + 1)])
    return presets[int(choice) - 1]


def main() -> int:
    presets = available_presets()

    ap = argparse.ArgumentParser(description="Bootstrap company standards into a repo")
    ap.add_argument("repo", nargs="?", default=".", help="repo root (default: .)")
    ap.add_argument("--preset", choices=presets, help="guardrail level")
    ap.add_argument("--with-checker", action="store_true",
                    help="also copy check_schema.py into the repo's scripts/")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument("--yes", "-y", action="store_true", help="non-interactive, use the default preset")
    ap.add_argument("--list-presets", action="store_true")
    args = ap.parse_args()

    if args.list_presets:
        for name in presets:
            print(f"{name:18} {preset_title(name)}")
        return 0

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"not a directory: {repo}", file=sys.stderr)
        return 2
    if not TEMPLATE.is_file():
        print(f"template missing: {TEMPLATE}", file=sys.stderr)
        return 2

    preset = args.preset
    if not preset:
        if args.yes or not sys.stdin.isatty():
            preset = DEFAULT_PRESET
            print(f"non-interactive: using preset '{preset}'")
        else:
            preset = wizard(presets)

    agent_dir = repo / ".agent"
    agent_dir.mkdir(exist_ok=True)

    # 1. policy doc
    md_target = agent_dir / "standards.md"
    if md_target.exists() and not args.force:
        print(f"exists, left untouched: {md_target.relative_to(repo)}")
    else:
        shutil.copyfile(TEMPLATE, md_target)
        print(f"wrote {md_target.relative_to(repo)}")

    # 2. machine-readable config
    yml_target = agent_dir / "standards.yml"
    src = PRESET_DIR / f"{preset}.yml"
    if yml_target.exists() and not args.force:
        print(f"exists, left untouched: {yml_target.relative_to(repo)} "
              f"(delete it or pass --force to switch preset to '{preset}')")
    else:
        if src.is_file():
            body = src.read_text()
        else:  # skill installed without presets/ — write the built-in balanced set
            body = (
                "name: balanced\n"
                "rules:\n"
                "  DB-01: error\n  DB-02: error\n  DB-03: warn\n"
                "  DB-04: error\n  DB-05: warn\n  DB-06: warn\n  DB-07: warn\n  DB-08: warn\n"
                "exceptions: []\nboolean_allowlist:\n  - is_active\n  - is_deleted\n"
            )
        yml_target.write_text(body)
        print(f"wrote {yml_target.relative_to(repo)} (preset: {preset})")

    # 3. optional checker copy — preset files travel with it, or `--preset` breaks
    # in the target repo once the skill directory is not on disk. The engine
    # package travels too: check_schema.py is now an entry point over
    # ironclad_core/, and a lone copy would exit 3.
    if args.with_checker:
        scripts = repo / "scripts"
        scripts.mkdir(exist_ok=True)
        copies = [(CHECKER, scripts / "check_schema.py")]
        for yml in sorted(PRESET_SRC.glob("*.yml")):
            copies.append((yml, scripts / "presets" / yml.name))
        for src, dest in copies:
            if dest.exists() and not args.force:
                print(f"exists, left untouched: {dest.relative_to(repo)}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            if dest.suffix == ".py":
                dest.chmod(0o755)
            print(f"wrote {dest.relative_to(repo)}")

        core_src = SKILL_DIR / "ironclad_core"
        core_dest = scripts / "ironclad_core"
        if core_src.is_dir():
            if core_dest.exists():
                shutil.rmtree(core_dest)
            shutil.copytree(core_src, core_dest,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            print(f"wrote {core_dest.relative_to(repo)}/")

    print("\nnext:")
    print("  python3 scripts/check_schema.py . --json     # uses .agent/standards.yml")
    print("  # change the level later — re-run this same command with --preset <name> --force,")
    print("  # or edit the seven rule lines in .agent/standards.yml and commit them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
