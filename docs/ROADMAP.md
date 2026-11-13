# Roadmap — Ironclad Next

**Prinsip urutan:** perbaiki kebohongan dulu, baru bangun di atasnya. Sebuah
arsitektur baru yang mewarisi dua bug "lulus palsu" hanya menyebarkan bug itu
ke lima domain.

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

## Fase 2 — Domain API

**Kenapa kedua:** kontraknya paling jelas (HTTP, OpenAPI) dan paling murah
diverifikasi.

**Aturan awal (usulan; severity `warn` semua di rilis pertama):**

| ID | Aturan |
|---|---|
| API-01 | Endpoint tidak konsisten gaya (`/users` vs `/getUsers`) |
| API-02 | Status code tidak sesuai makna (200 untuk error, 201 tanpa Location) |
| API-03 | Bentuk respons tidak seragam (`{data}` vs array langsung) |
| API-04 | Tidak ada versi API saat ada breaking change |
| API-05 | Input tidak divalidasi sebelum dipakai |
| API-06 | OpenAPI ada tapi tidak cocok dengan route |

**Gerbang:**
- [ ] Minimal 3 tanya-jawab nyata: repo contoh dengan pelanggaran API
- [ ] False positive < 10% pada 3 repo uji
- [ ] `coverage` jujur: framework yang tidak dikenal → `skipped`, bukan lulus

**Risiko:** sedang. Banyak orang punya "gaya" berbeda; default `warn`.

---

## Fase 3 — Domain Security

**Peringatan:** ini domain yang paling mudah membuat alat dimatikan. Regex pada
secret menghasilkan false positive pada fixture test dan string contoh.

**Pekerjaan:**
- Deteksi secret dengan entropi + allowlist + sadar `.env.example`.
- Pemeriksaan auth: route tanpa guard, middleware hilang.
- Pola tidak aman: `eval`, SQL string concat, `md5` untuk password.

**Gerbang:**
- [ ] Nol false positive pada repo uji yang punya fixture secret
- [ ] Setiap temuan punya `remediation` konkret
- [ ] Redaksi: nilai secret **tidak pernah** dicetak (hanya `sha256` potong)

---

## Fase 4 — Architecture & Testing

Paling akhir karena butuh graf dependensi.

| Domain | Aturan awal |
|---|---|
| Architecture | ARCH-01 impor melingkar; ARCH-02 lapisan dilanggar (controller → model langsung); ARCH-03 direktori tak dikenal |
| Testing | TEST-01 test tidak sejajar modul; TEST-02 ambang coverage dari config; TEST-03 test yang selalu skip |

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

## Fase 6 — Distribusi & publikasi (butuh persetujuan)

- Repo `wilsench/ironclad-next`, migrasi riwayat.
- Rilis ditandai, `release-check.sh` hijau.
- Dokumentasi ID/EN diperbarui: lima domain, bukan satu.
- **Tidak ada push/publish tanpa persetujuan eksplisit.**

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
