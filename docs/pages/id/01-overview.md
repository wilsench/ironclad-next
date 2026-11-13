---
title: Apa ini, untuk siapa
slug: overview
group: Mulai
order: 1
summary: Satu halaman tanpa jargon — masalah apa yang diselesaikan, apa yang kamu putuskan sendiri, dan apa yang tidak perlu kamu sentuh.
---

# Ironclad, tanpa jargon

**Ironclad menjaga satu proyek tetap konsisten saat lebih dari satu orang — atau
lebih dari satu AI — menggarap bagian database-nya.**

Bukan aplikasi. Bukan layanan berlangganan. Bukan pengganti code review. Isinya
satu berkas pemahaman yang dibaca agent sebelum menulis kode, satu berkas
keputusan yang ikut git, dan satu pemeriksa yang bisa kamu pakai kalau mau.

## Mulai dari mana

| Kalau kamu… | Baca |
|---|---|
| **bukan programmer** — kamu memesan atau mengawasi pekerjaan ini | lanjut baca halaman ini, lalu [Untuk tim](/team/) |
| **developer, ingin coba dulu tanpa memasang apa pun** | [Coba tanpa install](#coba-tanpa-install) di bawah |
| **developer, sudah yakin mau pakai** | [Quickstart](/quickstart/) |
| **developer, ingin tahu kenapa desainnya begitu** | [Tiga lapis](/three-layers/) lalu [Mode](/modes/) |

## Masalahnya: dua developer, dua gaya

Ini bukan cerita tentang AI. Ini cerita tentang tim.

Satu proyek. Tiga developer. Ketiganya menyentuh database.

Developer A menyimpan status pesanan sebagai **enum**:

```sql
status ENUM('baru', 'dibayar', 'dikirim')
```

Developer B menyimpan hal yang sama sebagai **integer**:

```sql
status_code smallint NOT NULL
```

Dua-duanya jalan. Dua-duanya lolos review, karena masing-masing masuk akal kalau
dilihat sendirian. Yang tidak ada: keputusan bersama tentang mana yang dipakai
proyek ini.

Enam bulan kemudian, satu tabel enum, tabel lain integer, tabel ketiga teks
bebas. Laporan harus menulis tiga query untuk hal yang sama. Saat klien minta
status baru, developer C harus tahu dulu tabel mana yang pakai cara apa.

Tidak ada yang salah. Yang hilang cuma satu: **keputusan yang tertulis dan
dibaca semua orang sebelum mulai.** AI mempercepat hilangnya keputusan itu —
ia menulis dalam hitungan detik, di banyak berkas, dan tidak pernah bertanya
"proyek ini biasanya pakai cara yang mana?"

## Empat hal yang bisa kamu setel

Ironclad punya empat bagian. Empat-empatnya bisa dipakai terpisah, dan tidak ada
yang wajib.

**1. Pemahaman yang menempel di agent.**
Saat install, satu blok pendek ditulis ke konfigurasi global agent yang ada di
komputermu. Blok itu dibaca di awal setiap sesi, di repo mana pun: *baca repo
dulu, ikuti gaya yang sudah ada, jangan tambah gaya ketiga.* Ini bagian yang
membuat agent berhenti bertanya hal yang salah dan mulai mengikuti proyeknya.

**2. Keputusan yang ikut git.**
`.agent/standards.md` berisi keputusan yang sudah diambil tim. Bukan preferensi
satu orang — kesepakatan yang bisa dikutip di review PR, dan dibaca anggota baru
di hari pertama.

**3. Seberapa keras aturannya — *preset*.**
Empat tingkat, dari "semua warning" sampai "semua memblokir". Ini yang
menentukan apakah CI merah. Lihat [Preset](/presets/).

**4. Siapa yang memutuskan saat repo belum punya jawaban — *mode*.**
Dua pilihan: `ask` (agent bertanya) atau `house` (agent langsung memakai gaya
kantor). Ini yang membedakan "alat netral untuk siapa saja" dari "alat milik satu
tim". Lihat [Mode](/modes/).

Preset dan mode sering tertukar. Bedanya satu kalimat:

> **Mode** menentukan apa yang terjadi sebelum keputusan ada.
> **Preset** menentukan apa yang terjadi setelah kode ditulis.

## Ironclad punya pendapat, dan kamu tidak harus ikut

Kami condong ke **integer + lookup table** untuk status. Alasannya teknis, bukan
selera: menambah nilai enum berarti `ALTER TABLE` yang bisa mengunci tabel;
menambah kode integer berarti menambah satu baris data. Kode `88` aman selama
`88` terdaftar di lookup dan dijaga foreign key; `87` ditolak database.

Tapi ini **pendapat**, bukan hukum. Kalau kamu sudah konsisten memakai enum dan
tidak mau diubah, pakai preset `coherence`: tidak ada gaya yang dihukum di sana.
Yang gagal hanya satu hal — konsep yang sama disimpan dua cara berbeda dalam satu
proyek. Itu satu-satunya klaim yang bisa kami bela untuk siapa pun, dan itu juga
persis masalah yang dihadapi kantor kami.

## Coba tanpa install

```bash
npx github:wilsench/ironclad#v{{VERSION}} check .
```

Menjalankan pemeriksa, mencetak temuan, lalu berhenti. **Tidak menulis berkas,
tidak menyentuh konfigurasi agent.** Kalau hasilnya bersih, repo-mu sudah
konsisten dan kamu tidak perlu memasang apa pun.

Kalau kamu ingin mencoba pandangan "netral" — yang tidak menganggap enum salah:

```bash
npx github:wilsench/ironclad#v{{VERSION}} check . --preset coherence
```

## Kalau kamu bukan yang menulis kode

Kamu tetap bisa memakai ini, dan kamu tidak perlu membaca satu baris pun kode.

**Kirim halaman ini ke developer kamu.** Minta mereka menjalankan dua perintah
di [Quickstart](/quickstart/), lalu commit hasilnya.

**Setelah itu ajukan empat pertanyaan ini.** Jawabannya menunjukkan apakah ini
benar-benar dipasang atau cuma dijanjikan:

1. **"Repo ini sudah konsisten atau campur?"** — jawaban yang benar menyebut
   angka temuan, bukan "sudah beres".
2. **"Preset apa yang dipakai?"** — salah satu dari `legacy-friendly`,
   `strict`, `balanced`, atau `coherence`. Kalau jawabannya "apa itu preset",
   berarti belum dijalankan.
3. **"Pull request yang melanggar benar-benar gagal?"** — kalau belum pernah
   diuji dengan PR sungguhan, gate-nya belum terbukti bekerja.
4. **"Kalau ada tabel baru, siapa yang memutuskan gaya statusnya?"** — jawaban
   yang baik menyebut satu nama berkas (`.agent/standards.md`) atau satu mode
   (`house`). Jawaban "tergantung developer-nya" berarti masalahnya masih ada.

**Yang tidak perlu kamu pelajari:** cara kerja pemeriksa, apa itu foreign key,
atau isi berkas YAML-nya.

## Yang tidak dilakukan Ironclad

- **Bukan pengganti programmer.** Tidak menulis fitur, tidak memperbaiki bug.
- **Bukan pengganti review.** Ia menangkap pola; ia tidak tahu apakah logika
  bisnismu benar.
- **Bukan audit keamanan.** Ia memeriksa tiga hal yang bisa dibuktikan dari
  berkas — kredensial di berkas yang bisa ikut terkirim git, kredensial yang
  ditulis langsung di kode, dan `.env.example` yang sudah melenceng dari `.env`.
  Ia tidak menemukan celah kontrol akses, injeksi, atau apa pun yang butuh
  aplikasi berjalan.
- **Tidak mengubah tampilan aplikasi.** Tidak ada hubungannya dengan desain.
- **Tidak mengirim data ke mana pun.** Semuanya berjalan di komputermu sendiri.

## Batas jujurnya

- **Pemeriksanya mencocokkan pola, bukan memahami kode.** Ia bisa salah menandai
  yang benar dan melewatkan yang salah. Manusia tetap lapis terakhir.
- **Cakupannya sempit dengan sengaja.** Enam belas aturan di empat domain — cara
  menyimpan status, uang, dan waktu; cara endpoint menjawab; apa yang bocor; dan
  bagaimana modul saling bergantung. Bukan dua ratus aturan. Alat yang mencoba
  menangkap segalanya kalah dari linter khusus, dan tak ada yang memasangnya dua
  kali.
- **Beberapa aturan gugur setelah diukur.** "Controller tidak boleh menyentuh
  model" menyala di 6 dari 7 controller Laravel sungguhan. Aturan itu tidak ada
  di alat ini.
- **Framework yang belum didukung akan berhenti dengan jujur** (`exit 2`), bukan
  berpura-pura hijau.
- **Ia tidak bisa memaksa orang membaca.** Kalau CI tidak dipasang dan
  `.agent/standards.md` diabaikan, tidak ada yang menangkap. Yang membuatnya
  bekerja adalah gate, bukan niat baik.
- **Belum ada pengguna di luar tim kami.** Kami belum bisa bilang ini membantu
  orang lain — hanya bahwa ia menyelesaikan satu masalah nyata di sini.
- **Belum ada pembaruan otomatis.** Untuk versi baru, jalankan ulang installer.

## Arah selanjutnya

| Kalau kamu… | Baca |
|---|---|
| ingin tahu istilah yang dipakai di sini | [Kamus](/kamus/) |
| ingin memasang sekarang | [Pasang](/install/) |
| ingin tahu bedanya mode dan preset | [Mode](/modes/) · [Preset](/presets/) |
| ingin melihat langkah lengkapnya | [Quickstart](/quickstart/) |
| ingin tahu kalau ada versi baru | [Memperbarui](/update/) |
| ingin tahu aturan apa saja yang diperiksa | [Aturan](/rules/) |
| ingin tahu kenapa alat seperti ini sering dicabut | [Tiga lapis](/three-layers/) |
