---
title: Aturan
slug: rules
group: Referensi
order: 20
summary: Enam belas aturan di empat domain, masing-masing dengan contoh salah yang benar-benar diuji checker — plus catatan apa yang menolak ia putuskan.
---

# Aturan

Setiap aturan punya ID, supaya laporan agent dan komentar review bisa mengutipnya.
Awalan menunjukkan berkas mana yang dibuka aturan itu: `DB-` skema database,
`API-` deklarasi rute, `SEC-` kredensial dan `.env`, `ARCH-` graf impor.

## Ringkasan

Kolom **Status** di bawah adalah perilaku pada preset `balanced` (default). Pada
`strict` keenam belas aturan jadi `error`. Pada `legacy-friendly` semuanya `warn`
dan tidak ada yang memblokir build — kecuali ARCH-01 dan ARCH-02, yang dimatikan
sama sekali: siklus impor di proyek warisan biasanya sudah ada sebelum kamu tiba,
dan memblokir semuanya di hari pertama adalah cara aturan ini dihapus dari CI.
Jalankan `ironclad rules --preset <nama>` untuk melihat yang berlaku pada
presetmu, bukan yang tertulis di sini.

| ID | Aturan | Status |
|---|---|---|
| DB-01 | Tidak ada `enum` native di schema | **error** |
| DB-02 | Tidak ada magic number dibandingkan ke kolom status | **error** |
| DB-03 | Integer status wajib punya FK atau `CHECK` | warn |
| DB-04 | Label manusia tidak pernah disimpan sebagai status | **error** |
| DB-05 | `boolean` hanya untuk biner sejati | warn |
| DB-06 | Uang harus eksak — `numeric` skala tetap atau `bigint` satuan terkecil, bukan float | warn |
| DB-07 | Timestamp wajib membawa zona waktu | warn |
| DB-08 | Satu proyek satu gaya status — tidak campur enum dan integer | warn |

### API — bagaimana endpoint menjawab

| ID | Aturan | Status |
|---|---|---|
| API-01 | Gaya penamaan endpoint lebih dari satu dalam satu router | warn |
| API-02 | Payload error dikirim dengan status 2xx | warn |
| API-07 | Rute yang sama dideklarasikan dua kali | error |

### Keamanan — apa yang bocor, dan apa yang hampir bocor

| ID | Aturan | Status |
|---|---|---|
| SEC-01 | Kredensial di berkas yang bisa ikut terkirim git | warn (error bila terbukti dilacak) |
| SEC-02 | Kredensial ditulis langsung di kode | error |
| SEC-03 | `.env.example` tidak lagi cocok dengan `.env` | warn |

### Arsitektur — bentuk proyek, dibaca dari impornya

| ID | Aturan | Status |
|---|---|---|
| ARCH-01 | Berkas saling mengimpor dalam siklus | warn |
| ARCH-02 | Impor menunjuk berkas yang tidak ada | warn |

Rincian tiap domain ada di `references/` di dalam skill, dan
`ironclad rules explain <ID>` mencetak alasan yang sama plus **apa yang menolak
ia putuskan** — bagian yang paling berguna saat kamu tidak setuju dengan temuan.

## Kenapa empat domain ini, dan tidak lebih

Satu set aturan adalah klaim tentang apa yang bisa diperiksa dengan jujur hanya
dari kode sumber. Masing-masing diukur pada repo nyata sebelum dikirim, dan
beberapa usulan aturan gugur karena angkanya berkata tidak:

- "controller tidak boleh menyentuh model" menyala di **6 dari 7** controller
  Laravel sungguhan — itu idiom resmi framework, bukan cacat.
- "test yang selalu skip" menyala **nol** kali di seluruh repo pada mesin yang
  membangun alat ini. Aturan yang belum pernah menyala adalah aturan yang belum
  diketahui bekerja.
- "satu berkas test per modul" mengasumsikan pemetaan yang tak pernah ada di
  monorepo sungguhan: 15 berkas test untuk tiga workspace.

Ini bukan pendapat soal gaya. Ini sisa dari pengukuran, dan pengukurannya tercatat
di `docs/PHASE2_API_DOMAIN.md` sampai `docs/PHASE5_DX.md` di repositori.

---

## DB-01 — Tidak ada `enum` native

```sql
-- ✗ ditolak
status enum('pending','shipped','cancelled')

-- ✓ diterima
status_code smallint NOT NULL REFERENCES ref_order_status(code)
```

**Alasan:** menambah nilai enum butuh `ALTER TABLE`; pada tabel besar itu mengunci dan bisa berarti downtime. Status bisnis selalu tumbuh — "ditunda karena cuaca", "dibatalkan sebagian" — dan tiap pertumbuhan tidak seharusnya jadi acara migrasi.

**Pengecualian:** enum yang memang **disengaja** dan nilainya hanya berubah lewat review kode. Tulis alasannya di komentar migrasi; pada `balanced` itu diterima saat review.

```php
// Enum disengaja: nilainya mengikat kontrak API publik, tidak akan tumbuh.
$table->enum('visibility', ['public','unlisted','private']);
```

---

## DB-02 — Tidak ada magic number pada kolom status

```php
// ✗ ditolak
if ($order->status_code === 3) { ... }
Order::where('status_code', 3)->get();

// ✓ diterima
if ($order->status_code === OrderStatus::SHIPPED) { ... }
Order::where('status_code', OrderStatus::SHIPPED)->get();
```

**Alasan:** `3` tidak berarti apa pun saat muncul di log atau stack trace. Enam bulan kemudian tidak ada yang berani mengubahnya, karena tidak ada yang tahu apa itu `3`.

**Yang tidak dilanggar:** literal di dalam `CHECK (...)` dan `INSERT` — itu DDL yang benar, dan checker mengabaikannya secara sadar.

```sql
CONSTRAINT stock_qty_consistent
  CHECK ((status_code = 88 AND qty = 0) OR (status_code <> 88 AND qty >= 0))
```

---

## DB-03 — Integer status wajib punya FK atau `CHECK`

```sql
-- ✗ ditolak: 7 bisa masuk, tidak ada yang menolak
status_code smallint NOT NULL

-- ✓ diterima
status_code smallint NOT NULL REFERENCES ref_stock_status(code)
```

**Alasan:** tanpa FK, kolom integer adalah `varchar` yang kebetulan berupa angka. Tidak ada yang mencegah `status_code = 7` saat kode sahnya hanya `88..91`.

**Peringatan desain:** `CHECK` yang menghardcode semua kode sah berarti kamu membangun ulang enum. Pakai FK ke lookup table — menambah nilai jadi satu baris data, bukan perubahan schema.

---

## DB-04 — Label manusia tidak pernah jadi nilai status

```sql
-- ✗ ditolak
stock_state varchar(20)    -- 'available', 'empty'

-- ✓ diterima
status_code smallint NOT NULL REFERENCES ref_stock_status(code)
```

**Alasan:** label berubah karena alasan pemasaran ("Kosong" → "Stok Habis"), dan setiap perubahan itu menjadi migrasi data yang menyentuh seluruh baris. Lebih buruk: label tidak pernah diterjemahkan, jadi aplikasi berbahasa Indonesia menyimpan kata Inggris selamanya.

Label tinggal di lookup table, satu tempat, dan bisa diterjemahkan lewat tabel terpisah kalau perlu.

---

## DB-05 — `boolean` hanya untuk biner sejati

```sql
-- ✗ ditolak: status punya lebih dari dua keadaan
is_status boolean

-- ✓ diterima
is_active    boolean NOT NULL DEFAULT true
is_deleted   boolean NOT NULL DEFAULT false
status_code  smallint NOT NULL REFERENCES ref_stock_status(code)
```

**Alasan:** `is_status` menjebak. Hari ini true/false; bulan depan butuh "tertunda", dan kamu menambah `is_pending`, lalu `is_partial` — tiga boolean yang saling bertentangan dan tidak ada yang tahu kombinasi mana yang sah.

**Tes cepat:** bisakah kolom ini punya keadaan ketiga dalam dua tahun? Kalau ya, ia bukan boolean.

---

## DB-06 — Uang harus eksak, bukan `float`

```sql
-- ✗ ditolak
total_amount  float
harga_satuan  double precision
price         real

-- ✓ diterima (dua-duanya sah)
total_minor   bigint NOT NULL          -- 1250000 = Rp 12.500,00
currency      char(3) NOT NULL         -- 'IDR'

total_amount  numeric(14,2) NOT NULL   -- presisi tetap, juga eksak
```

**Alasan:** `0.1 + 0.2` pada float bukan `0.3`. Untuk satu transaksi selisihnya nol
koma nol sekian; untuk laporan bulanan dengan 200.000 baris, itu selisih yang harus
dijelaskan ke auditor.

`numeric`/`decimal` **juga eksak** dan checker tidak melarangnya — yang dilarang hanya
binary float (`float`, `real`, `double precision`). Memilih integer satuan terkecil
atau `numeric` keduanya benar: integer paling aman terhadap pembulatan per-pangkah dan
perbedaan ORM, `numeric` lebih mudah dibaca dan cocok untuk perhitungan yang butuh
pecahan (persentase, kurs). Yang tidak boleh: mencampur keduanya dalam satu kolom
yang sama di dua tempat berbeda.

---

## DB-07 — Timestamp membawa zona waktu

```sql
-- ✗ ditolak
issued_at  timestamp

-- ✓ diterima
issued_at  timestamptz
created_at timestamptz NOT NULL DEFAULT now()
```

**Alasan:** `timestamp` tanpa zona menyimpan "14:30" tanpa menjawab "di mana". Aplikasi dengan pengguna di Jakarta dan server di Singapura akan salah satu jam, dan tidak ada cara memperbaikinya setelah data bertahun-tahun terkumpul.

Laravel dan Prisma memakai `createdAt`/`updatedAt` sebagai konvensi; checker mengenali itu dan tidak melaporkannya.

---

## DB-08 — Satu proyek, satu gaya status

Ini aturan yang paling langsung menjawab masalah tim: **bukan** "enum itu salah",
tapi "jangan biarkan satu proyek memakai tiga cara sekaligus".

```sql
-- ✗ ditolak: satu proyek, dua gaya berbeda
CREATE TABLE orders (
  status ENUM('new','paid','shipped')
);
CREATE TABLE shipments (
  status_code smallint NOT NULL REFERENCES shipment_status(code)
);
```

```
a.sql:1: [DB-08] warn
  status is stored 2 different ways in this project:
  enum (a.sql), integer (b.sql)
  pick one for the whole project; integer + lookup is the default
```

```sql
-- ✓ diterima: semua tabel memakai cara yang sama
CREATE TABLE orders (
  status_code smallint NOT NULL REFERENCES order_status(code)
);
CREATE TABLE shipments (
  status_code smallint NOT NULL REFERENCES shipment_status(code)
);
```

**Alasan:** enum dan integer sama-sama bisa bekerja — yang tidak bisa bekerja adalah
keduanya di proyek yang sama. Setiap laporan jadi butuh dua query, setiap developer
baru harus menebak, dan pertanyaan "bagaimana menambah status?" tidak punya satu
jawaban. DB-08 adalah satu-satunya aturan yang membaca **lintas berkas**, karena
inkonsistensi adalah sifat proyek, bukan sifat satu tabel.

**Kenapa integer jadi default:** menambah kode integer berarti menambah satu baris
data; menambah nilai enum berarti `ALTER TABLE` yang mengunci tabel. Bukan soal
selera, soal biaya saat status bertambah.

**Menyimpang dengan sadar:** kalau tim memilih enum, tulis alasannya di
`.agent/standards.md`. Yang dilarang bukan pilihan yang berbeda — yang dilarang
adalah tidak ada pilihan sama sekali.

Kalau kamu tidak ingin mengurus berkas config sama sekali, preset `coherence`
melakukan hal yang sama untuk seluruh proyek: `DB-01` di sana hanya peringatan,
dan `DB-08` tetap error. Jadi repo yang konsisten memakai enum akan hijau, sementara
repo yang mencampur tetap merah — tanpa kamu menulis apa pun.

---

## Uji sendiri

```bash
# harus lolos semua preset
python3 scripts/check_schema.py examples/good.sql --preset strict
# preset: strict
# 1 file(s), 0 error(s), 0 warning(s)

# harus gagal di strict
python3 scripts/check_schema.py examples/bad.sql --preset strict
```

`examples/good.sql` memakai kode `88/89/90` dan `990…993` dengan sengaja — untuk membuktikan bahwa kode tak berurutan itu sah, selama terdaftar di lookup table dan dipakai lewat FK.
