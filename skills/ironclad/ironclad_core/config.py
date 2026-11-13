"""Configuration: presets, layering, and severity resolution.

Extracted from check_schema.py so the precedence rule lives in exactly one
place. The wrapper used to compute a preset in shell and pass it as an argument,
which is how `--preset strict` got silently overruled and how a repo using
`coherence` became uncheckable. One resolver, no second opinion.

Precedence, weakest to strongest:

    built-in balanced  <  repo .agent/standards.yml  <  --preset  <  --config

The repo layer is always applied — even when --preset or --config is given —
because `exceptions` and `boolean_allowlist` describe which files to look at,
not how strict to be, and silently dropping them changes what was scanned.
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import normalise_severity

DEFAULT_PRESET = "balanced"

BUILTIN_PRESET = {
    "name": "balanced",
    "rules": {"DB-01": "error", "DB-02": "error", "DB-03": "warn",
              "DB-04": "error", "DB-05": "warn", "DB-06": "warn", "DB-07": "warn"},
    "exceptions": [],
    "boolean_allowlist": ["is_active", "is_deleted", "is_published",
                          "is_verified", "is_terminal", "has_invoice"],
}


def parse_simple_yaml(text: str) -> dict:
    """Parse the YAML subset this project ships.

    Deliberately dependency-free: CI often has no PyYAML, and a checker that
    cannot import its own config is worse than no checker. Supports
    `key: value` under `rules:` and `- item` lists under named keys.
    """
    data: dict = {"rules": {}, "exceptions": [], "boolean_allowlist": []}
    section = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(("name:", "title:", "description:")):
            key, _, val = line.partition(":")
            data[key.strip()] = val.strip()
            section = None
            continue
        if line.startswith("rules:"):
            section = "rules"
            continue
        if line.startswith("exceptions:"):
            section = "exceptions"
            # `exceptions: [a, b]` and `exceptions: []` are legal YAML that the
            # parser used to ignore entirely, silently checking files the repo
            # had excluded. Accept both inline and block forms.
            inline = line.split(":", 1)[1].strip()
            if inline.startswith("[") and inline.endswith("]"):
                body = inline[1:-1].strip()
                if body:
                    data["exceptions"].extend(
                        part.strip().strip("'\"") for part in body.split(","))
            continue
        if line.startswith("boolean_allowlist:"):
            section = "boolean_allowlist"
            continue
        if section == "rules" and ":" in line:
            key, _, val = line.partition(":")
            data["rules"][key.strip()] = val.split("#")[0].strip().lower()
            continue
        if section in ("exceptions", "boolean_allowlist") and line.lstrip().startswith("-"):
            data[section].append(line.lstrip()[1:].strip().strip("'\""))
    return data


def find_repo_config(repo_paths) -> Path | None:
    """The repo's own policy: .agent/standards.yml inside the target.

    Only inside. Searching parents meant that checking `/root/projects/x` picked
    up `/root/.agent/standards.yml` — a policy for a different project, or for the
    machine — and applied it silently. `doctor` surfaced it as "from
    /root/.agent/standards.yml (repo policy)" while also saying there was no
    policy here: two contradictory sentences in one report.

    A caller who genuinely wants a parent policy can pass `--config <path>`; that
    is an explicit act, which is the point.
    """
    for base in (Path(p) for p in (repo_paths or [".", ])):
        base = base.resolve()
        if base.is_file():
            base = base.parent
        cand = base / ".agent" / "standards.yml"
        if cand.is_file():
            return cand
    return None


def _preset_names(preset_dir: Path) -> str:
    return ", ".join(sorted(p.stem for p in preset_dir.glob("*.yml")))


def load_config(preset=None, config_path=None, repo_paths=None,
                preset_dir: Path | None = None):
    """Merge the layers. Returns (config, source_label).

    `source_label` keeps its historical shape — the single strongest layer —
    because consumers may parse it. The full chain is in `config["sources"]`.
    """
    if preset_dir is None:
        raise ValueError("preset_dir is required: the caller owns the search path")

    layers = []
    labels = []

    # 1. The repo's own policy, always.
    repo_cfg = find_repo_config(repo_paths)
    if repo_cfg is not None:
        repo_layer = parse_simple_yaml(repo_cfg.read_text())
        # `name:` alone — what `ironclad preset` writes — resolves to that
        # preset's rules. An overlay, never a replacement: the repo may name a
        # preset *and* keep its own exceptions, and replacing would delete them.
        named = repo_layer.get("name")
        if named and not repo_layer.get("rules") and (preset_dir / f"{named}.yml").is_file():
            resolved = parse_simple_yaml((preset_dir / f"{named}.yml").read_text())
            resolved.update({k: v for k, v in repo_layer.items() if v})
            repo_layer = resolved
        layers.append(repo_layer)
        labels.append(str(repo_cfg))

    # 2. An explicitly requested preset outranks the committed one.
    if preset:
        preset_file = preset_dir / f"{preset}.yml"
        if not preset_file.is_file():
            print(f"unknown preset '{preset}' — available: {_preset_names(preset_dir)}",
                  file=sys.stderr)
            return None, None
        layers.append(parse_simple_yaml(preset_file.read_text()))
        labels.append(f"preset:{preset}")

    # 3. An explicit config file outranks everything.
    if config_path:
        cfg_file = Path(config_path)
        if not cfg_file.is_file():
            print(f"config not found: {cfg_file}", file=sys.stderr)
            return None, None
        layers.append(parse_simple_yaml(cfg_file.read_text()))
        labels.append(str(cfg_file))

    source = labels[-1] if labels else "builtin:balanced"
    sources = labels or ["builtin:balanced"]

    merged = {"name": DEFAULT_PRESET,
              "rules": dict(BUILTIN_PRESET["rules"]),
              "exceptions": [],
              "boolean_allowlist": list(BUILTIN_PRESET["boolean_allowlist"])}
    for layer in layers:
        for rule, sev in (layer.get("rules") or {}).items():
            merged["rules"][rule] = normalise_severity(sev, default="warn")
        if layer.get("exceptions"):
            merged["exceptions"] = layer["exceptions"]
        if layer.get("boolean_allowlist"):
            merged["boolean_allowlist"] = layer["boolean_allowlist"]
        if layer.get("name"):
            merged["name"] = layer["name"]
    merged["sources"] = sources
    return merged, source


def layering_report(cfg: dict, source: str) -> list[str]:
    """Which layers were read, in precedence order, for `doctor` to print.

    Deliberately reads the `sources` list the loader recorded rather than
    recomputing it: a report that re-derives precedence can disagree with what
    actually ran, and the whole point of `doctor` is to say what will run.
    """
    sources = cfg.get("sources") or [source or "builtin:balanced"]
    lines = []
    for i, label in enumerate(sources):
        kind = ("repo policy" if label.endswith((".yml", ".yaml")) and ".agent" in label
                else "preset" if label.startswith("preset:") else
                "config file" if label.endswith((".yml", ".yaml")) else "built-in")
        lines.append(f"{'from' if i == len(sources) - 1 else 'then'} {label}  ({kind})")
    if not lines:
        lines.append("built-in defaults only")
    return lines


def detect_stack(root) -> dict:
    """What this repo is, from files it already has.

    Used by `init` to stop asking a question the repo has answered, and by
    `doctor` to explain why a run saw what it saw. Every signal here is a file a
    framework creates on install — never a guess from a filename pattern.

    Returns {"frameworks": [...], "schema": [...], "tests": [...]}, each list
    sorted. Empty lists are meaningful: "no test runner detected" is the finding.
    """
    from pathlib import Path

    root = Path(root)
    if root.is_file():
        root = root.parent

    def has(*names) -> bool:
        return any((root / n).exists() for n in names)

    def glob1(*patterns) -> bool:
        return any(next(root.glob(p), None) is not None for p in patterns)

    frameworks, schema, tests = [], [], []

    if has("artisan"):
        frameworks.append("laravel")
    if has("composer.json"):
        frameworks.append("php/composer")
        try:
            import json as _json
            data = _json.loads((root / "composer.json").read_text())
            deps = {**(data.get("require") or {}), **(data.get("require-dev") or {})}
            if "phpunit/phpunit" in deps:
                tests.append("phpunit")
            if "laravel/framework" in deps and "laravel" not in frameworks:
                frameworks.append("laravel")
        except (OSError, ValueError):
            pass
    if has("phpunit.xml", "phpunit.xml.dist"):
        tests.append("phpunit")

    if has("package.json"):
        try:
            import json as _json
            data = _json.loads((root / "package.json").read_text())
            scripts = data.get("scripts") or {}
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            if "next" in deps:
                frameworks.append("next.js")
            if "react" in deps:
                frameworks.append("react")
            if "express" in deps:
                frameworks.append("express")
            if "vitest" in deps or "vitest.config.ts" in deps:
                tests.append("vitest")
            if "jest" in deps:
                tests.append("jest")
            if scripts.get("test"):
                tests.append("npm test script")
            # A workspace root declares `workspaces` and keeps every dependency in
            # its children. Reading only the root's package.json made a real
            # Express+React monorepo look like it had no framework at all.
            for ws in (data.get("workspaces") or [])[:8]:
                child = root / ws.replace("*", "")
                pkg = child / "package.json" if child.is_dir() else None
                if not pkg or not pkg.is_file():
                    continue
                try:
                    cd = _json.loads(pkg.read_text())
                except (OSError, ValueError):
                    continue
                cdep = {**(cd.get("dependencies") or {}), **(cd.get("devDependencies") or {})}
                if "express" in cdep and "express" not in frameworks:
                    frameworks.append("express")
                if "react" in cdep and "react" not in frameworks:
                    frameworks.append("react")
                if "next" in cdep and "next.js" not in frameworks:
                    frameworks.append("next.js")
                cs = (cd.get("scripts") or {}).get("test")
                if cs:
                    cmd = "vitest" if "vitest" in cs else "jest" if "jest" in cs else "npm test script"
                    tests.append(cmd)
        except (OSError, ValueError):
            pass

    if glob1("prisma/schema.prisma", "*/prisma/schema.prisma"):
        schema.append("prisma")
    if glob1("*.sql", "database/migrations/*.sql", "migrations/*.sql", "*/*.sql"):
        schema.append("sql")
    if glob1("app/Models/*.php", "*/app/Models/*.php"):
        schema.append("laravel-migrations" if has("artisan") else "php-models")
    if glob1("models.py", "*/models.py"):
        schema.append("django (unreadable)")
    if glob1("meilisearch*", "**/*.prisma"):
        pass

    def uniq(xs):
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return sorted(out)

    return {"frameworks": uniq(frameworks), "schema": uniq(schema), "tests": uniq(tests)}


def suggested_preset(root) -> tuple[str, str]:
    """Which preset `init` should pick when nobody chose one.

    The rule is about age, not taste: a repo whose schema is already consistent
    can hold `strict` without drowning, and a repo with mixed styles needs the
    warnings first. This returns (preset, one-line reason) so `init` can say why
    instead of asking a question the user has no basis to answer yet.
    """
    stack = detect_stack(root)
    has_tests = bool(stack["tests"])
    modern = any(f in stack["frameworks"] for f in ("next.js", "laravel", "express"))
    if modern and has_tests:
        return "strict", f"{', '.join(stack['frameworks'])} with {stack['tests'][0]}"
    if modern:
        return "balanced", f"{', '.join(stack['frameworks'])}, no test runner detected"
    return "legacy-friendly", "no framework markers found; assume existing debt"
