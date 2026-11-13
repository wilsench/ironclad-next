---
title: Mode — ask atau house
slug: modes
group: Konsep
order: 9
summary: Siapa yang memutuskan gaya status saat repo belum punya jawaban. Satu flag saat install, dan itu yang membedakan alat netral dari alat milik satu tim.
---

# Mode — siapa yang memutuskan

Ini pertanyaan yang paling sering luput, dan penyebab dua orang memakai alat yang
sama dengan hasil berbeda:

> Repo ini belum punya tabel dengan kolom status. Kamu minta agent menambah tabel
> `invoices`. **Siapa yang memutuskan statusnya disimpan sebagai apa?**

Ada tiga jawaban yang mungkin, dan hanya dua yang kami dukung:

- agent menebak → **tidak**, itu sumber masalahnya
- agent bertanya → mode **`ask`**
- agent memakai keputusan tim → mode **`house`**

## Bedanya satu baris

| | `ask` (default) | `house` |
|---|---|---|
| Repo sudah punya gaya | ikuti gaya itu | ikuti gaya itu |
| Repo punya dua gaya | berhenti, sebut keduanya | berhenti, sebut keduanya |
| Repo belum punya apa pun | **bertanya dulu** | **langsung `status_code` + lookup** |
| Cocok untuk | siapa saja, repo apa pun | satu tim dengan keputusan yang sama |

Perhatikan baris kedua: **`house` tidak memaksa repo lama menyeragamkan gaya.**
Kalau repo-mu sudah konsisten memakai enum, `house` tetap mengikuti enum. Yang
ditanamkan bukan "integer di mana-mana", tapi "kalau belum ada keputusan, ini
keputusan kami".

## Memasang

```bash
# netral — agent akan bertanya kalau belum ada apa pun
npx github:wilsench/ironclad-next#v{{VERSION}}

# kantor — agent langsung memakai gaya yang disepakati
npx github:wilsench/ironclad-next#v{{VERSION}} --mode house
```

Tanpa flag, hasilnya `ask`. Itu disengaja: orang yang menemukan alat ini dari
mesin pencari tidak sedang menyetujui pilihan database orang lain.

## Yang ditulis `house` ke blok agent

Bagian ini hanya muncul di mode `house`:

```markdown
- **no status anywhere yet** -> use the house default. Do not ask.
  `status_code SMALLINT NOT NULL` + lookup table (`code` PK, `label`) + FK
  from the column, plus named constants in code. Any integer codes are fine
  (10/20/30, 1/2/3) as long as every code exists in the lookup table and is
  never reused.
  Say "house default: status_code + lookup" in one line, then write it.
```

Tiga hal yang diperhatikan dari bunyi itu:

- **"Do not ask"** — agent tidak menggantung menunggu jawaban yang tidak akan
  datang di sesi otomatis.
- **"Any integer codes are fine"** — kode tidak harus kelipatan 10. `88` dan `99`
  sah, asal terdaftar di lookup dan dijaga FK.
- **"Say it in one line"** — kamu tetap tahu keputusan apa yang diambil, tanpa
  dialog. Satu baris di jawaban agent, bukan pertanyaan.

## Mengubah mode setelah install

Mode disimpan di berkas, bukan hanya di lingkungan shell. Artinya:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} --mode ask     # turunkan jadi netral
npx github:wilsench/ironclad-next#v{{VERSION}} --mode house   # naikkan jadi berpihak
```

Installer membaca mode yang tersimpan lebih dulu. Mesin `house` yang di-install
ulang tanpa flag **tetap** `house` — tidak turun diam-diam hanya karena kamu lupa
menyertakan flag.

## Mode bukan pengganti keputusan

`house` hanya mengisi kekosongan. Ia tidak:

- menyatukan dua gaya yang sudah ada (itu pekerjaan migrasi, bukan installer)
- mengubah tabel lama
- mengalahkan `.agent/standards.md` yang sudah kamu tulis — berkas itu selalu
  menang, karena keputusan proyek lebih spesifik daripada default alat

Kalau kamu ingin **memaksa** keseragaman di repo yang sudah campur, itu urusan
[Preset](/presets/) dan `DB-08`, bukan mode.

## Untuk orang yang tidak memakai AI agent

Mode tidak relevan kalau kamu tidak memakai agent — tidak ada yang perlu
diberi tahu. Yang tetap berguna: `check` untuk melihat apakah repo campur, dan
`init` untuk mencatat keputusan tim. Lihat [Checker](/checker/).
