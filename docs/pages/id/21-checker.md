---
title: Checker
slug: checker
group: Referensi
order: 21
summary: Referensi lengkap check_schema.py — argumen, exit code, format JSON, apa yang dipindai dan apa yang tidak.
---

# Checker

`scripts/check_schema.py` adalah pintu masuk ke `ironclad_core/`, paket kecil tanpa
dependensi (stdlib Python saja, tidak butuh PyYAML). Ia membaca berkas skema dan
kode sumber di empat domain — lihat [Aturan](/rules/) untuk daftar terkini.

Pintu masuknya sengaja tetap satu berkas: repo yang menyalin checker lewat
`--with-checker` masih bisa menjalankan `python3 scripts/check_schema.py`, dan
mesinnya ikut sebagai `scripts/ironclad_core/`.

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

Tiga perintah lain membaca lapisan config yang sama dengan `check`, jadi yang
mereka tampilkan adalah yang benar-benar akan dijalankan:

```bash
ironclad doctor                 # kenapa ini tidak bekerja seperti yang saya harapkan?
ironclad rules                  # semua aturan dan keparahan efektifnya
ironclad rules explain SEC-01   # apa yang dicari, dan apa yang menolak ia putuskan
```

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
| `3` | instalasinya sendiri rusak (mesin tidak ditemukan) |

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
| `.js` `.ts` `.tsx` `.py` dll. | deklarasi rute (API), kredensial (SEC), graf impor (ARCH) |

Daftar itu bukan keputusan inti: tiap domain mendeklarasikan sendiri ekstensi yang
ia klaim, dan mesin menggabungkannya. Menambah domain berarti menambah berkas,
bukan mengubah mesin.

File yang dilewati otomatis: `node_modules`, `.git`, `vendor`, `dist`, `build`,
`coverage`, virtualenv, dan pohon dependensi bersarang.

## Apa yang **tidak** terdeteksi

Ini penting, karena checker yang dipercaya berlebihan lebih berbahaya daripada tidak ada checker.

- **Query builder ORM** — `Order::where('status_code', 3)` tidak dinilai sebagai
  pelanggaran skema; ia hanya dibaca oleh domain API/arsitektur.
- **SQL yang dirangkai runtime** — string yang dibangun dari variabel tidak bisa dinilai tanpa mengeksekusi kode.
- **Tipe di TypeScript** — `type Status = 1 | 2 | 3` tidak terlihat sama sekali.
- **Kesalahan semantik** — kolom bernama `status_code` yang berisi kode salah tetap lolos secara sintaksis.
- **Sebagian konvensi lintas-berkas** — DB-08 membandingkan gaya status seluruh
  proyek dan ARCH-01 membangun graf impor, tapi keduanya tidak tahu bahwa lookup
  table-mu ada di migration lain dan di-join di tempat lain.

Untuk semua itu, reviewer manusia tetap lapis terakhir. Checker menangkap pola yang mahal dan berulang, bukan menggantikan penilaian.

## Menulis aturan sendiri

Lihat [Memperluas](/extending/) — cara menambah aturan ke domain yang ada, atau
membuat domain baru beserta aturannya.

Sebelum menulis aturan, ukur dulu: jalankan pada repo nyata dan hitung apa yang
akan ia laporkan. Tiga aturan yang diusulkan untuk proyek ini gugur setelah
diukur — termasuk satu yang menyala di 6 dari 7 controller Laravel sungguhan.

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
