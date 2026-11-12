# Phase 4 — the architecture domain

**Status:** selesai dan terverifikasi. Dua aturan dikirim, lima ditolak. Seperti
Fase 3, angka yang menentukan desainnya, bukan selera saya.

---

## 1. Yang diukur lebih dulu

Empat repo nyata di mesin ini: ucapanin (Laravel, 142 berkas PHP), silomag
(Express + React, 457 berkas JS/TS, 930 edge impor), wilsench (Next.js), saku (PHP).

| Kandidat | Hasil pengukuran | Keputusan |
|---|---|---|
| ARCH-01 impor melingkar | 0 siklus di semua repo; kontrol tanaman (3-node, 2-node) **tertangkap**, DAG tidak | dikirim |
| ARCH-02 impor rusak | 0 setelah resolver diperbaiki; kontrol tanaman tertangkap | dikirim |
| ARCH-03 controller → model | **6 dari 7** controller ucapanin — itu idiomatik Laravel | ditolak |
| ARCH-04 direktori tak dikenal | menyala di `scripts/`, `docs/`, `public/`, `shared/`, `prisma/` | ditolak |
| ARCH-05 berkas terlalu besar | ambang yang tak disepakati siapa pun | ditolak |
| TEST-01 test tidak sejajar modul | silomag punya 15 test untuk 3 workspace, bukan 1:1 | ditolak |
| TEST-02 ambang coverage | pilihan, bukan cacat | ditolak |
| TEST-03 test selalu skip | **0** di seluruh repo; aturan yang tak pernah menyala tak bisa dipercaya | ditolak |

Nol siklus itu sendiri mencurigakan, jadi saya tanam kontrol sebelum percaya:
siklus 3-node dan 2-node tertangkap, DAG `x→y→z` tidak. Detektornya bekerja dan
repo-repo ini memang bersih.

## 2. Dua aturan yang dikirim

| ID | Aturan | balanced | strict | coherence | legacy |
|---|---|---|---|---|---|
| ARCH-01 | berkas saling mengimpor dalam siklus | `warn` | `error` | `warn` | `off` |
| ARCH-02 | impor menunjuk berkas yang tidak ada | `warn` | `error` | `warn` | `off` |

ARCH-01 dilaporkan **per komponen**, bukan per edge. Simpul 200 berkas dengan 400
edge adalah 400 temuan yang tak bisa ditindak; satu temuan berisi anggotanya
adalah satu keputusan. Tarjan iteratif, bukan rekursif — repo 5000 berkas
melempar `RecursionError`, dan pemeriksa yang crash di repo besar lebih buruk
daripada yang melewatkan satu siklus.

`legacy-friendly` mematikan keduanya dengan sengaja: kode lama punya siklus yang
tidak akan diperbaiki kuartal ini, dan jalan pertama yang dibuka dengan 40 temuan
adalah jalan pertama yang tidak diulang.

## 3. Tiga bug yang ditemukan dengan menjalankan

**1. `use` di PHP bukan edge.** Draf pertama menghitung `use App\X\Y;` sebagai
impor, menghasilkan **8 "siklus"** di resource Filament ucapanin. Semuanya pola
resmi framework: Resource menyebut Pages-nya, tiap Page menunjuk balik ke
Resource. Itu bukan simpul, itu pohon yang digambar dua kali. Di PHP, `use`
hanyalah alias — autoloader memuatnya malas. Yang memaksa pemuatan hanya
`extends`, `implements`, dan `use Trait` di dalam badan kelas. Pembeda terakhir
itu kedalaman kurung kurawal: alias di kedalaman 0, trait di dalam kelas.

**2. `./x.js` bukan impor rusak.** Resolver pertama melaporkan 15 dari 1927 impor
silomag sebagai rusak. Semuanya TypeScript benar: NodeNext menulis `./types/index.js`
untuk berkas `types/index.ts`. Resolver sekarang mencoba akhiran TS lebih dulu
saat spesifier berakhiran `.js`.

**3. Dokumentasi bukan skema.** Repo Next.js melaporkan "punya berkas skema yang
tak bisa dibaca: .js" karena bundle docs Ironclad sendiri memuat kalimat
"Sequelize `DataTypes.*` belum — dilaporkan, tidak diperiksa". Teks *tentang*
sesuatu bukan sesuatu itu — bug yang sama kelasnya dengan `.agent/standards.yml`
di Fase 3. Aset build sekarang dikecualikan dari deteksi skema.

## 4. Perubahan inti: cakupan yang jujur

Exit code 2 berarti "tidak ada skema yang bisa diperiksa". Domain architecture
membaca `.ts`, jadi repo JS murni akan selalu punya "berkas yang diperiksa" dan
tidak pernah bisa exit 2 — kecuali kalau cakupan dibiarkan berarti apa saja yang
dibuka.

Solusinya dua angka, bukan satu:

- `schema_checked` — berkas yang benar-benar diurai aturan skema. Tetap
  menentukan exit code 2, persis seperti sebelumnya.
- `files_checked` — berkas yang dibuka aturan apa pun. Dipakai untuk laporan.

Dan aturan penutupnya: **stack skema yang tak terbaca selalu menang**. Repo
Django dengan `models.py` tetap exit 2 walaupun ARCH-01 baru saja membaca
`models.py`. Tanpa aturan itu, repo Django kembali lulus palsu — dan memang
begitu saat pertama saya coba: 8 kasus baseline berubah dari exit 2 ke exit 0.

## 5. Verifikasi

| Gerbang | Hasil |
|---|---|
| 108 kasus perilaku | **0 exit code berubah, 0 temuan berubah** |
| `tests/test_architecture_domain.py` | **23/23** (13 di antaranya negatif) |
| `tests/test_security_domain.py` | 29/29 |
| `tests/test_api_domain.py` | 31/31 |
| `tests/test_regressions.py` | 22/22 |
| `drill.py --selftest` | exit 0 |
| ucapanin (142 PHP) | 0 ARCH — dan 8 siklus Filament hilang setelah perbaikan |
| silomag (930 edge, 1927 impor) | 0 ARCH |
| wilsench (Next.js) | 0 ARCH, **exit 0** (dulu exit 2 karena docs) |
| saku | 0 ARCH |
| kontrol tanaman di salinan ucapanin | siklus + impor rusak **tertangkap**, exit 1 di `strict` |

Silomag dan ucapanin diverifikasi identik dengan commit `cad3801` lewat worktree
terpisah, bukan dari ingatan: jumlah temuan sama, berkas sama, baris sama.

## 6. Yang sengaja tidak dikirim

Domain `testing` tidak dikirim sama sekali. Tiga aturan yang diusulkan roadmap
gugur dalam pengukuran, dan tidak satu pun alasan kegagalannya bisa diperbaiki
dengan lebih banyak kode:

- **TEST-01** mengasumsikan satu test per berkas sumber. Tidak ada repo di sini
  yang begitu, dan aturan yang menyala untuk setiap berkas tanpa test kembar
  adalah laporan coverage yang dibuat ulang dengan buruk.
- **TEST-02** menganggap tidak adanya ambang coverage sebagai cacat. Itu pilihan.
- **TEST-03** tidak pernah menyala di satu berkas pun di mesin ini. Aturan yang
  belum pernah terbukti menyala adalah aturan yang belum diketahui bekerja.

Yang tersisa untuk domain testing adalah pertanyaan yang butuh menjalankan tes
(`ironclad doctor`), bukan membaca berkas. Ia menunggu fase berikutnya.

## 7. Yang masih terbuka

- **ARCH-03 lapisan** — butuh proyek mendeklarasikan lapisannya sendiri
  (`.agent/layers.yml`). Tanpa itu setiap aturan lapisan adalah tebakan penulis
  aturan tentang arsitektur orang lain.
- **Alias bundler** — `@/x` dilewati, bukan diselesaikan, kecuali `tsconfig`
  ada. Membaca `vite.config.ts`/`webpack.config.js` berarti mengeksekusi
  konfigurasi; itu keputusan tersendiri.
- **PHP `composer.json` PSR-4** — hanya `App\` yang diikuti. Repo yang memetakan
  namespace lain akan luput, bukan salah lapor.
- **Siklus lewat paket** — edge ke `node_modules` tidak diikuti. Siklus yang
  melewati dependensi adalah masalah dependensi itu.
