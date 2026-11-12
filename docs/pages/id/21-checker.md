---
title: Checker
slug: checker
group: Referensi
order: 21
summary: Referensi lengkap check_schema.py — argumen, exit code, format JSON, apa yang dipindai dan apa yang tidak.
---

# Checker

`scripts/check_schema.py` — linter schema tanpa dependensi (stdlib Python saja, tidak butuh PyYAML).

## Penggunaan

```bash
python3 scripts/check_schema.py [paths…] [opsi]
```

| Opsi | Arti |
|---|---|
| `paths…` | file atau direktori; default `.` |
| `--preset NAME` | `balanced` · `coherence` · `strict` · `legacy-friendly` |
| `--config FILE` | config eksplisit, menimpa `--preset` |
| `--json` | keluaran mesin |
| `--strict` | eskalasi semua warn jadi error (flag lama) |
| `--list-presets` | tampilkan preset beserta hitungannya |

Urutan prioritas, dari paling lemah ke paling kuat:

```
builtin:balanced  <  .agent/standards.yml  <  --preset  <  --config
```

Berkas `.agent/standards.yml` **selalu** dibaca — `exceptions` dan
`boolean_allowlist` milik repo tetap berlaku walaupun kamu memberi `--preset`.
Yang ditimpa preset hanyalah tingkat keparahan per aturan. Sebuah berkas yang
hanya berisi `name: coherence` (persis yang ditulis `ironclad preset`) dibaca
sebagai preset tersebut, jadi keduanya sah: nama saja, atau aturan eksplisit.

## Exit code

| Kode | Arti |
|---|---|
| `0` | bersih, atau hanya warning pada preset yang tidak memblokir |
| `1` | ada error yang memblokir |
| `2` | salah pakai — preset tidak dikenal, config tidak ditemukan, tidak ada file |

Bisa dipakai langsung sebagai gate CI tanpa membungkusnya dengan `grep`.

## Keluaran manusia

```
bad.sql:4: [DB-01] ERROR SQL/prisma enum column; use integer code + lookup table (see DB-03)
bad.sql:6: [DB-04] ERROR status stored as text (`stock_state`); use smallint code + lookup table

preset: balanced (.agent/standards.yml)
1 file(s), 2 error(s), 2 warning(s)
```

Baris terakhir menyebut **dari mana** presetnya dibaca — penting saat dua orang mendapat hasil berbeda dan penyebabnya berkas config yang tertinggal.

## Keluaran JSON

```bash
python3 scripts/check_schema.py . --json
```

```json
{
  "preset": "balanced",
  "source": "preset:balanced",
  "files": 1,
  "findings": [
    {
      "rule": "DB-01",
      "severity": "error",
      "line": 4,
      "msg": "SQL/prisma enum column; use integer code + lookup table (see DB-03)",
      "file": "examples/bad.sql"
    }
  ],
  "errors": 2,
  "warnings": 2
}
```

Field `source` bisa berupa path berkas (`.agent/standards.yml`), nama preset (`preset:strict`), atau `builtin:balanced` kalau tidak ada config sama sekali.

## Apa yang dipindai

| Ekstensi | Yang dibaca |
|---|---|
| `.sql` | `CREATE TABLE`, `ALTER TABLE … ADD COLUMN`, `INSERT` (untuk melewati literal) |
| `.php` | migration Laravel: `$table->enum()`, `$table->string('status')`, `$table->tinyInteger()` |
| `.prisma` | `enum` block, tipe kolom, `@relation` |

File yang dilewati otomatis: `node_modules`, `.git`, `vendor`, `dist`, `build`, dan file berukuran tidak wajar.

## Apa yang **tidak** terdeteksi

Ini penting, karena checker yang dipercaya berlebihan lebih berbahaya daripada tidak ada checker.

- **Query builder ORM** — `Order::where('status_code', 3)` di `app/` tidak dibaca; hanya berkas dengan ekstensi di atas.
- **SQL yang dirangkai runtime** — string yang dibangun dari variabel tidak bisa dinilai tanpa mengeksekusi kode.
- **Tipe di TypeScript** — `type Status = 1 | 2 | 3` tidak terlihat sama sekali.
- **Kesalahan semantik** — kolom bernama `status_code` yang berisi kode salah tetap lolos secara sintaksis.
- **Konvensi lintas-berkas** — lookup table di berkas A dan FK di berkas B dinilai per berkas untuk DB-03.

Untuk semua itu, reviewer manusia tetap lapis terakhir. Checker menangkap pola yang mahal dan berulang, bukan menggantikan penilaian.

## Menulis aturan sendiri

Lihat [Memperluas](/extending/) — cara menambah domain aturan (API, security) beserta pemeriksanya.

## Hasil uji pada fixture

```
examples/good.sql            balanced 0 error 0 warn   exit 0
                             strict   0 error 0 warn   exit 0
examples/bad.sql             balanced 2 error 2 warn   exit 1
                             legacy   0 error 4 warn   exit 0
examples/bad_migration.php   2 temuan
examples/bad.prisma          1 temuan
```

Angka-angka ini ikut diuji di CI repo ini lewat `.github/workflows/engineering-standards.yml`, jadi kalau checker-nya rusak, CI yang memberi tahu lebih dulu — bukan penggunanya.
