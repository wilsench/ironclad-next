---
title: Preset — seberapa keras
slug: presets
group: Konsep
order: 11
summary: Empat tingkat penegakan. Ini yang menentukan apakah CI merah, dan yang membedakan "menegur" dari "menolak".
---

# Preset — seberapa keras aturannya

Preset tidak mengubah apa yang **diketahui** Ironclad. Ia hanya mengubah apa yang
**memblokir**. Repo lama dengan ratusan temuan akan mematikan gate di hari pertama
kalau semuanya merah — jadi tingkatnya bisa disetel.

> Bingung dengan **mode**? Itu pertanyaan berbeda: siapa yang memutuskan sebelum
> kode ditulis. Lihat [Mode](/modes/).

## Empat preset

| Preset | Memblokir | Hanya warning | Untuk |
|---|---|---|---|
| `legacy-friendly` | — | semua | repo tua dengan utang teknis |
| `coherence` | DB-08, API-07, SEC-01, SEC-02 | sisanya | **siapa saja** yang tidak mau dipaksa satu gaya |
| `balanced` | DB-01, DB-02, DB-04, API-07, SEC-02 | DB-03, DB-05…DB-08, API-01, API-02, SEC-01, SEC-03, ARCH-01, ARCH-02 | pekerjaan produk normal; default kantor |
| `strict` | semua | — | keuangan, kesehatan, sistem yang diaudit |

Angka nyata dari fixture yang sama (`examples/bad.sql`):

```
balanced           errors=6 warns=11
coherence          errors=5 warns=11
legacy-friendly    errors=0 warns=15
strict             errors=17 warns=0
```

Perhatikan `coherence`: ia punya **lebih sedikit** error daripada `balanced`, dan
itu maksudnya. Di preset itu enum tidak dihukum. Yang gagal hanya DB-08 — konsep
yang sama disimpan dua cara berbeda dalam satu proyek.

## Kapan memilih yang mana

**Kamu tidak setuju enum dianggap salah, dan repo-mu sudah konsisten.**
→ `coherence`. Hasilnya hijau. Itu benar, bukan bug.

**Kamu punya tim yang sudah sepakat memakai integer + lookup.**
→ `balanced` (default). Enum dan status-teks memblokir; sisanya warning.

**Repo-mu lama, campur, dan kamu baru mau mulai.**
→ `legacy-friendly` dulu. Semua dilaporkan, build tetap hijau. Naikkan setelah
baseline bersih.

**Sistemnya mengurus uang atau audit.**
→ `strict`. Uang sebagai float dan timestamp tanpa zona ikut memblokir.

## Default otomatis

Tidak ada pertanyaan. `ironclad init` tanpa argumen memakai `balanced`:

```
$ ironclad init
wrote   .agent/standards.yml (preset: balanced)
wrote   .agent/standards.md
wrote   scripts/check_schema.py + scripts/presets/
```

Perintah yang bertanya akan menggantung di CI dan di agent tanpa TTY — dan
perintah yang menggantung lebih buruk daripada pilihan yang bisa diubah.

## Memilih saat install

Kalau kamu ingin repo langsung memakai preset tertentu:

```bash
npx github:wilsench/ironclad#v{{VERSION}} --project . --preset strict
```

Atau belakangan, dari dalam repo:

```bash
ironclad init strict
```

## Mengubah setelah install

Pilihanmu hidup di `.agent/standards.yml` **di dalam repo**, bukan di dalam skill,
jadi ia ikut git dan terlihat di diff PR.

**1. Tulis ulang dari preset:**

```bash
ironclad preset strict
```

**2. Edit langsung — bisa di-review:**

```yaml
name: coherence
rules:
  DB-01: warn       # pemakaian enum dilaporkan, tidak diblokir
  DB-02: error
  DB-03: warn
  DB-04: warn       # teks berkode sah; hanya dilaporkan
  DB-05: warn
  DB-06: warn
  DB-07: warn
  DB-08: error      # satu-satunya yang memblokir: gaya campur
exceptions: []
```

**3. Sekali jalan, tanpa mengubah berkas:**

```bash
python3 scripts/check_schema.py . --preset coherence
```

## Urutan adopsi yang tidak menyakitkan

| Tahap | Preset | Yang terjadi |
|---|---|---|
| Minggu 1 | `legacy-friendly` | semua dilaporkan, build tetap hijau |
| Minggu 2–3 | `balanced` + gate hanya berkas yang berubah | temuan baru diblokir, utang lama dibiarkan |
| Setelah baseline bersih | `strict` | semua memblokir |

Melewati tahap pertama adalah cara tercepat membuat tim membenci alat ini.

## Preset sendiri

Buat `presets/tim.yml`:

```yaml
name: tim
title: Aturan internal kita
rules:
  DB-01: error
  DB-02: error
  DB-03: error
  DB-04: error
  DB-05: off        # proyek ini memang penuh flag biner
  DB-06: error
  DB-07: warn
  DB-08: error
exceptions:
  - migrations/2023_legacy_import.sql
boolean_allowlist:
  - is_active
  - is_deleted
```

```bash
python3 scripts/check_schema.py . --config presets/tim.yml
```

> **`off` bukan tombol bisu.** Mematikan satu aturan adalah keputusan yang
> di-review dan dicatat, bukan jalan pintas agar build hijau. Kalau alasannya
> tidak bisa ditulis dalam satu baris PR, berarti aturannya belum perlu dimatikan.

## Prioritas pembacaan

```
--config  >  --preset  >  .agent/standards.yml  >  preset bawaan
```

Yang paling kanan adalah jaring pengaman: kalau semua berkas hilang, checker tetap
jalan, bukan crash.
