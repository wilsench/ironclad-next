---
title: Quickstart
slug: quickstart
group: Mulai
order: 5
summary: Dua menit dari nol sampai checker hijau di satu repo, tanpa mengganggu pekerjaan lain.
---

# Quickstart

Dua menit. Tidak ada pertanyaan yang harus dijawab, tidak ada berkas yang harus
diedit tangan.

## 1. Pasang

```bash
npx github:wilsench/ironclad#v{{VERSION}}
```

Selesai. Skill ada di `~/.agents/skills/ironclad/`, perintah `ironclad` ada di
`~/.local/bin/`.

## 2. Lihat dulu, jangan ubah apa pun

```bash
cd repo-kamu
ironclad check
```

Ini hanya membaca. Keluarannya seperti ini:

```
bad.sql:4: [DB-01] ERROR SQL/prisma enum column; use integer code + lookup table (see DB-03)
bad.sql:6: [DB-04] ERROR status stored as text (`stock_state`); use smallint code + lookup table

preset: balanced (preset:balanced)
1 file(s), 2 error(s), 2 warning(s)
```

Kalau repo kamu besar, jangan panik melihat jumlahnya. Itu gunanya langkah 4.

## 3. Jadikan permanen

```bash
ironclad init
```

Menulis empat hal, semuanya untuk di-commit:

```
wrote   .agent/standards.yml (preset: balanced)
wrote   .agent/standards.md
wrote   scripts/check_schema.py + scripts/presets/
```

```bash
git add .agent scripts
git commit -m "chore: adopt ironclad standards"
```

Sejak commit itu, agent membaca `.agent/standards.md` sebelum menulis DDL, dan CI
membaca `.agent/standards.yml` untuk memutuskan apa yang memblokir. Satu sumber,
dua pembaca.

## 4. Pilih tingkat penegakan yang tidak membuat tim matikan CI

Ini bagian yang paling sering dilewatkan orang, dan penyebab utama alat seperti
ini dicabut dalam seminggu.

| Repo kamu | Mulai dari | Kenapa |
|---|---|---|
| repo baru, atau sudah bersih | `strict` | semua memblokir, tidak ada utang |
| repo jalan, utang wajar | `balanced` (default) | enum & status-teks memblokir, sisanya warning |
| repo konsisten pakai enum, tidak mau diubah | `coherence` | tidak ada gaya yang dihukum; hanya gaya campur yang gagal |
| repo tua, ratusan temuan | `legacy-friendly` | semua warning, build tetap hijau |

```bash
ironclad preset coherence         # repo konsisten: hijau, tanpa memaksa gaya
ironclad preset legacy-friendly   # repo tua: pasang dulu, bersihkan pelan-pelan
ironclad preset balanced          # setelah baseline bersih
ironclad preset strict            # setelah tidak ada warning tersisa
```

Naik satu tingkat setelah jumlah temuan turun, bukan setelah tanggal tertentu.
Perbedaan lengkap keempatnya ada di [Preset](/presets/).

## 5. Buktikan gate-nya benar-benar bekerja

```bash
ironclad drill --selftest
```

Satu perintah, memakai contoh yang sudah pasti. Keluarannya panjang — puluhan baris
`PASS` — dan yang penting hanya satu hal di baris terakhir: apakah ada `FAIL`.

```
  PASS  enum blocked in the default preset
  PASS  integer + lookup + fk accepted
  PASS  text label blocked in the default preset
  PASS  money as float blocks under strict
  PASS  naive timestamp blocks under strict
  PASS  mixed project flagged (DB-08) — the two-developer case
  PASS  consistent project stays silent (no false alarm)
```

Kalau ada yang `FAIL`, jangan lanjut: gate-nya rusak, dan semua hijau setelahnya
tidak berarti apa-apa.

Perhatikan baris keempat dan kelima: pada preset `balanced`, uang-float dan
timestamp tanpa zona **hanya warning**, tidak memblokir. Itu disengaja — tapi
artinya jangan mengira `balanced` menangkap semuanya. Naik ke `strict` kalau
kamu memang butuh semuanya memblokir.

## 6. Buktikan agent-nya benar-benar paham

Ini pertanyaan yang berbeda dari langkah 5. Gate yang bekerja tidak menjamin
agent membaca policy — dan agent yang hari ini benar bisa lain besok.

```bash
ironclad drill --prompt
```

Perintah itu mencetak satu tugas untuk ditempel ke agent kamu — dan sengaja
**tidak** menyebut integer, enum, atau aturan apa pun. Kalau agent memang
memahami policy-nya, ia akan sampai ke jawaban yang sama tanpa disuapi.

Lalu nilai hasilnya:

```bash
ironclad drill answer.sql
```

```
  PASS  policy check                           clean
  PASS  no enum column                         none
  PASS  lookup table for status                order_status
  PASS  status column has a foreign key        status_code → order_status
  PASS  statuses seeded as data (not schema)   1 INSERT statement(s)
  PASS  money is integer minor units           ok
  PASS  timestamps carry a timezone            ok
  PASS  cites a rule ID                        DB-01, DB-03, DB-08
8/8 criteria
```

Penilai ini tidak memanggil model. Alat yang menilai model dengan bertanya ke
model lain hanya menilai dirinya sendiri. Semua kriteria di atas diperiksa dari
teks SQL-nya: ada `enum` atau tidak, ada tabel lookup atau tidak, kolom status
punya `REFERENCES` atau tidak, status di-seed sebagai data atau tidak.

**Kalau hasilnya di bawah 8/8**, urutan yang benar:

1. Pastikan agent benar-benar memuat skill — minta ia mengutip `.agent/standards.md`.
2. Minta ia menyebut ID aturan yang diikuti. Agent yang tidak bisa menyebut
   aturannya sedang menebak.
3. Pasang checker di CI. Skill itu nasihat; gate adalah satu-satunya yang tidak
   bisa dibantah saat tengah malam.

Lalu buka PR yang menambah satu kolom `enum` — PR itu harus merah di GitHub.
Kalau tidak merah, CI-nya belum benar, bukan checkernya.

## 7. Mengetahui ada versi baru

```bash
ironclad update
```

Kalau kamu sudah di versi terbaru, ia bilang begitu dan berhenti. Kalau ada yang
lebih baru, ia menampilkan apa yang berubah dalam bahasa biasa, lalu menawarkan
empat pilihan:

```
installed: 0.9.4
latest:    0.9.5
A newer version is available.

What changed since 0.9.4:
  1 change: 1 docs

  • three layers had the wrong first layer

What do you want to do?
  1) Install 0.9.5 now  (recommended)
  2) Stay on 0.9.4 for now  (nothing changes)
  3) Show me what changed
  4) Stop asking on this machine
Choose 1-4 [2]:
```

- **1** memasang versi baru lewat perintah yang sama seperti saat install pertama.
  Blok agent diganti di tempat, `standards.md` yang sudah kamu isi tidak disentuh.
- **2** tidak mengubah apa pun. Pilihan ini tersimpan, jadi kamu tidak ditanya lagi
  hari itu.
- **3** menampilkan ulang daftar perubahan, lalu kembali ke menu.
- **4** mematikan pemeriksaan selamanya di mesin itu.

Pemeriksaan ini tidak pernah memblokir: ia hanya jalan paling sering sekali per 24
jam, tidak pernah di pipe/CI, dan tidak pernah mengubah exit code `ironclad check`.
Kalau kamu mau melihat status tanpa diprompt:

```bash
ironclad update --check    # 0 = terbaru, 10 = ada yang lebih baru
ironclad update --notes    # hanya daftar perubahannya
```

## Selesai

Yang tersisa hanya kebiasaan: `ironclad check` sebelum commit, dan biarkan CI
menjalankan hal yang sama pada setiap PR.

Kalau ada yang tidak berjalan seperti di halaman ini, lihat
[Troubleshooting](/troubleshooting/) — disusun dari gejala, bukan dari teori.
