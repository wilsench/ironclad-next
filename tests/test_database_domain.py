"""Tests for the database domain — the false positives found on a real Laravel repo.

The first two cases here are the ones that mattered. Run on `portfolio.ucapin.my.id`
(a Laravel portfolio app, 148 files), Ironclad raised two DB findings that were
wrong, and both were `error` severity, so both would have failed a strict build:

  DB-02  `$table->string('tipe', 40)` read as "magic number in query filter on
         `tipe`". The 40 is the column *width*. Every sized column named
         status/type/tipe fired — the most common shape in any Laravel schema.

  DB-04  `tipe` (= hero / tentang / proyek) read as "status stored as text".
         That is a discriminant, not lifecycle state; text is the right type
         there and the suggested smallint + lookup table would be a downgrade.

So half of this file is negative on purpose: a rule that fires on a healthy
schema is worse than a rule that misses, because it teaches people to ignore
the output.

Run:  python3 tests/test_database_domain.py        (exit 0 = all passed)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "ironclad"))

from ironclad_core.domains import load_all  # noqa: E402
from ironclad_core.engine import FileContext  # noqa: E402

PASS, FAIL = [], []


def check(label: str, got, want) -> None:
    if got == want:
        PASS.append(label)
    else:
        FAIL.append(f"{label}: got {got!r}, want {want!r}")


def ctx(name: str, text: str) -> FileContext:
    return FileContext(path=Path(name), text=text, language="test")


def run_db(*contexts) -> list:
    """Run only the database rules over these contexts."""
    reg = load_all(only=("database",))
    out = []
    for c in contexts:
        for rule in reg.file_rules:
            if rule.applies(c):
                out.extend(rule.check(c, {}))
    for rule in reg.project_rules:
        out.extend(rule.check(list(contexts), {}))
    return out


def rules(*contexts) -> list[str]:
    return sorted(f.rule for f in run_db(*contexts))


MIG = "database/migrations/2026_10_01_000100_create_pesanan_table.php"


# ---------------------------------------------------------------- DB-02 widths
# A column declaration's number is a size, never a status code.
for src, name in [
    ("$table->string('tipe', 40);", "string('tipe', 40)"),
    ("$table->string('status', 20);", "string('status', 20)"),
    ("$table->string('tipe', 40)->nullable();", "string('tipe', 40)->nullable()"),
    ('$table->string("kategori", 40);', 'string("kategori", 40)'),
    ("status varchar(20)", "varchar(20) SQL"),
    ("$table->char('state', 2);", "char('state', 2)"),
]:
    got = [f for f in run_db(ctx(MIG, src)) if f.rule == "DB-02"]
    check(f"DB-02 quiet on column width: {name}", got, [])

# But a real magic number in a filter must still fire.
for src, name in [
    ("$q->where('status', 2);", "where('status', 2)"),
    ("Model::where('tipe', 3)->get();", "where('tipe', 3)"),
    ("if ($row->status === 1) {", "status === 1"),
    ("$order->status = 4;", "status = 4;"),
]:
    got = [f for f in run_db(ctx("app/Models/Pesanan.php", src)) if f.rule == "DB-02"]
    check(f"DB-02 still fires on real code: {name}", len(got) > 0, True)

# A HTTP status code is transport, not a column.
check("DB-02 quiet on res.status === 404",
      [f for f in run_db(ctx("routes/web.js", "if (res.status === 404) return;"))
       if f.rule == "DB-02"], [])


# ------------------------------------------------------- DB-04 lifecycle only
# Lifecycle state as a human label is the thing worth flagging.
for src, name in [
    ("$table->string('status')->default('menunggu_pembayaran');", "status string"),
    ("$table->string('status_pesanan', 40);", "status_pesanan string"),
    ("$table->string('kondisi', 32);", "kondisi string"),
    ('stock_state varchar(32)', "stock_state varchar"),
]:
    got = [f for f in run_db(ctx(MIG, src)) if f.rule == "DB-04"]
    check(f"DB-04 catches lifecycle text: {name}", len(got) > 0, True)

# A discriminant column is not a lifecycle status. Text is correct here.
for src, name in [
    ("$table->string('tipe', 40);", "tipe = hero/tentang/proyek"),
    ("$table->string('kategori', 40);", "kategori"),
    ("$table->string('type', 40);", "type"),
]:
    got = [f for f in run_db(ctx(MIG, src)) if f.rule == "DB-04"]
    check(f"DB-04 quiet on discriminant: {name}", got, [])


# ------------------------------------------------------------- the other rules
# DB-01 still refuses native enums.
check("DB-01 catches $table->enum()",
      [f for f in run_db(ctx(MIG, "$table->enum('status', ['a','b']);"))
       if f.rule == "DB-01"] != [], True)

# DB-06 still refuses money as float.
check("DB-06 catches float price",
      [f for f in run_db(ctx(MIG, "$table->float('harga');"))
       if f.rule == "DB-06"] != [], True)

# DB-06 must not fire on a legitimate integer amount.
check("DB-06 quiet on unsignedBigInteger harga",
      [f for f in run_db(ctx(MIG, "$table->unsignedBigInteger('harga');"))
       if f.rule == "DB-06"], [])


print(f"{len(PASS)} passed, {len(FAIL)} failed")
for line in FAIL:
    print("  FAIL", line)
sys.exit(1 if FAIL else 0)
