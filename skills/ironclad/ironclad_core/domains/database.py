"""The database domain: the original eight rules, unchanged in behaviour.

Every rule is now a class with an ID and a scope instead of a block inside one
long loop. The regexes are copied verbatim from 0.10.2 — the point of Phase 1 is
to prove the interface holds, not to improve the rules.
"""

from __future__ import annotations

import re

from .. import Finding, RuleMeta, Position
from ..engine import FileContext, ProjectRule, Registry, Rule

DOMAIN = "database"

# The file types this domain can read. Declared here, not in discovery: the
# engine unions what the loaded domains claim, so a new domain means a new file.
DATABASE_EXTS = (".sql", ".php", ".prisma")

# ---------------------------------------------------------------- vocabulary
# `type`/`tipe` must start a word segment, otherwise `mimeType`/`prototype`
# false-positive.
_LEAD = r"(?<![a-z])"
STATUS_WORD = _LEAD + r"(?:status|state|stage|kondisi|keberangkatan|ketersediaan|kategori|type|tipe)"
STATUS_COL = re.compile(rf"^[a-z0-9_]*{STATUS_WORD}[a-z0-9_]*$", re.I)

ENUM_PATTERNS = [
    (re.compile(r"\$\w+\s*->\s*enum\s*\(", re.I), "Laravel $table->enum()"),
    (re.compile(r"\bALTER\s+TABLE\b[^;]*\bADD\s+COLUMN\b[^;]*\benum\s*\(", re.I),
     "SQL enum column"),
    # Not anchored to the line: `CREATE TABLE t (id bigint, status enum('a','b'))`
    # is the shape people actually write, and an anchored pattern let every
    # one-line definition through as a pass.
    (re.compile(r"[\w\"]\s+enum\s*\(", re.I), "SQL/prisma enum column"),
    (re.compile(r"^\s*enum\s+\w+\s*\{", re.I | re.M), "prisma enum block"),
]

# HTTP response codes are not database status columns. `res.status === 409` is
# the most common false positive on a PHP/JS repo, and noise like that is what
# makes people switch a linter off.
HTTP_RECEIVER = re.compile(r"(?:\bres(?:ponse)?|r|xhr|request|req)\s*\.\s*_*$", re.I)

# A column *declaration* carries a length, not a status value: `string('tipe', 40)`
# and `char('state', 2)` are dimensions. Matching those made DB-02 fire on every
# sized column named status/type/tipe — the most common shape in Laravel.
# It must name the schema builder: `where('status', 2)` also ends in `)` and the
# 2 there *is* a status code.
COLUMN_LENGTH = re.compile(
    rf"->\s*(?:string|char|varchar|text|enum)\s*\(\s*['\"][a-z0-9_]*{STATUS_WORD}"
    rf"[a-z0-9_]*['\"]\s*,\s*'?\d+'?\s*\)", re.I)

MAGIC_COMPARE = re.compile(
    rf"({STATUS_WORD}[a-zA-Z0-9_]*)\s*(?:===?|!==?|<>|==|!=)\s*'?\d+'?", re.I)
MAGIC_WHERE = re.compile(
    rf"['\"]([a-z0-9_]*{STATUS_WORD}[a-z0-9_]*)['\"]\s*,\s*'?\d+'?", re.I)
MAGIC_ASSIGN = re.compile(rf"(\$?\w*{STATUS_WORD}\w*)\s*=\s*'?[0-9]'?\s*;", re.I)

# DB-04 is about lifecycle state stored as human labels ('In Stock', 'in stock ').
# A classification column (`tipe` = hero/tentang/proyek) is a discriminant, not a
# status: text is a normal choice there, and smallint would not be an improvement.
LIFECYCLE_WORD = _LEAD + r"(?:status|state|stage|kondisi|keberangkatan|ketersediaan)"

VARCHAR_STATUS = re.compile(
    rf"['\"]?([a-z0-9_]*{LIFECYCLE_WORD}[a-z0-9_]*)['\"]?\s+(?:varchar|string|text)", re.I)
LARAVEL_STRING_STATUS = re.compile(
    rf"\$\w+\s*->\s*(?:string|text)\s*\(\s*['\"]([a-z0-9_]*{LIFECYCLE_WORD}[a-z0-9_]*)['\"]",
    re.I)

BOOL_NAMES = re.compile(r"\b(is|has|should|can)_(?:status|state|kondisi|tipe|type|kategori)\b", re.I)

MONEY_WORD = r"(?:amount|price|harga|total|subtotal|cost|biaya|fee|tarif|salary|gaji|balance|saldo)"
MONEY_FLOAT = re.compile(
    rf"\b([a-z0-9_]*(?:{MONEY_WORD})[a-z0-9_]*)\b\s+(?:float|double|real|float8|float4)\b", re.I)
MONEY_FLOAT_LARAVEL = re.compile(
    rf"\$\w+\s*->\s*(?:float|double)\s*\(\s*['\"]([^'\"]+)['\"]", re.I)

TIMESTAMP_BARE = re.compile(
    r"\b([a-z0-9_]+)\s+timestamp\b(?!\s*\(?\s*\d*\s*\)?\s*with\s+time\s+zone)", re.I)
LARAVEL_TIMESTAMP_BARE = re.compile(
    r"\$\w+\s*->\s*timestamp\s*\(\s*['\"]([^'\"]+)['\"]", re.I)

INT_TYPE = rf"(?:smallint|tinyint|integer|int|bigint)"


# ------------------------------------------------------------------- helpers
def is_migration_like(path, text: str) -> bool:
    """Laravel filenames put the word 'migration' in the DIRECTORY, not the name.

    Checking only `path.name` silently skipped every real Laravel migration.
    """
    where = str(path).lower()
    return ("migration" in where or "migrasi" in where
            or "schema" in where
            or re.search(r"\$\w+\s*->", text) is not None
            or re.search(r"\bSchema::\w+\b", text) is not None
            or re.search(r"\bCREATE\s+TABLE\b", text, re.I) is not None)


def _comment_lines(text: str):
    """Yield (lineno, line) for lines that are not comments, tracking /* */."""
    in_block = False
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("/*"):
            in_block = True
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith(("//", "#", "--", "*")):
            continue
        yield i, line


# --------------------------------------------------------------------- rules
class Db01Enum(Rule):
    extensions = DATABASE_EXTS
    meta = RuleMeta("DB-01", DOMAIN, "native enum in schema", "error")

    def check(self, ctx: FileContext, cfg: dict) -> list[Finding]:
        out = []
        for i, line in _comment_lines(ctx.text):
            for pat, label in ENUM_PATTERNS:
                if pat.search(line):
                    out.append(Finding(rule="DB-01", severity="error", file=str(ctx.path),
                                       position=Position(i), domain=DOMAIN,
                                       message=f"{label}; use integer code + lookup table "
                                               f"(see DB-03)"))
                    break
        return out


class Db02MagicNumber(Rule):
    extensions = DATABASE_EXTS
    meta = RuleMeta("DB-02", DOMAIN, "magic number on a status field", "error")

    def check(self, ctx: FileContext, cfg: dict) -> list[Finding]:
        out = []
        migration = is_migration_like(ctx.path, ctx.text)
        check_depth = 0
        for i, line in _comment_lines(ctx.text):
            in_check = check_depth > 0 or re.search(r"\bCHECK\b", line, re.I) is not None
            if re.search(r"\bCHECK\b", line, re.I):
                check_depth += line.count("(") - line.count(")")
            elif check_depth > 0:
                check_depth += line.count("(") - line.count(")")
                if check_depth < 0:
                    check_depth = 0

            for pat, kind in ((MAGIC_COMPARE, "comparison"), (MAGIC_WHERE, "query filter"),
                              (MAGIC_ASSIGN, "assignment")):
                m = pat.search(line)
                if m and in_check:
                    break
                if not (m and (migration or kind != "assignment")):
                    continue
                # `string('tipe', 40)` declares a width. The 40 is bytes, not a
                # status code, and flagging it is noise on every sized column.
                if COLUMN_LENGTH.search(line):
                    break
                name = m.group(1) if m.groups() else m.group(0)
                # `res.status === 401` is transport, not schema. The captured
                # name tells us: if it is literally `status` and a receiver
                # precedes it, this is not a database column.
                if kind == "comparison" and name.lower().lstrip("_") == "status":
                    if HTTP_RECEIVER.search(line[:m.start()]):
                        continue
                out.append(Finding(rule="DB-02", severity="error", file=str(ctx.path),
                                   position=Position(i), domain=DOMAIN,
                                   message=f"magic number in {kind} on `{name}`; "
                                           f"use a named constant"))
                break
        return out


class Db03LookupFk(Rule):
    extensions = DATABASE_EXTS
    meta = RuleMeta("DB-03", DOMAIN, "status integer without FK/CHECK", "warn")

    def check(self, ctx: FileContext, cfg: dict) -> list[Finding]:
        if not is_migration_like(ctx.path, ctx.text):
            return []
        out = []
        lines = ctx.lines
        text = ctx.text
        window = 6

        for i, line in enumerate(lines, 1):
            m = re.search(rf"\b([a-z0-9_]*{STATUS_WORD}[a-z0-9_]*(?:_code)?)\b\s+{INT_TYPE}",
                          line, re.I)
            if not m:
                continue
            col = m.group(1)
            if not STATUS_COL.match(col):
                continue
            lo, hi = max(0, i - 1 - window), min(len(lines), i + window)
            near = "\n".join(lines[lo:hi])

            inline = re.search(
                rf"\b{re.escape(col)}\b[^\n]{{0,200}}?(?:\bREFERENCES\b|\bconstrained\b|\bCHECK\b)",
                near, re.I)
            # Table-level FOREIGN KEY, possibly split over lines — the house
            # style in most migrations. Reading only the column's own line calls
            # a correct schema a violation.
            table_level = re.search(
                rf"\bFOREIGN\s+KEY\s*\(\s*{re.escape(col)}\s*\)[^;]{{0,400}}?\bREFERENCES\b",
                text, re.I | re.S)
            block = re.search(rf"\b{re.escape(col)}\b[^;]{{0,300}}?\bCHECK\s*\(", text,
                              re.I | re.S)
            if inline or table_level or block:
                continue
            out.append(Finding(rule="DB-03", severity="warn", file=str(ctx.path),
                               position=Position(i), domain=DOMAIN,
                               message=f"`{col}` has no FK to a lookup table or "
                                       f"CHECK constraint"))
        return out


class Db04StatusText(Rule):
    extensions = DATABASE_EXTS
    meta = RuleMeta("DB-04", DOMAIN, "status stored as text", "error")

    def check(self, ctx: FileContext, cfg: dict) -> list[Finding]:
        if not is_migration_like(ctx.path, ctx.text):
            return []
        out = []
        for i, line in _comment_lines(ctx.text):
            m = VARCHAR_STATUS.search(line) or LARAVEL_STRING_STATUS.search(line)
            if m:
                out.append(Finding(rule="DB-04", severity="error", file=str(ctx.path),
                                   position=Position(i), domain=DOMAIN,
                                   message=f"status stored as text (`{m.group(1)}`); "
                                           f"use smallint code + lookup table"))
        return out


class Db05BooleanName(Rule):
    extensions = DATABASE_EXTS
    meta = RuleMeta("DB-05", DOMAIN, "boolean named for a non-binary concept", "warn")

    def check(self, ctx: FileContext, cfg: dict) -> list[Finding]:
        allow = {b.lower() for b in cfg.get("boolean_allowlist") or []}
        out = []
        for i, line in _comment_lines(ctx.text):
            m = BOOL_NAMES.search(line)
            if m and m.group(0).lower() not in allow:
                out.append(Finding(rule="DB-05", severity="warn", file=str(ctx.path),
                                   position=Position(i), domain=DOMAIN,
                                   message=f"`{m.group(0)}` is not a binary concept; "
                                           f"use a code column"))
        return out


class Db06MoneyFloat(Rule):
    extensions = DATABASE_EXTS
    meta = RuleMeta("DB-06", DOMAIN, "money stored as float", "warn")

    def check(self, ctx: FileContext, cfg: dict) -> list[Finding]:
        if not is_migration_like(ctx.path, ctx.text):
            return []
        out = []
        for i, line in _comment_lines(ctx.text):
            m = MONEY_FLOAT.search(line) or MONEY_FLOAT_LARAVEL.search(line)
            if m:
                out.append(Finding(rule="DB-06", severity="warn", file=str(ctx.path),
                                   position=Position(i), domain=DOMAIN,
                                   message=f"money column `{m.group(1)}` uses a binary float "
                                           f"type; use numeric/decimal with a fixed scale, "
                                           f"or bigint minor units"))
        return out


class Db07NaiveTimestamp(Rule):
    extensions = DATABASE_EXTS
    meta = RuleMeta("DB-07", DOMAIN, "timestamp without timezone", "warn")

    def check(self, ctx: FileContext, cfg: dict) -> list[Finding]:
        if not is_migration_like(ctx.path, ctx.text):
            return []
        out = []
        for i, line in _comment_lines(ctx.text):
            lm = LARAVEL_TIMESTAMP_BARE.search(line)
            if lm and not lm.group(1).endswith("_tz"):
                out.append(Finding(rule="DB-07", severity="warn", file=str(ctx.path),
                                   position=Position(i), domain=DOMAIN,
                                   message=f"`$table->timestamp('{lm.group(1)}')` has no "
                                           f"timezone; use timestampTz() so Jakarta and "
                                           f"the server agree"))
            # camelCase `*At` is the Laravel/Prisma convention, not a smell.
            m = TIMESTAMP_BARE.search(line)
            if m and not re.search(r"[a-z]At$", m.group(1)) and "timestamptz" not in line.lower():
                out.append(Finding(rule="DB-07", severity="warn", file=str(ctx.path),
                                   position=Position(i), domain=DOMAIN,
                                   message=f"`{m.group(0).strip()}` has no timezone; "
                                           f"use timestamptz (or createdAt/updatedAt "
                                           f"in Laravel)"))
        return out


def status_styles(text: str) -> set[str]:
    """Which ways does this file store a status?"""
    styles = set()
    for line in text.splitlines():
        if line.strip().startswith(("//", "#", "--", "*")):
            continue
        if any(pat.search(line) for pat, _ in ENUM_PATTERNS):
            styles.add("enum")
        if VARCHAR_STATUS.search(line) or LARAVEL_STRING_STATUS.search(line):
            styles.add("text")
        if re.search(rf"\b(?:[a-z0-9_]*{STATUS_WORD}[a-z0-9_]*)\b\s+{INT_TYPE}", line, re.I):
            styles.add("integer")
    return styles


class Db08MixedStatus(ProjectRule):
    """The project uses more than one way to store a status.

    The only rule that looks across files, because inconsistency is a property
    of the whole project, not of one table. One finding for the project, not one
    per file: a reader needs to know a choice was never made, not that eleven
    files each picked something.
    """
    extensions = DATABASE_EXTS
    meta = RuleMeta("DB-08", DOMAIN, "status stored more than one way", "warn",
                    scope="project")

    def check(self, contexts: list[FileContext], cfg: dict) -> list[Finding]:
        style_map = {}
        for ctx in contexts:
            if ctx.path.suffix not in DATABASE_EXTS:
                continue
            found = status_styles(ctx.text)
            if found:
                style_map[str(ctx.path)] = found

        all_styles = set().union(*style_map.values()) if style_map else set()
        if len(all_styles) < 2:
            return []

        rank = {"enum": 0, "text": 1, "integer": 2}
        order = sorted(all_styles, key=lambda s: rank.get(s, 9))
        where = {}
        for f, styles in style_map.items():
            for s in styles:
                where.setdefault(s, f)
        detail = ", ".join(f"{s} ({where[s]})" for s in order)
        first = style_map and sorted(style_map, key=str)[0]
        # Do not advertise a house preference to people who never asked for one.
        # Under `coherence` the point is that a choice was never made, not which.
        indoor = ("pick one for the whole project"
                  if cfg.get("name") == "coherence"
                  else "integer code + lookup is the default")
        return [Finding(rule="DB-08", severity="warn", file=str(first),
                        position=Position(1), domain=DOMAIN,
                        message=(f"status is stored {len(all_styles)} different ways in "
                                 f"this project: {detail} — {indoor}"))]


def register(reg: Registry) -> None:
    for rule in (Db01Enum(), Db02MagicNumber(), Db03LookupFk(), Db04StatusText(),
                 Db05BooleanName(), Db06MoneyFloat(), Db07NaiveTimestamp(),
                 Db08MixedStatus()):
        reg.add(rule)
