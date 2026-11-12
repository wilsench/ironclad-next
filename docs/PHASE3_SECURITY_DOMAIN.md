# Phase 3 — the security domain

**Status:** selesai dan terverifikasi. Tiga aturan dikirim, empat ditolak. Yang
paling penting dari fase ini bukan aturannya, melainkan **angka yang membuktikan
mengapa aturan itu harus sempit**.

---

## 1. Bukti sebelum aturan

Domain ini paling mudah menjadi alat yang dimatikan orang, jadi saya ukur dulu.
Pada tiga repo nyata di server ini:

| Pendekatan | Temuan |
|---|---|
| entropi mentah (assignment apa pun yang acak) | 1647 + 408 + 536 |
| nama kredensial + entropi + lewati placeholder | 2 (keduanya **salah**) |
| ditambah "nama kelas PHP bukan rahasia" | 0 |
| kontrol yang ditanam (`sk_live_...`, app key base64) | 1, benar |

Dua yang salah itu: `'auth.password' => 'Illuminate\Auth\Passwords\...'` di berkas
cache Laravel. Nilainya nama kelas. Itu kasus negatif paling berguna yang dimiliki
domain ini, dan alasan penjaga `_CLASS_REF` ada.

## 2. Yang dikirim

| ID | Aturan | Default |
|---|---|---|
| SEC-01 | Kredensial di berkas yang bisa dikirim git | `warn` (naik ke `error` bila terbukti dilacak) |
| SEC-02 | Kredensial ditulis langsung di kode | `error` |
| SEC-03 | `.env.example` tidak lagi mendokumentasikan isi `.env` | `warn` |

SEC-01 memisahkan empat keadaan, karena itu empat masalah berbeda:

- **dilacak git** → `error`: sudah masuk riwayat, harus dicabut dan dirotasi
- **tidak dilacak, tidak diabaikan** → `warn`: satu `git add .` dari bocor
- **tidak dilacak dan diabaikan** → diam: ini bentuk yang benar
- **tidak ada repo sama sekali** → diam: `.env` produksi di server memang tempatnya

Keadaan keempat itu bukan teori: di server ini `.env` silomag persis begitu. Draf
pertama menuduhnya "committed" tanpa memeriksa git — kesalahan yang akan
menghapus kredibilitas seluruh domain.

## 3. Rahasia tidak pernah dicetak

Temuan menyebut berkas, baris, nama variabel, dan tindakan. Tidak pernah nilainya,
bahkan tidak potongannya. Laporan yang mengutip rahasia adalah salinan kedua
rahasia itu, di log dan di artefak CI. Ada tes yang memastikan nilainya tidak
muncul di keluaran.

## 4. Empat bug, semuanya ditemukan dengan menjalankan

1. **`.env` tidak pernah ditemukan.** `Path(".env").suffix` kosong, jadi berkas
   paling penting di domain ini tidak pernah masuk daftar selama entri
   `.env` ditulis sebagai ekstensi. Sekarang klaim juga dicocokkan sebagai nama.
2. **`.env.example` juga tidak ditemukan** — suffix-nya `.example`. Satu berkas
   yang justru seharusnya di-commit jadi tak terlihat. Klaim `.env` sekarang
   mencakup keluarga bertitik (`.env.example`, `.env.production`).
3. **Severity per-temuan ditimpa config.** SEC-01 perlu `error` untuk berkas yang
   dilacak dan `warn` untuk yang tidak, dan satu entri config tidak bisa
   menyatakan keduanya. Engine sekarang menghormati severity pilihan aturan
   kecuali config menyebut aturan itu secara eksplisit.
4. **Berkas kebijakan Ironclad sendiri ikut dipindai.** `.agent/standards.yml`
   dinilai sebagai kode sumber, artinya repo dihakimi oleh aturan yang ia
   konfigurasi. Dikecualikan.

Tambahan: `getenv('APP_KEY')` sempat dianggap rahasia literal. Sekarang pemanggilan
pembaca environment (`getenv`, `process.env`, `os.environ`) ditolak lebih dulu.

## 5. Perubahan inti: cakupan skema vs pekerjaan nyata

Domain security membaca 22 jenis ekstensi, termasuk `.py`. Akibatnya repo Django
berisi `models.py` kembali **exit 0** — lulus palsu yang sama seperti Fase 2,
dengan penyebab baru: berkasnya "diperiksa" oleh aturan security, padahal tidak ada
aturan skema yang melihatnya.

Perbaikannya: exit code 2 adalah janji tentang **cakupan skema**. `SCHEMA_DOMAINS`
sekarang memisahkan "ada aturan yang berjalan" dari "ada skema yang diperiksa".
Domain security tetap bekerja penuh; ia hanya tidak lagi bisa membuat repo tanpa
skema tampak bersih.

Sempat saya buat kesalahan di sini: patch pertama membatasi **eksekusi** ke domain
skema, yang akan mematikan semua temuan API dan security. Tertangkap karena tes
API dan security langsung merah, bukan karena saya membacanya ulang.

## 6. Verifikasi

| Gerbang | Hasil |
|---|---|
| 108 kasus perilaku | **0 exit code berubah, 0 temuan berubah**; 16 pesan berubah |
| `tests/test_security_domain.py` | **29/29** (12 di antaranya negatif) |
| `tests/test_api_domain.py` | **31/31** |
| `tests/test_regressions.py` | **22/22** |
| `drill.py --selftest` | exit 0 |
| ucapanin (Laravel, 143 berkas skema) | 10 DB + 1 SEC-03 |
| silomag (Express, 3 berkas skema) | 31 DB + 1 SEC-03 |
| saku (PHP, 3 berkas skema) | 3 DB |

Kedua temuan SEC-03 nyata dan berguna: ucapanin `.env.example` kehilangan 7
variabel (termasuk `DB_HOST`, `DB_PASSWORD`), silomag kehilangan `VITE_API_URL`.
Nol SEC-01/SEC-02 di semua repo, dan itu benar: tidak ada `.env` yang dilacak dan
tidak ada kredensial literal di sumber.

## 7. Yang masih terbuka

- **SEC-04 riwayat git** — butuh `git log -S`; tempatnya di `ironclad doctor`,
  bukan pemeriksa berkas.
- **SEC-05 CVE dependensi** — butuh jaringan dan basis data kerentanan. Alat ini
  harus berguna offline; daftar CVE basi lebih buruk daripada tidak ada.
- **SEC-06 authz per rute** — middleware bisa dipasang lewat grup, service
  provider, atau kernel. Regex tidak bisa melihat warisan; repo Laravel akan
  menyala untuk kode yang terlindungi.
- **SEC-07 SQL injection** — uji yang jujur adalah "apakah query builder dipakai",
  yaitu pekerjaan AST atas beberapa bentuk pemanggilan.
- **Rotasi**: SEC-01 bisa menyebut bahwa kredensial sudah masuk riwayat, tapi
  tidak bisa menilai apakah sudah dirotasi. Itu keputusan manusia.
