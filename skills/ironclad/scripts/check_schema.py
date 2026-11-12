#!/usr/bin/env python3
"""Schema convention checker for Ironclad.

Scans SQL files, Laravel migrations, and Prisma schemas for rule violations.

Exit codes: 0 = no error-severity findings, 1 = violations, 2 = usage error.

Severity comes from a preset, so the same checker can be gentle on a brownfield
repo and block hard on a regulated one:

    presets/legacy-friendly.yml   everything warns
    presets/balanced.yml          default — most rules block
    presets/strict.yml            everything blocks, no warnings
    .agent/standards.yml          per-repo override, created by init_standards.py

Resolution order: --config > --preset > .agent/standards.yml > built-in balanced.

Rules:
  DB-01 native enum in schema
  DB-02 magic number compared to / assigned on a status-like field
  DB-03 status integer with no FK/CHECK
  DB-04 status stored as text
  DB-05 boolean named for a non-binary concept
  DB-06 money stored as float
  DB-07 timestamp without timezone
"""

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
# Two layouts: inside the skill (assets/presets/) and inside a target repo where
# init_standards.py --with-checker copied the checker next to its presets (presets/).
_HERE = Path(__file__).resolve().parent
PRESET_DIR = next((d for d in (_HERE / "presets", SKILL_DIR / "assets" / "presets") if d.is_dir()),
                  _HERE / "presets")

DEFAULT_PRESET = "balanced"

BUILTIN_PRESET = {
    "name": "balanced",
    "rules": {"DB-01": "error", "DB-02": "error", "DB-03": "warn",
              "DB-04": "error", "DB-05": "warn", "DB-06": "warn", "DB-07": "warn"},
    "exceptions": [],
    "boolean_allowlist": ["is_active", "is_deleted", "is_published",
                          "is_verified", "is_terminal", "has_invoice"],
}

RULE_TITLES = {
    "DB-01": "native enum in schema",
    "DB-02": "magic number on a status field",
    "DB-03": "status integer without FK/CHECK",
    "DB-04": "status stored as text",
    "DB-05": "boolean named for a non-binary concept",
    "DB-06": "money stored as float",
    "DB-07": "timestamp without timezone",
}

# `type`/`tipe` must start a word segment, otherwise `mimeType`/`prototype` false-positive.
_LEAD = r"(?<![a-z])"
STATUS_WORD = _LEAD + r"(?:status|state|stage|kondisi|keberangkatan|ketersediaan|kategori|type|tipe)"
STATUS_COL = re.compile(rf"^[a-z0-9_]*{STATUS_WORD}[a-z0-9_]*$", re.I)

ENUM_PATTERNS = [
    (re.compile(r"\$\w+\s*->\s*enum\s*\(", re.I), "Laravel $table->enum()"),
    (re.compile(r"\bALTER\s+TABLE\b[^;]*\bADD\s+COLUMN\b[^;]*\benum\s*\(", re.I),
     "SQL enum column"),
    # Not anchored to the line: `CREATE TABLE t (id bigint, status enum('a','b'))` is
    # the shape people actually write, and an anchored pattern let every one-line
    # definition through as a pass. Requires a word before `enum(` so a bare
    # `ENUM(...)` in an INSERT/type cast is not mistaken for a column definition.
    (re.compile(r"[\w\"]\s+enum\s*\(", re.I), "SQL/prisma enum column"),
    (re.compile(r"^\s*enum\s+\w+\s*\{", re.I | re.M), "prisma enum block"),
]

# HTTP response codes are not database status columns. `res.status === 409`,
# `res.__status === 401` and `xhr.status == 404` are the most common false positives
# on a PHP/JS repo, and noise like that is what makes people switch a linter off.
# A *receiver* before the dot: `res.status`, `r.status`, `response.status`,
# `response.__status`, `xhr.status`. Deliberately not a bare `status == 404`, which
# still looks like a database column and stays flagged.
HTTP_RECEIVER = re.compile(
    r"(?:\bres(?:ponse)?|r|xhr|request|req)\s*\.\s*_*$",
    re.I,
)

# status = 0 | ->where('status', 2) | === 3 on a status-y name
MAGIC_COMPARE = re.compile(
    rf"({STATUS_WORD}[a-zA-Z0-9_]*)\s*(?:===?|!==?|<>|==|!=)\s*'?\d+'?", re.I)
MAGIC_WHERE = re.compile(
    rf"['\"]([a-z0-9_]*{STATUS_WORD}[a-z0-9_]*)['\"]\s*,\s*'?\d+'?", re.I)
MAGIC_ASSIGN = re.compile(
    rf"(\$?\w*{STATUS_WORD}\w*)\s*=\s*'?[0-9]'?\s*;", re.I)

VARCHAR_STATUS = re.compile(
    rf"['\"]?([a-z0-9_]*{STATUS_WORD}[a-z0-9_]*)['\"]?\s+(?:varchar|string|text)", re.I)
# Laravel puts the type first: $table->string('departure_status')
LARAVEL_STRING_STATUS = re.compile(
    rf"\$\w+\s*->\s*(?:string|text)\s*\(\s*['\"]([a-z0-9_]*{STATUS_WORD}[a-z0-9_]*)['\"]", re.I)

BOOL_NAMES = re.compile(r"\b(is|has|should|can)_(?:status|state|kondisi|tipe|type|kategori)\b", re.I)

MONEY_WORD = r"(?:amount|price|harga|total|subtotal|cost|biaya|fee|tarif|salary|gaji|balance|saldo)"
MONEY_FLOAT = re.compile(
    rf"\b([a-z0-9_]*(?:{MONEY_WORD})[a-z0-9_]*)\b\s+(?:float|double|real|float8|float4)\b", re.I)
MONEY_FLOAT_LARAVEL = re.compile(rf"\$\w+\s*->\s*(?:float|double)\s*\(\s*['\"]([^'\"]+)['\"]", re.I)

TIMESTAMP_BARE = re.compile(r"\b([a-z0-9_]+)\s+timestamp\b(?!\s*\(?\s*\d*\s*\)?\s*with\s+time\s+zone)", re.I)
# Laravel spells the same thing differently, and `timestamp()` there means
# "timestamp WITHOUT time zone" — a genuine drift trap that raw-SQL patterns miss.
LARAVEL_TIMESTAMP_BARE = re.compile(
    r"\$\w+\s*->\s*timestamp\s*\(\s*['\"]([^'\"]+)['\"]", re.I)

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".next",
             "storage", "__pycache__", ".venv", "venv"}
TARGETS = {".sql", ".php", ".prisma"}

# Stacks this checker cannot read yet, but whose files are unambiguously schema.
# Staying silent about them is the worst failure mode available: the run is green,
# the CI badge is green, and half the repo was never looked at. So we detect them
# and say so out loud instead of implying coverage we do not have.
UNSUPPORTED_HINTS = {
    ".py": re.compile(r"\bmodels\.(?:Model|CharField|IntegerField|FloatField|DecimalField|"
                      r"ForeignKey|SmallIntegerField)\b|\bColumn\(\s*(?:Integer|String|Float)"),
    ".rb": re.compile(r"\bcreate_table\b|\bt\.(?:integer|string|decimal|float)\b"),
    ".ts": re.compile(r"\bpgTable\b|@Entity\b|\bDataTypes\.",
                      re.I),
    ".js": re.compile(r"\bpgTable\b|\bDataTypes\.|\bSequelize\b|\bModel\.init\b"),
    ".go": re.compile(r"\bgorm:\""),
    ".java": re.compile(r"@Entity\b"),
    ".kt": re.compile(r"@Entity\b"),
    ".cs": re.compile(r"\[Table\(|\bDbSet<"),
    ".rs": re.compile(r"#\[(?:derive\(.*?(?:sqlx|diesel)|table_name)"),
}


# ---------------------------------------------------------------- preset loading
# Deliberately dependency-free: CI often has no PyYAML, and a checker that fails
# to import its own config is worse than no checker. Parses the subset we ship:
# `key: value` under `rules:`, and `- item` lists under named keys.
def _parse_simple_yaml(text):
    data = {"rules": {}, "exceptions": [], "boolean_allowlist": []}
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
        if line.startswith(("exceptions:", "boolean_allowlist:")):
            section = line.split(":")[0].strip()
            continue
        if section == "rules" and ":" in line:
            key, _, val = line.partition(":")
            data["rules"][key.strip()] = val.split("#")[0].strip().lower()
            continue
        if section in ("exceptions", "boolean_allowlist") and line.lstrip().startswith("-"):
            data[section].append(line.lstrip()[1:].strip().strip("'\""))
    return data


def _find_repo_config(repo_paths):
    """The repo's own policy: .agent/standards.yml at or above the first target."""
    for base in (Path(p) for p in (repo_paths or ["."])):
        base = base.resolve()
        for d in [base, *base.parents]:
            cand = d / ".agent" / "standards.yml"
            if cand.is_file():
                return cand
    return None


def load_preset(name=None, config_path=None, repo_paths=None):
    """Merge preset layers. Returns (config, source_label).

    Precedence, weakest to strongest:

        built-in balanced  <  repo .agent/standards.yml  <  --preset  <  --config

    The repo policy must be layered even when --preset is given, or an explicit
    flag would silently discard the repo's own `exceptions` and allowlists.
    And --preset must beat the repo, because a caller asking for `strict` in CI
    is asking for a stricter run than whatever the repo committed — it used to
    lose that argument silently.
    """
    layers = []
    labels = []

    # 1. The repo's own policy. Skipped when an explicit config file is named:
    #    two policy files at once is a question nobody wants to answer twice.
    repo_cfg = None if config_path else _find_repo_config(repo_paths)
    if repo_cfg is not None:
        repo_layer = _parse_simple_yaml(repo_cfg.read_text())
        # `name:` alone is a valid policy file — that is what `ironclad preset`
        # writes. Resolve it to the preset's rules here, in one place, instead of
        # having the shell turn the name into --preset (which is how a repo on
        # `coherence` became uncheckable, and how repo `exceptions` got dropped).
        # Overlay, never replace: a repo may name a preset *and* keep its own
        # exceptions, and replacing the layer would quietly delete them.
        named = repo_layer.get("name")
        if named and not repo_layer.get("rules") and (PRESET_DIR / f"{named}.yml").is_file():
            resolved = _parse_simple_yaml((PRESET_DIR / f"{named}.yml").read_text())
            resolved.update({k: v for k, v in repo_layer.items() if v})
            repo_layer = resolved
        layers.append(repo_layer)
        labels.append(str(repo_cfg))

    # 2. An explicitly requested preset outranks the committed one.
    if name:
        preset_file = PRESET_DIR / f"{name}.yml"
        if not preset_file.is_file():
            print(f"unknown preset '{name}' — available: "
                  f"{', '.join(sorted(p.stem for p in PRESET_DIR.glob('*.yml')))}",
                  file=sys.stderr)
            return None, None
        layers.append(_parse_simple_yaml(preset_file.read_text()))
        labels.append(f"preset:{name}")

    # 3. An explicit config file outranks everything.
    if config_path:
        cfg = Path(config_path)
        if not cfg.is_file():
            print(f"config not found: {cfg}", file=sys.stderr)
            return None, None
        layers.append(_parse_simple_yaml(cfg.read_text()))
        labels.append(str(cfg))

    # `source` keeps its old shape — the strongest layer — because consumers may
    # parse it. The full chain goes in a new key, so layering is visible without
    # breaking anyone. Additive only, per COMPATIBILITY_PLAN.md.
    source = labels[-1] if labels else "builtin:balanced"
    sources = labels or ["builtin:balanced"]

    merged = {"name": DEFAULT_PRESET, "rules": dict(BUILTIN_PRESET["rules"]),
              "exceptions": [], "boolean_allowlist": list(BUILTIN_PRESET["boolean_allowlist"])}
    for layer in layers:
        merged["rules"].update(layer.get("rules") or {})
        if layer.get("exceptions"):
            merged["exceptions"] = layer["exceptions"]
        if layer.get("boolean_allowlist"):
            merged["boolean_allowlist"] = layer["boolean_allowlist"]
        if layer.get("name"):
            merged["name"] = layer["name"]
    merged["sources"] = sources
    return merged, source


# ------------------------------------------------------------------- rule engine
def iter_files(paths, exceptions=()):
    exc = [e.rstrip("/") for e in exceptions]
    for p in paths:
        p = Path(p)
        if p.is_file() and p.suffix in TARGETS:
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.suffix not in TARGETS:
                    continue
                if set(f.parts) & SKIP_DIRS:
                    continue
                s = str(f)
                if any(e in s for e in exc):
                    continue
                yield f


def find_unsupported(paths):
    """Schema files in stacks we cannot parse. Reported, never silently skipped."""
    hits = {}
    for p in paths:
        root = Path(p)
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if f.suffix not in UNSUPPORTED_HINTS:
                continue
            if set(f.parts) & SKIP_DIRS:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if UNSUPPORTED_HINTS[f.suffix].search(text):
                hits.setdefault(f.suffix, []).append(str(f))
    return hits


def is_migration_like(path, text):
    # Laravel migration filenames look like 2024_01_01_000000_create_orders_table.php
    # — the word "migration" is in the DIRECTORY, not the filename. Checking only
    # path.name silently skipped every real Laravel migration.
    where = str(path).lower()
    return ("migration" in where or "migrasi" in where
            or "schema" in where
            or re.search(r"\$\w+\s*->", text) is not None
            or re.search(r"\bSchema::\w+\b", text) is not None
            or re.search(r"\bCREATE\s+TABLE\b", text, re.I) is not None)


def status_styles(path, text):
    """Which ways does this file store a status?

    The point of DB-08 is not that one style is wrong in isolation — it is that a
    project using three of them forces every report to be written three times, and
    makes "how do we add a status?" a question with no single answer.
    Returns a set of style names found in this file.
    """
    styles = set()
    for line in text.splitlines():
        if line.strip().startswith(("//", "#", "--", "*")):
            continue
        if any(pat.search(line) for pat, _ in ENUM_PATTERNS):
            styles.add("enum")
        if VARCHAR_STATUS.search(line) or LARAVEL_STRING_STATUS.search(line):
            styles.add("text")
        if re.search(rf"\b(?:[a-z0-9_]*{STATUS_WORD}[a-z0-9_]*)\b\s+"
                     rf"(?:smallint|tinyint|integer|int|bigint)", line, re.I):
            styles.add("integer")
    return styles


def check_file(path, cfg):
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [{"rule": "IO", "severity": "error", "line": 0,
                 "msg": f"unreadable: {e}", "file": str(path)}]

    def add(rule, line, msg):
        sev = cfg["rules"].get(rule, "warn")
        if sev in ("off", "ignore", "none"):
            return
        findings.append({"rule": rule, "severity": sev, "line": line,
                         "msg": msg, "file": str(path)})

    lines = text.splitlines()
    migration = is_migration_like(path, text)
    bool_allow = {b.lower() for b in cfg.get("boolean_allowlist") or []}

    in_comment_block = False
    check_depth = 0          # paren depth inside a CHECK(...) constraint
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("/*"):
            in_comment_block = True
        if in_comment_block:
            if "*/" in stripped:
                in_comment_block = False
            continue
        if stripped.startswith(("//", "#", "--", "*")):
            continue

        # DB-01
        for pat, label in ENUM_PATTERNS:
            if pat.search(line):
                add("DB-01", i, f"{label}; use integer code + lookup table (see DB-03)")
                break

        # a CHECK constraint is exactly where literal codes belong (DDL, not app logic)
        line_in_check = check_depth > 0 or re.search(r"\bCHECK\b", line, re.I) is not None
        if re.search(r"\bCHECK\b", line, re.I):
            check_depth += line.count("(") - line.count(")")
        elif check_depth > 0:
            check_depth += line.count("(") - line.count(")")
            if check_depth < 0:
                check_depth = 0

        # DB-02
        for pat, kind in ((MAGIC_COMPARE, "comparison"), (MAGIC_WHERE, "query filter"),
                          (MAGIC_ASSIGN, "assignment")):
            m = pat.search(line)
            if m and line_in_check:
                break
            if m and (migration or kind != "assignment"):
                name = m.group(1) if m.groups() else m.group(0)
                # An HTTP response code is not a database status value. The name the
                # regex captured tells us: if it is literally `status` and a response
                # object precedes it (`res.status`, `r.status`, `response.__status`),
                # this is transport, not schema.
                if kind == "comparison" and name.lower().lstrip("_") == "status":
                    if HTTP_RECEIVER.search(line[:m.start()]):
                        continue
                add("DB-02", i, f"magic number in {kind} on `{name}`; use a named constant")
                break

        # DB-04
        m = VARCHAR_STATUS.search(line) or LARAVEL_STRING_STATUS.search(line)
        if m and migration:
            add("DB-04", i, f"status stored as text (`{m.group(1)}`); use smallint code + lookup table")

        # DB-05
        m = BOOL_NAMES.search(line)
        if m and m.group(0).lower() not in bool_allow:
            add("DB-05", i, f"`{m.group(0)}` is not a binary concept; use a code column")

        # DB-06
        if migration:
            m = MONEY_FLOAT.search(line) or MONEY_FLOAT_LARAVEL.search(line)
            if m:
                add("DB-06", i, f"money column `{m.group(1)}` uses a binary float type; "
                                f"use numeric/decimal with a fixed scale, or bigint minor units")

        # DB-07 — camelCase `*At` is the Laravel/Prisma timestamp convention, not a smell
        if migration:
            lm = LARAVEL_TIMESTAMP_BARE.search(line)
            if lm and not lm.group(1).endswith("_tz"):
                add("DB-07", i, f"`$table->timestamp('{lm.group(1)}')` has no timezone; "
                                f"use timestampTz() so Jakarta and the server agree")
            m = TIMESTAMP_BARE.search(line)
            if m and not re.search(r"[a-z]At$", m.group(1)) and "timestamptz" not in line.lower():
                add("DB-07", i, f"`{m.group(0).strip()}` has no timezone; "
                                f"use timestamptz (or createdAt/updatedAt in Laravel)")

    # DB-03: a status code column with no FK/CHECK anywhere in the file
    #
    # A constraint is very often written across two lines, which is the house style
    # in most migrations:
    #
    #     CONSTRAINT orders_status_fk FOREIGN KEY (status_code)
    #         REFERENCES order_status (code)
    #
    # Reading only the column's own line calls that a violation and would fail a
    # correct schema. So: build a window around the line and also accept a
    # table-level FOREIGN KEY that names the column anywhere in the file.
    if migration:
        window = 6
        for i, line in enumerate(lines, 1):
            m = re.search(rf"\b([a-z0-9_]*{STATUS_WORD}[a-z0-9_]*(?:_code)?)\b\s+"
                          rf"(?:smallint|tinyint|integer|int|bigint)", line, re.I)
            if not m:
                continue
            col = m.group(1)
            if not STATUS_COL.match(col):
                continue
            lo = max(0, i - 1 - window)
            hi = min(len(lines), i + window)
            near = "\n".join(lines[lo:hi])

            inline = re.search(
                rf"\b{re.escape(col)}\b[^\n]{{0,200}}?(?:\bREFERENCES\b|\bconstrained\b|\bCHECK\b)",
                near, re.I)
            # table-level: FOREIGN KEY (col) ... REFERENCES, possibly split over lines
            table_level = re.search(
                rf"\bFOREIGN\s+KEY\s*\(\s*{re.escape(col)}\s*\)[^;]{{0,400}}?\bREFERENCES\b",
                text, re.I | re.S)
            # a column-level CHECK inside the same CREATE TABLE block
            block = re.search(rf"\b{re.escape(col)}\b[^;]{{0,300}}?\bCHECK\s*\(",
                              text, re.I | re.S)
            if inline or table_level or block:
                continue
            add("DB-03", i, f"`{col}` has no FK to a lookup table or CHECK constraint")

    return findings


def main():
    ap = argparse.ArgumentParser(
        description="Company schema convention checker",
        epilog="presets: " + ", ".join(sorted(p.stem for p in PRESET_DIR.glob("*.yml"))))
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--preset", help="preset name (balanced, strict, legacy-friendly, coherence)")
    ap.add_argument("--config", help="explicit config file (overrides --preset)")
    ap.add_argument("--strict", action="store_true",
                    help="escalate every warn to an error (legacy flag, still supported)")
    ap.add_argument("--list-presets", action="store_true")
    args = ap.parse_args()

    if args.list_presets:
        for p in sorted(PRESET_DIR.glob("*.yml")):
            data = _parse_simple_yaml(p.read_text())
            n_err = sum(1 for v in data["rules"].values() if v == "error")
            n_warn = sum(1 for v in data["rules"].values() if v == "warn")
            print(f"{p.stem:18} errors={n_err} warns={n_warn}  {data.get('title','')}")
        return 0

    targets = args.paths or ["."]
    cfg, source = load_preset(args.preset, args.config, targets)
    if cfg is None:
        return 2

    files = list(iter_files(targets, cfg.get("exceptions") or ()))
    unsupported = find_unsupported(targets)

    if not files:
        print("no .sql/.php/.prisma files found", file=sys.stderr)
        if unsupported:
            exts = ", ".join(sorted(unsupported))
            print(f"\nThis repo does have schema files this checker cannot read: {exts}.",
                  file=sys.stderr)
            print("Nothing was checked. Do not treat this as a pass.", file=sys.stderr)
            for ext, paths in sorted(unsupported.items()):
                print(f"  {ext}: {paths[0]}"
                      f"{f' (+{len(paths)-1} more)' if len(paths) > 1 else ''}",
                      file=sys.stderr)
            print("\nUntil support exists, enforce the same rules by hand or with your",
                  file=sys.stderr)
            print("framework's own migrations review — see", file=sys.stderr)
            print("https://wilsench.my.id/ironclad/troubleshooting/", file=sys.stderr)
        return 2

    findings = []
    style_map = {}
    for f in files:
        findings.extend(check_file(f, cfg))
        try:
            found = status_styles(f, f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            found = set()
        if found:
            style_map[f] = found

    # DB-08 — the project uses more than one way to store a status. Each file above
    # is already judged on its own; this is the only rule that looks across files,
    # because inconsistency is a property of the whole project, not of one table.
    # One finding for the project, not one per file: a reader needs to know that a
    # choice was never made, not that eleven files each picked something.
    all_styles = set().union(*style_map.values()) if style_map else set()
    if len(all_styles) > 1:
        sev = cfg["rules"].get("DB-08", "warn")
        if sev not in ("off", "ignore", "none"):
            rank = {"enum": 0, "text": 1, "integer": 2}
            order = sorted(all_styles, key=lambda s: rank.get(s, 9))
            where = {}
            for f, styles in style_map.items():
                for s in styles:
                    where.setdefault(s, str(f))
            detail = ", ".join(f"{s} ({where[s]})" for s in order)
            first = style_map and sorted(style_map, key=str)[0]
            # Do not advertise a house preference to people who never asked for one.
            # Under `coherence` the point is that a choice was never made, not which.
            indoor = ("pick one for the whole project"
                      if cfg.get("name") == "coherence"
                      else "integer code + lookup is the default")
            findings.append({
                "rule": "DB-08", "severity": sev, "line": 1,
                "msg": (f"status is stored {len(all_styles)} different ways in this "
                        f"project: {detail} — {indoor}"),
                "file": str(first)})

    # Partial coverage is the dangerous case: green output, half a repo unchecked.
    if unsupported:
        partial = (f"{len(files)} schema file(s) checked, but this repo also has "
                   f"{', '.join(sorted(unsupported))} schema files this checker cannot read")
        findings.append({
            "rule": "COVERAGE", "severity": "warn", "line": 1,
            "msg": partial + " — those files were NOT checked; verify them by hand",
            "file": (sorted(unsupported.items())[0][1] or ["."])[0]})

    if args.strict:
        for f in findings:
            f["severity"] = "error"

    errors = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warn"]

    if args.json:
        print(json.dumps({"preset": cfg.get("name"), "source": source,
                          "sources": cfg.get("sources") or [source],
                          "files": len(files), "findings": findings,
                          "errors": len(errors), "warnings": len(warns)},
                         indent=2, ensure_ascii=False))
    else:
        for f in findings:
            tag = "ERROR" if f["severity"] == "error" else "warn "
            print(f"{f['file']}:{f['line']}: [{f['rule']}] {tag} {f['msg']}")
        if findings:
            print()
        print(f"preset: {cfg.get('name')} ({source})")
        print(f"{len(files)} file(s), {len(errors)} error(s), {len(warns)} warning(s)")
        if warns and not errors:
            print("warnings do not fail the build; use --strict to escalate")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
