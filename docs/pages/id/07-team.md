---
title: Untuk tim
slug: team
group: Mulai
order: 7
summary: Cara menggulirkan ke developer lain tanpa menyentuh semua repo sekaligus, dan siapa yang memutuskan saat agent berhenti dan bertanya.
---

# Menggulirkan ke tim

Ironclad bukan aturan yang dipaksakan dari atas. Ia satu perilaku kecil: sebelum
agent menulis kolom status, ia membaca repo itu dulu, dan berhenti kalau repo-nya
sudah tidak konsisten. Sisanya — kapan dipakai, di repo mana, dan gaya apa yang jadi
standar — keputusan kamu.

Halaman ini urutan yang paling sedikit menimbulkan keributan.

## Urutan yang disarankan

### 1. Satu repo pilot, bukan semua

Pilih repo yang paling sering bermasalah dengan status: yang laporannya butuh
`CASE WHEN`, atau yang migrasinya pernah ditambal dua gaya. Jangan yang paling besar,
dan jangan yang paling sepi.

Di repo itu, jalankan sekali:

```bash
cd repo-pilot
ironclad check
```

Itu hanya membaca. Kalau hasilnya bersih, repo itu terlalu rapi untuk jadi pilot —
pilih yang lain. Pilot yang berguna adalah yang **menghasilkan temuan**.

### 2. Isi keputusannya, jangan biarkan kosong

Installer sudah menanam default rumah (`status_code` + lookup + FK) untuk tabel baru.
Tapi repo pilot biasanya **sudah** punya gaya sendiri, dan gaya repo selalu menang.

Keputusan yang perlu kamu tulis di `.agent/standards.md` hanya satu kalimat: proyek
ini menyimpan status dengan cara apa, dan kenapa. Kalau repo sudah konsisten, cukup
tulis gaya yang sudah ada — bukan gaya default.

```bash
ironclad init      # hanya untuk mengunci keputusan ke git
```

Kalau file yang ditulis masih template kosong, ia akan diganti saat upgrade. Kalau
sudah kamu isi, ia tidak akan disentuh.

### 3. Satu developer mencoba dulu

Kirim ke **satu** orang, sebaiknya yang memakai agent berbeda darimu. Yang perlu
mereka lakukan hanya satu perintah:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} --mode house
```

`--mode house` yang membuat semua orang otomatis memakai gaya yang sama untuk tabel
baru. Tanpa flag itu, installer memakai `ask` — agent akan bertanya alih-alih memilih.

Lalu minta mereka buka repo pilot dan bertanya ke agent-nya:

> Sebelum bikin kolom status, aturannya apa?

Jawaban yang benar menyebut tiga hal: baca repo dulu, ikuti gaya yang ada, dan kalau
belum ada pakai `status_code` + lookup. Kalau agent hanya menjawab "pakai integer"
tanpa menyebut membaca repo, bloknya tidak termuat.

### 4. Baru sebar

Setelah satu orang berhasil, sebar perintah yang sama. Tidak ada konfigurasi per
repo, tidak ada yang perlu di-commit, kecuali kamu memang mau aturannya ikut git
lewat `ironclad init`.

## Saat agent berhenti dan bertanya

Ada dua jenis pertanyaan, dan hanya satu yang butuh jawabanmu.

**"Boleh saya tulis sekarang?"** — itu sopan, jawab saja.

**"Repo ini punya dua gaya status, mana yang jadi standar?"** — ini yang penting.
Agent sengaja berhenti karena memilih sendiri akan menambah gaya ketiga. Jawaban yang
kamu berikan hari itu menjadi standar repo tersebut. Tulis di `.agent/standards.md`
supaya agent berikutnya — dan orang berikutnya — tidak menanyakannya lagi.

Kalau kamu tidak tahu jawabannya, "ikuti yang paling banyak dipakai" adalah jawaban
yang sah. Yang tidak sah: diam, lalu membiarkan agent memilih.

## Yang perlu disepakati di awal

Tiga hal ini tidak ditentukan oleh alat, dan sebaiknya kamu putuskan sebelum menyebar:

- **Gaya status untuk repo baru** — default rumah sudah `status_code` + lookup. Kalau
  timmu lebih nyaman dengan `enum` native, ubah sekarang, bukan setelah sepuluh tabel.
- **Uang** — `numeric(14,2)` atau integer satuan terkecil. Dua-duanya sah; yang tidak
  boleh cuma `float`.
- **Repo lama** — dibiarkan apa adanya, atau diseragamkan perlahan. Rekomendasi:
  dibiarkan. Menulis ulang skema yang jalan untuk mengejar default adalah cara
  kehilangan satu akhir pekan dan mendapat satu bug.

## Kalau ada yang tidak bekerja

Sebelum melapor, minta satu hal dari orang itu:

```bash
ironclad version
```

Itu menyebut versi skill, lokasinya, dan ukuran blok yang terpasang. Tiga angka itu
memisahkan hampir semua masalah: versi lama, salah folder, atau blok tidak tertulis.

Kalau versinya benar tapi agent tetap tidak bertanya, berarti agent itu tidak memuat
file yang kita tulis. Itu perlu dilaporkan — jangan diasumsikan bekerja.
