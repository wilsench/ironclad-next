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
    """The repo's own policy: .agent/standards.yml at or above the first target."""
    for base in (Path(p) for p in (repo_paths or ["."])):
        base = base.resolve()
        for d in [base, *base.parents]:
            cand = d / ".agent" / "standards.yml"
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
