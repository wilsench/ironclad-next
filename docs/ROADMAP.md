# Roadmap — Ironclad Next

**Prinsip urutan:** perbaiki kebohongan dulu, baru bangun di atasnya. Sebuah
arsitektur baru yang mewarisi dua bug "lulus palsu" hanya menyebarkan bug itu
ke setiap domain yang menyusul.

Setiap fase punya **gerbang** yang harus lulus sebelum fase berikutnya dimulai.

---

## Fase 0 — Audit (SELESAI)

**Keluaran:** `BASELINE_AUDIT.md`, `FEATURE_PARITY.md`, `ARCHITECTURE_PROPOSAL.md`,
`COMPATIBILITY_PLAN.md`, `ROADMAP.md`.

**Temuan:** 2 bug nyata (BUG-A payload tidak lengkap di jalur remote, BUG-B
`--preset` diabaikan), 55 kontrak dipetakan, 52 terverifikasi.

**Gerbang:** tidak ada perubahan kode. Selesai.

---

## Fase 0.5 — Perbaikan bug & jaring regresi (SELESAI)

**Kenapa sebelum Fase 1:** keduanya menghasilkan "lulus" palsu. Membangun mesin
baru di atasnya berarti menyalin cacatnya.

**Pekerjaan:**

| # | Tugas | Berkas | Status |
|---|---|---|---|
| 1 | Manifest payload diturunkan dari filesystem, bukan ditulis tangan | `install.sh` (`_manifest`) | selesai |
| 2 | Mirror menerbitkan `MANIFEST` + membuang berkas usang | `scripts/sync-mirror.sh` | selesai |
| 3 | `--preset` pengguna menang atas preset repo (satu tempat) | `check_schema.py:load_preset` | selesai |
| 4 | Berkas repo selalu dilapisi; `name:` saja diselesaikan ke presetnya | `check_schema.py:load_preset` | selesai |
| 5 | Uji installer di CI (`curl|bash` di HOME sandbox) | `tests/test_regressions.py` + workflow | selesai |
| 6 | `ironclad doctor` minimal | — | **belum** (Fase 5) |

**Gerbang:**
- [x] C-10 lulus (payload lengkap lewat mirror): 14 berkas, `update` & `init coherence` jalan
- [x] C-07 lulus (`--preset` benar-benar berlaku): `strict`→exit 1, `legacy-friendly`→exit 0
- [x] Selftest tetap 20/20
- [x] CI punya langkah regresi (`tests/test_regressions.py`, 19 pemeriksaan)
- [x] Instalasi nyata di HOME bersih (bukan hanya unit test)

**Catatan:** pekerjaan #1–#5 juga menutup BUG-C (repo berpreset `coherence` tidak
bisa diperiksa sama sekali), yang tidak terlihat saat audit awal karena hanya
muncul lewat wrapper pada mesin hasil `curl|bash`.

**Risiko:** rendah. Tidak ada aturan yang berubah; `drill.py --selftest` tetap
20/20 dan fixture tidak disentuh.

---

## Fase 1 — Ekstraksi core tanpa mengubah perilaku

**Tujuan:** memindahkan mesin keluar dari `check_schema.py` menjadi
`core/` + `domains/database/`, **tanpa satu pun perubahan perilaku**.

**Pekerjaan:**

1. `core/model.py` — `Finding`, `Severity`, `Position`, `RuleMeta`.
2. `core/config.py` — resolusi berlapis + override (memperbaiki BUG-B secara
   struktural, bukan tambal).
3. `core/discovery.py` — penemuan berkas & `SKIP_DIRS` dari kode sekarang.
4. `core/engine.py` — orkestrasi + agregasi `scope=project` untuk DB-03/DB-08.
5. `core/report/{text,json}.py` — dua reporter; kunci JSON lama dipertahankan.
6. `domains/database/` — pindahkan 8 aturan + coverage satu per satu.
7. `skills/ironclad/` menjadi pembungkus tipis.

**Gerbang:**
- [ ] C-01: selftest 20/20, **fixture tidak diubah** (diff fixture = 0 baris)
- [ ] C-02 … C-04 lulus
- [ ] C-06, C-07 lulus
- [ ] C-13: kunci JSON lama masih ada
- [ ] Tidak ada `if rule_id == "DB-"` di `core/`
- [ ] `core/` tidak mengimpor `domains/`

**Risiko:** sedang. Mitigasi: refactor murni, satu aturan per commit, selftest
dijalankan setiap commit.

---

## Fase 2 — Domain API (SELESAI)

**Kenapa kedua:** kontraknya paling jelas (HTTP) dan paling murah diverifikasi.

**Dikirim:**

| ID | Aturan | Keparahan |
|---|---|---|
| API-01 | Nama path tidak konsisten gaya (`/users` vs `/getUsers`) | `warn` |
| API-02 | Error dikirim di bawah status 2xx | `warn` |
| API-07 | Rute yang sama dideklarasikan dua kali | `error` |

**Tidak dikirim:**

| Usulan | Kenapa |
|---|---|
| API-03 bentuk respons tidak seragam | `{data}` vs array langsung sama-sama lazim; tidak ada yang bisa disebut benar |
| API-04 versi API saat breaking change | butuh riwayat perilaku, bukan potret kode |
| API-05 input tidak divalidasi | "divalidasi" tak bisa diputuskan tanpa dataflow |
| API-06 OpenAPI tidak cocok dengan route | butuh spek nyata di repo; tidak ada di repo uji |

**Gerbang:** lulus. 31 pemeriksaan di `tests/test_api_domain.py`, 108 kasus
perilaku 0.10.2 tidak berubah. Lihat `docs/PHASE2_API_DOMAIN.md`.

---

## Fase 3 — Domain Security (SELESAI)

**Peringatan:** ini domain yang paling mudah membuat alat dimatikan. Terbukti:
entropi mentah menghasilkan 1.647 temuan di satu repo. Nama kredensial + entropi +
lewati placeholder menyisakan 2 — dan **keduanya salah** (nilainya nama kelas PHP
`Illuminate\...`). Yang akhirnya bekerja adalah bukti, bukan entropi.

**Dikirim:**

| ID | Aturan | Keparahan |
|---|---|---|
| SEC-01 | `.env` dilacak git — empat keadaan: dilacak (`error`, rotasi), tidak dilacak & tidak diabaikan (`warn`, satu `git add .` dari bocor), tidak dilacak & diabaikan (diam), tanpa repo (diam) | `error`/`warn` |
| SEC-02 | Kredensial ditulis sebagai literal di source | `error` di `strict` |
| SEC-03 | `.env.example` kehilangan variabel yang dipakai kode | `warn` |

**Tidak dikirim:** pemeriksaan auth (route tanpa guard, middleware hilang) dan pola
tidak aman (`eval`, konkatenasi SQL, `md5` untuk password) — ketiganya butuh
memahami maksud kode, bukan mencocokkan bentuk.

**Gerbang:** lulus. 29 pemeriksaan (12 negatif), nilai rahasia **tidak pernah**
dicetak — ada tes yang memastikan nilainya absen dari keluaran. Dua temuan SEC-03
nyata ditemukan di situs produksi (ucapanin kehilangan 7 variabel termasuk
`DB_HOST`/`DB_PASSWORD`; silomag kehilangan `VITE_API_URL`) dan **belum
diperbaiki** karena itu berkas produksi. Lihat `docs/PHASE3_SECURITY_DOMAIN.md`.

---

## Fase 4 — Architecture (SELESAI), Testing (tidak dikirim)

Paling akhir karena butuh graf dependensi.

**Dikirim:**

| ID | Aturan | Keparahan |
|---|---|---|
| ARCH-01 | Impor melingkar, dilaporkan per komponen — satu simpul berisi anggotanya, bukan satu temuan per edge | `error` di `strict`, `warn` di preset lain |
| ARCH-02 | Impor menunjuk berkas yang tidak ada | `warn` |

**Gugur setelah diukur** — ini yang membuat halaman aturan menjanjikan empat
domain, bukan lima:

| Usulan | Terukur | Putusan |
|---|---|---|
| ARCH "controller tidak boleh menyentuh model" | 6 dari 7 controller Laravel nyata melakukannya | ditolak — idiom resmi framework |
| ARCH-03 "direktori tak dikenal" | menyala di `scripts/`, `docs/`, `public/`, `shared/` | ditolak — tidak ada daftar direktori yang sah |
| ARCH "berkas terlalu besar" | ambangnya pilihan, bukan fakta | ditolak — selera |
| TEST-01 "test tidak sejajar modul" | silomag: 15 tes untuk 3 workspace; pemetaan 1:1 tak pernah ada | ditolak |
| TEST-02 "ambang coverage dari config" | ambang itu pilihan proyek | ditolak |
| TEST-03 "test yang selalu skip" | nol `.skip` di seluruh repo di mesin ini | ditolak — aturan yang tak pernah menyala tak diketahui bekerja |

**Gerbang:** seluruh perilaku 0.10.2 tidak berubah (108 kasus, 0 exit/0 temuan),
dan siklus/impor rusak yang ditanam di salinan repo 143 berkas PHP tertangkap
tanpa temuan lain. Lihat `docs/PHASE4_ARCHITECTURE_DOMAIN.md`.

---

## Fase 5 — DX (SELESAI)

| Fitur | Alasan |
|---|---|
| `ironclad init` mendeteksi stack | menghilangkan pilihan yang tidak perlu |
| `ironclad doctor` lengkap | satu perintah untuk "kenapa tidak jalan" |
| `ironclad rules list/--explain` | orang tidak bisa memercayai aturan yang tak bisa dibaca |
| `ironclad preset list` | konsistensi dengan perintah lain |
| `--dry-run` untuk init | syarat "aman dijalankan ulang" |

**Gerbang Fase 5:** `init` pada repo dengan `.agent/` yang sudah ada **tidak
mengubah apa pun** kecuali diminta.

**Hasil:** lulus, diuji dengan hash pohon (bukan pembacaan kode). Lihat
`docs/PHASE5_DX.md`. Tiga perintah baru: `doctor`, `rules`, `rules explain`;
`init` mendeteksi stack; `--dry-run` menulis 0 berkas. Empat bug ditemukan dengan
menjalankannya pada repo nyata, termasuk policy induk yang terpakai diam-diam dan
help yang terpotong.

---

## Fase 6 — Distribusi & publikasi (KODE SELESAI, penerbitan menunggu)

- Repo `wilsench/ironclad-next`, migrasi riwayat.
- Rilis ditandai, `release-check.sh` hijau.
- Dokumentasi ID/EN diperbarui: **empat domain yang benar-benar berjalan**, bukan
  satu, dan bukan lima. Domain testing tidak dikirim karena ketiga aturannya
  gugur saat diukur (lihat tabel di Fase 4).
- **Tidak ada push/publish tanpa persetujuan eksplisit.**

**Dua bug distribusi ditemukan saat mengerjakan fase ini** — keduanya lolos dari
penjaga rilis yang lama:

| # | Bug | Akibat |
|---|---|---|
| D-1 | `sync-mirror.sh` tidak pernah menyalin `ironclad_core/` | jalur `curl\|bash` memasang cangkang tanpa mesin; `npx` selamat karena menyalin seluruh repo |
| D-2 | `release-check.sh` membandingkan string versi | mirror `0.10.2` + repo `0.10.2` = "agrees everywhere" walau payload tidak bisa jalan |

Bug ketiga ditemukan oleh tes yang baru: `DIGEST` bergantung pada locale, jadi
cocok di mesin ini dan berbeda di mesin lain. Diperbaiki dengan `LC_ALL=C`.

**Gerbang:** `test_distribution.py` 45/45 (baru), gerbang lain 22/31/29/23/43,
108 kasus perilaku 0 berubah, `curl|bash` dan `npx` diuji di HOME sandbox.
`release-check.sh` kini **menolak** (exit 1) mirror live yang belum disinkronkan
— itu perilaku yang benar. Lihat `docs/PHASE6_DISTRIBUTION.md`.

---

## Ringkasan ketergantungan

```
Fase 0 ──► Fase 0.5 ──► Fase 1 ──► Fase 2 ──► Fase 3 ──► Fase 4 ──► Fase 5 ──► Fase 6
 audit      bug+CI       core       API        security    arch+test    DX       rilis
                         └────────┴──────────┴───────────┘
                              butuh persetujuan per fase
```

Fase 2–4 masing-masing butuh keputusan: **yang mana dulu** bila waktu terbatas.
Rekomendasi saya: API dulu, Security kedua, dan **jangan** mengerjakan keduanya
sekaligus — dua domain serentak berarti dua kali false positive sebelum ada yang
mempercayai alat ini.

---

## Di luar cakupan (sengaja)

- Layanan hosted / akun / telemetri.
- Menulis ulang installer di Node.
- Mengganti nama ID aturan.
- Auto-fix yang mengubah source code aplikasi.
- Dukungan semua framework sekaligus.
