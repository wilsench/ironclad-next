# Phase 2 — the API domain

**Status:** selesai dan terverifikasi. Tiga aturan dikirim; empat ditolak setelah
diukur pada repo nyata.

---

## 1. Yang dikirim

| ID | Aturan | Severity default | Mengapa ini, bukan selera |
|---|---|---|---|
| API-01 | Path endpoint memakai lebih dari satu gaya penamaan | `warn` | Konsistensi, bukan preferensi: satu repo yang konsisten tidak pernah kena |
| API-02 | Payload error dikirim dengan status 2xx | `warn` | Kode menyatakan dua hal sekaligus; klien tidak bisa membedakan sukses dari gagal |
| API-07 | Rute yang sama dideklarasikan dua kali | `error` | Buktinya dua string identik dalam konteks mount yang sama; tidak ada tafsir |

API-07 satu-satunya yang `error`, karena satu-satunya yang tidak menebak. Aturan
lain `warn` sampai terbukti pada repo yang lebih banyak.

## 2. Yang dibuang, dan alasannya

Rencana awal punya enam aturan. Empat dicabut **setelah** dibangun atau
dirancang, karena pada repo nyata ia menghasilkan temuan yang salah:

- **API-03 bentuk respons seragam** — butuh tahu apa yang dikembalikan handler,
  termasuk yang dibangun helper. Regex akan menandai setiap endpoint yang
  mengembalikan array telanjang dan melewatkan setiap wrapper. Diam lebih baik.
- **API-04 versi API** — "breaking change" adalah properti riwayat git, bukan
  working tree. Tanpa riwayat, aturan ini hanya menuntut `/v1`, yaitu selera.
- **API-05 input tak tervalidasi** — validasi sering ada di FormRequest,
  middleware, atau berkas skema yang tidak dibuka aturan. Repo Laravel akan
  menyala untuk kode yang benar.
- **API-06 OpenAPI tidak cocok** — sudah dibangun, diukur, lalu ditarik. Pada repo
  Express nyata ia melaporkan drift yang sebenarnya hanya prefix mount
  (`app.use('/api/x', router)`) yang tidak bisa dilihatnya. Kembali saat discovery
  bisa mengikuti mount.

Ini keputusan yang sama dengan Fase 0.5: alat yang salah lebih buruk daripada alat
yang diam, karena yang salah akan dimatikan orang dan tidak pernah dinyalakan lagi.

## 3. Dua bug yang ditemukan dengan menjalankan, bukan membaca

Keduanya tidak akan terlihat dari tes unit yang saya tulis sendiri.

**Klien bukan server.** Draf pertama mencocokkan `api.post('/auth/login')` di
halaman React dengan pola yang sama seperti `router.post('/auth/login')`. Setiap
titik panggil menjadi "deklarasi duplikat": 95 temuan pada repo Express yang sehat,
dan `DELETE /{}` dilaporkan 35 kali. Perbaikannya: berkas diklasifikasi lebih dulu
(import axios = klien, `Router()` = server), dan duplikat hanya dibandingkan dalam
satu berkas untuk router JS karena mount-nya tidak terlihat.

**Grup itu mengubah arti path.** `Route::domain('{sub}.x')->group(...)` dan
`Route::get('/')` di luar grup adalah dua endpoint berbeda. Membandingkan string
mentah melaporkan kode Laravel yang benar sebagai rusak. Konteks mount sekarang
dilacak per baris.

Ketiga: **`id()` bukan kunci yang aman.** `files_checked` sempat melaporkan
"2 file" untuk repo satu berkas, karena dict berkunci `id(ctx)` tidak menahan
objeknya dan CPython mendaur ulang alamat memori. Diganti indeks. Ditemukan hanya
karena angkanya tidak masuk akal.

## 4. Perubahan inti yang dibutuhkan domain kedua

Ini yang membuktikan arsitekturnya, bukan sekadar mengikuti rencana:

1. **Discovery jadi deklaratif.** Daftar ekstensi tidak lagi ditulis di
   `discovery.py`; setiap aturan menyatakan `extensions`, dan `Registry.extensions()`
   menggabungkannya. Menambah domain = menambah berkas.
2. **`ProjectRule.applies_to()`** memisahkan "berkas ini layak dibaca" dari
   "berkas ini dinilai". Tanpa itu, aturan proyek membaca 400 berkas untuk menilai
   nol, dan `files_checked` membengkak.
3. **Cakupan diukur per aturan, bukan per berkas yang terbuka.** Ini menutup lulus
   palsu: repo Django berisi `models.py` dulu berubah dari exit 2 menjadi exit 0
   karena berkasnya "berhasil dibaca" padahal tidak ada aturan yang memeriksanya.
4. **`handles_responses()`** supaya API-02 bisa memeriksa controller Laravel yang
   tidak pernah memuat `Route::`, tanpa ikut memindai halaman React.

## 5. Verifikasi

| Gerbang | Hasil |
|---|---|
| 108 kasus perilaku vs baseline | **0 exit code berubah, 0 temuan berubah**; 16 pesan berubah (memang diperbaiki) |
| `tests/test_api_domain.py` | **31/31** |
| `tests/test_regressions.py` | **22/22** |
| `drill.py --selftest` | exit 0 |
| Repo Laravel nyata (ucapanin, 146 berkas) | 10 temuan, semuanya DB; 0 API |
| Repo Express nyata (silomag, 37 berkas diperiksa) | 31 temuan, semuanya DB; 0 API |

Nol temuan API pada dua repo itu **bukan** karena aturannya tidak jalan: ekstraksi
mengeluarkan 35 rute di repo Laravel dan 75 rute dari 21 berkas rute di repo
Express, dan keduanya memang konsisten. Yang diuji adalah rute yang benar-benar
terbaca, bukan jumlah temuan.

## 6. Yang masih terbuka

- **Prefix mount JS lintas berkas.** `app.use('/api/v1', router)` belum diikuti,
  jadi API-06 tidak bisa kembali dan path JS dibandingkan apa adanya.
- **`Route::resource()`** tidak diperluas menjadi tujuh rute, jadi tidak ikut
  diperiksa duplikat.
- **FastAPI dekorator** baru dikenali sebagai penanda berkas, belum diekstrak
  path-nya.
- **Default API-07 = `error`** pada instalasi baru. Aman karena buktinya dua string
  identik, tapi ini tetap default pertama yang bisa memblokir di luar database;
  perlu satu rilis pengamatan sebelum dipertahankan.
