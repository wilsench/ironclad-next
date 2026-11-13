# Phase 5 — DX

**Status:** selesai dan terverifikasi. Tiga perintah baru, satu gerbang yang
dijanjikan roadmap, dan empat bug yang semuanya muncul saat perintah itu dipakai
pada repo nyata.

---

## 1. Gerbang yang dijanjikan

> `init` pada repo dengan `.agent/` yang sudah ada **tidak mengubah apa pun**
> kecuali diminta.

Ini diuji sebagai janji, bukan sebagai pembacaan kode: seluruh pohon di-hash
sebelum dan sesudah `init` kedua, dan hash-nya harus identik.

```
init pertama  → c6d29d1fe1dc41fa490ffd749851b503ef0ad2e89dd8ea305097f3122f73bc17
init kedua    → c6d29d1fe1dc41fa490ffd749851b503ef0ad2e89dd8ea305097f3122f73bc17
```

Sebelum fase ini janji itu **dilanggar**: `cp` selalu menulis ulang, jadi setiap
`init` menyentuh 12 berkas dan membuat `git status` kotor tanpa alasan. Itu cara
orang belajar mengabaikan output alat.

Perbaikannya membandingkan dulu, menyalin kemudian: `cmp` untuk berkas tunggal,
dan penanda hash 16 karakter untuk direktori `ironclad_core/`. Hasilnya
`kept    scripts/ (already current)` alih-alih daftar `wrote` yang tidak benar.

## 2. Tiga perintah baru

| Perintah | Menjawab |
|---|---|
| `ironclad doctor` | kenapa ini tidak bekerja seperti yang saya harapkan? |
| `ironclad rules` | aturan apa saja, dan seberapa keras masing-masing di preset ini |
| `ironclad rules explain ID` | aturan ini mencari apa, dan **apa yang menolak ia putuskan** |
| `ironclad presets` | preset bawaan dan hitungan error/warn-nya |

`doctor` mencetak empat bagian dengan urutan yang orang benar-benar tanyakan:
install (python, aset, jumlah preset) → engine (berapa aturan per domain) →
policy (**dari lapisan mana**, dan apakah berkas di disk setuju dengan yang akan
dijalankan) → berkas (apa yang terbaca, apa yang tidak) → aturan yang akan
menyala, termasuk yang `off`.

Ia tidak pernah menulis dan tidak pernah memperbaiki. Diagnostik yang mengubah
keadaan tidak bisa dipakai saat kamu sedang mencari tahu apa yang berubah.

Exit code-nya memperluas kontrak yang sudah ada: `0` sehat, `1` repo butuh
perhatian, `3` **instalasinya** yang rusak. Perbedaan itu penting — "re-run
installer" adalah saran yang salah kalau yang salah adalah repo.

`rules explain` sengaja memuat bagian **"What it will not decide"**. Setiap aturan
punya batas, dan menyebutkannya lebih berguna daripada menyembunyikannya: SEC-01
bisa melihat kredensial ada di berkas yang bisa dikirim git, tapi tidak bisa tahu
apakah kredensial itu masih hidup.

## 3. Deteksi stack

`init` berhenti bertanya kalau repo sudah menjawab. Sinyalnya hanya berkas yang
dibuat framework saat instalasi — `artisan`, `composer.json` + dependensi,
`package.json` + `workspaces`, `prisma/schema.prisma`, `phpunit.xml`:

| Repo | Terdeteksi | Preset |
|---|---|---|
| ucapanin | laravel, php/composer, phpunit | `strict` |
| silomag | express, react, vitest (lewat `workspaces`) | `strict` |
| wilsench | next.js, react, tanpa test runner | `balanced` |
| saku | tanpa penanda framework | `legacy-friendly` |

Aturannya soal usia, bukan selera: repo yang skemanya sudah konsisten bisa
menahan `strict`; repo dengan gaya campuran butuh peringatan dulu.

## 4. Empat bug, semuanya ditemukan dengan menjalankan

**1. `doctor` membaca policy milik proyek lain.** `find_repo_config` menelusuri
direktori **induk**, jadi memeriksa `/root/projects/x` mengambil
`/root/.agent/standards.yml` — policy mesin ini — dan menerapkannya diam-diam.
`doctor` lalu mencetak dua kalimat yang saling bertentangan dalam satu laporan:
"from /root/.agent/standards.yml (repo policy)" dan "no .agent/standards.yml
here". Sekarang hanya mencari **di dalam** target; policy induk harus diminta
eksplisit lewat `--config`.

**2. Tes Ironclad sendiri dianggap skema Django.** `UNSUPPORTED_HINTS[".py"]`
cocok pada *kata* `models.Model`, dan suite tes arsitektur memuat
`class Fake(models.Model)` di dalam fixture string. Repo diperiksa dengan
menganggap dirinya punya skema yang tak terbaca. Dua perbaikan: regex-nya
sekarang menambatkan bentuk deklarasi (`^class X(models.Model):`), dan blok string
tiga kutip dibuang sebelum diuji — teks *tentang* kode bukan kode.

**3. Wrapper tidak mengenal perintah baru.** `rules` dan `doctor` saya sambungkan
ke `check_schema.py` saja. Instalasi nyata memakai generator launcher di
`install.sh`, jadi `ironclad rules` menjawab "unknown command". Yang menangkapnya
adalah uji pada instalasi bersih di HOME sandbox, bukan uji unit.

**4. Help terpotong.** `--help` mencetak `sed -n '2,14p'` — rentang tetap. Begitu
satu verb ditambahkan, baris terakhir hilang tanpa suara. Sekarang membaca seluruh
blok komentar kepala.

## 5. Verifikasi

| Gerbang | Hasil |
|---|---|
| `init` idempoten | **hash pohon identik** sebelum/sesudah |
| `init --dry-run` | exit 0, **0 berkas ditulis** |
| `tests/test_dx_commands.py` | **43/43** |
| `tests/test_architecture_domain.py` | 23/23 |
| `tests/test_security_domain.py` | 29/29 |
| `tests/test_api_domain.py` | 31/31 |
| `tests/test_regressions.py` | 22/22 |
| `drill.py --selftest` | exit 0 |
| 108 kasus perilaku | **0 exit code berubah, 0 temuan berubah** |
| instalasi bersih di HOME sandbox | 40 berkas; `rules`, `doctor`, `presets` jalan |

## 6. Yang masih terbuka

- **`doctor --fix`** tidak dibuat. Memperbaiki otomatis berarti menulis ke repo
  orang berdasarkan tebakan tentang apa yang mereka maksud; itu pekerjaan
  tersendiri dengan persetujuan tersendiri.
- **`ironclad explain <file>`** (kenapa berkas *ini* tidak diperiksa) belum ada.
  `doctor` menjawabnya per repo; per berkas butuh melaporkan alasan per aturan.
- **Deteksi stack tidak membaca `Gemfile`, `go.mod`, `Cargo.toml`, `pom.xml`.**
  Repo di mesin ini tidak memakainya, jadi menambahkannya sekarang berarti
  menulis kode yang belum pernah dijalankan pada input nyata.
