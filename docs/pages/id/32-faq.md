---
title: FAQ
slug: faq
group: Operasional
order: 32
summary: Pertanyaan yang paling sering muncul, dijawab langsung tanpa berputar.
---

# FAQ

## Apakah saya harus menjalankan Python?

**Untuk memasang: ya, Python 3.8+.** Bukan untuk mengunduh — installer-nya bash + curl — tapi untuk menulis blok aturan ke `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`. Kalau `python3` tidak ada, installer sekarang berhenti dengan exit 3 dan mengatakannya, bukan mencetak "installed" di atas folder kosong.

`python3` sudah terpasang di macOS, hampir semua distro Linux, dan Termux. Kalau di mesinmu belum ada: `sudo apt install python3` (Debian/Ubuntu), `brew install python3` (macOS).

**Untuk checker: ya**, syarat yang sama. Checker-nya sendiri opsional — kalau kamu hanya ingin agent membaca aturannya, cukup skill + `.agent/standards.md`.

## Apakah skill aktif otomatis setiap kali agent jalan?

Ya, tapi **bukan berarti selalu dipakai**. Setiap turn agent melihat daftar nama + deskripsi skill. Ia memuat `SKILL.md` penuh hanya kalau tugasnya cocok.

Jadi: tidak ada perintah yang perlu dijalankan, dan tidak ada pertanyaan "mau pakai skill ini?". Agent memutuskan sendiri, seperti memilih alat.

Kalau kamu ingin memastikan, sebut namanya: `pakai skill ironclad`.

## Kalau tidak mau sepanjang ini, cukup satu perintah?

Ya:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}}
```

Itu saja. Tidak ada langkah kedua — agent sudah bertanya sendiri di repo mana pun.

Kalau kamu ingin aturannya ikut git supaya seluruh tim dan CI memakai jawaban yang sama:

```bash
cd repo-kamu && ironclad init
```

Satu perintah, tanpa clone, tanpa baca dokumen — dan tanpa `ironclad init` kecuali kamu ingin aturannya ikut git.

## Installer ini bisa untuk selain Hermes?

Ya, dan itu target utamanya. Enam target: Hermes, Claude Code, Codex, Cursor, opencode, Antigravity. Formatnya standar Agent Skills (`SKILL.md`), bukan format khusus Hermes.

```bash
npx github:wilsench/ironclad-next#v{{VERSION}}  --all              # semua agent yang terdeteksi
npx github:wilsench/ironclad-next#v{{VERSION}}  --target claude
npx github:wilsench/ironclad-next#v{{VERSION}}  --target gemini    # Antigravity global
npx github:wilsench/ironclad-next#v{{VERSION}}  --target opencode
```

## Bisa langsung pakai `wilsench/ironclad-next`?

Untuk Hermes, ya — begitu repo GitHub-nya terbit:

```bash
hermes skills install wilsench/ironclad-next/skills/ironclad
```

Untuk agent lain, pakai `npx github:wilsench/ironclad-next#v{{VERSION}}` — itu menarik paket langsung dari repo GitHub tanpa publish ke npm. Kalau tidak ada Node, mirror `install.sh` di `wilsench.my.id` menjalankan kode yang sama persis.

## Apakah `curl | bash` aman?

Installer-nya 180 baris bash dan bisa kamu baca dulu:

```bash
curl -fsSL https://wilsench.my.id/ironclad-next/install.sh | less
```

Yang dilakukannya: mengunduh 10 berkas teks, menyalinnya ke satu folder skill, dan — hanya kalau kamu memberi `--project` — menulis `.agent/` di repo yang kamu sebut. Tidak ada `sudo`, tidak mengubah shell profile, tidak menyentuh skill lain.

## Apakah bisa dipakai tanpa Git?

Bisa. Skill hanya folder berisi berkas. Checker hanya butuh path. Yang hilang hanya dua hal: `.agent/standards.md` tidak punya riwayat perubahan, dan tidak ada CI yang menjalankannya.

## Kenapa tidak pakai `enum` saja?

Karena menambah satu nilai enum berarti `ALTER TABLE`. Di MySQL, pada tabel besar, itu mengunci tabel. Status bisnis selalu tumbuh, dan tiap pertumbuhan tidak seharusnya jadi acara migrasi.

Tapi `enum` **tidak dilarang total**. Kalau nilainya memang disengaja dan hanya berubah lewat review kode, tulis alasannya di komentar migrasi — pada `balanced` itu diterima.

## Kalau kodenya `88`, `99`, bukan 0, 1, 2?

Sah sepenuhnya. Kode tidak harus berurutan dan tidak harus mulai dari nol. Yang membuatnya aman: kodenya terdaftar di lookup table (sehingga `87` ditolak database) dan dipakai lewat konstanta bernama di kode aplikasi.

Menyisakan blok — `8x` untuk stok, `9x`/`99x` untuk keberangkatan — membuat angka mentah masih bisa dibaca saat muncul di hasil query enam bulan kemudian.

## Apakah ini menggantikan review code?

Tidak. Checker menangkap pola sintaksis; ia tidak tahu apakah `status_code = 7` secara bisnis benar. Ia mengurangi pekerjaan review yang berulang, bukan menggantikannya.

## Kalau aturan perusahaan kami berbeda?

Itu intinya. Ubah `.agent/standards.md` dan `.agent/standards.yml` di repo kamu. Skill-nya tidak perlu diubah, dan tidak perlu install ulang. Aturan yang tidak cocok bisa di-set `warn` atau `off` — asal alasannya masuk PR.

## Apakah ada auto-update?

Belum. `hermes skills update` memakai URL saat install; agent lain perlu menjalankan ulang installer. Belum ada changelog bertanda versi. Kalau kamu mengubah aturan, yang perlu dibagikan adalah `.agent/standards.md` di repo — itu ikut git dan otomatis sampai ke semua orang.

## Berapa biaya konteksnya?

`SKILL.md` sekitar 7 KB, tapi agent hanya memuatnya saat tugasnya cocok. Yang selalu ada di konteks hanyalah satu baris deskripsi. Referensi (`database.md`, `presets.md`) hanya dibaca kalau agent perlu detail.

## Kalau saya sudah punya skill atau aturan lain, apa yang terjadi?

Tidak ada yang tertimpa. Installer hanya menambahkan satu blok berpagar di **akhir**
file konfigurasi yang sudah ada:

```
<!-- ironclad:begin v1 -->  ...  <!-- ironclad:end -->
```

Aturan, gaya, atau skill lain di file yang sama tetap utuh di tempatnya — baik sebelum
maupun sesudah blok. Yang dihapus hanya isi di antara dua penanda itu, dan hanya kalau
kamu menjalankan installer lagi atau `--uninstall`.

Tiga hal yang sudah diuji:

- **Install dua kali** — tidak menghasilkan blok ganda (`unchanged`).
- **Uninstall** — file kembali persis seperti sebelumnya, aturan orang lain utuh,
  termasuk jumlah barisnya.
- **`ironclad init` di repo yang sudah punya `AGENTS.md` dan `.agent/standards.md`** —
  aturan tim tetap ada, dan `standards.md` yang sudah kamu isi tidak diganti.

Satu hal yang bisa dianggap "gangguan": blok itu ikut terbaca di **setiap sesi** agent,
untuk semua repo, karena memang itu maksudnya. Ukurannya ~1.150 karakter. Kalau itu
mengganggu, lepas dengan `--uninstall`; skill dan alat lainnya tetap bisa dipakai
manual.

## Saya tidak setuju enum dianggap salah. Masih bisa pakai?

Bisa. Pakai preset `coherence`:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} check . --preset coherence
```

Di preset itu tidak ada gaya yang dihukum: `enum`, teks berkode, dan integer + lookup
semuanya diterima. Yang **gagal** hanya satu hal — konsep yang sama disimpan dua cara
berbeda dalam satu proyek. Itu satu-satunya tesis Ironclad; sisanya selera, dan selera
kamu tidak perlu sama dengan siapa pun.

## Bisa coba tanpa install?

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} check .
```

Itu menjalankan pemeriksa dan berhenti. Tidak ada file yang ditulis, tidak ada
konfigurasi agent yang disentuh. Kalau hasilnya bersih, berarti repo-mu memang konsisten
— dan kamu tidak perlu memasang apa pun.
