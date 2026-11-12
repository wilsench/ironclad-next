# Feature Parity — apa yang harus selamat

**Aturan:** setiap butir di bawah adalah **kontrak**, bukan saran. Ironclad Next
boleh mengubah cara mencapai hasil ini, tapi tidak boleh mengubah hasilnya tanpa
persetujuan eksplisit dan catatan migrasi.

Status: `[x]` terverifikasi berjalan pada audit ini · `[ ]` belum diuji.

---

## 1. Perilaku check (kontrak inti)

| # | Kontrak | Status | Bukti |
|---|---|---|---|
| P-01 | `check` tidak menulis berkas apa pun | [x] | `cli/index.mjs:33-56`, `check_schema.py` tak punya `write_text` |
| P-02 | Exit `0` = tak ada temuan severity error | [x] | `check_schema.py:544` |
| P-03 | Exit `1` = ada minimal satu error | [x] | idem |
| P-04 | Exit `2` = error penggunaan / tak ada berkas | [x] | `:451`, `:471` |
| P-05 | Exit `check` **tidak** dipengaruhi jaringan | [x] | `bin/ironclad:59-66` |
| P-06 | `--json` menghasilkan JSON valid dengan kunci `preset`, `source`, `files`, `findings`, `errors`, `warnings` — ditambah `sources` (aditif) | [x] | `:565-570` |
| P-07 | `--strict` menaikkan semua warn → error | [x] | `:521-523` |
| P-08 | `--preset <nama>` **menang** atas preset repo | [x] **DIPERBAIKI** | `check_schema.py:load_preset`, `tests/test_regressions.py` |
| P-09 | `--config <berkas>` menang atas `--preset` | [x] | `:228-235` |
| P-10 | Berkas `.agent/standards.yml` **selalu** dibaca sebagai lapisan; dicari naik ke direktori induk | [x] | `:190-222` |

## 2. Aturan database (ID harus tetap)

| ID | Perilaku | Status | Bukti |
|---|---|---|---|
| DB-01 | enum diblokir (balanced/strict), warning (coherence) | [x] | selftest |
| DB-02 | magic number pada status; HTTP status **dikecualikan** | [x] | selftest "HTTP status codes ignored" |
| DB-03 | status integer tanpa FK/CHECK; FK multi-baris **diterima** | [x] | selftest "multi-line FOREIGN KEY accepted" |
| DB-04 | status teks diblokir | [x] | selftest |
| DB-05 | boolean non-biner; allowlist per preset | [x] | `:104`, `:362-365` |
| DB-06 | uang float biner; `numeric(p,s)` & `bigint` **diterima** | [x] | selftest money |
| DB-07 | timestamp tanpa timezone; `timestampTz` & `*At` diterima | [x] | `:374-383` |
| DB-08 | satu temuan per **proyek**, bukan per berkas | [x] | selftest mixed project |
| COVERAGE | schema tak terbaca dilaporkan, bukan dilewati | [x] | `:512-519` |

**Tambahan yang wajib dipertahankan:** pesan DB-08 tidak boleh mengiklankan
preferensi kantor saat preset `coherence` (`:501-505`, diuji di selftest).

## 3. Preset

| # | Kontrak | Status |
|---|---|---|
| P-20 | Empat preset tetap ada dengan nama sama | [x] |
| P-21 | Severity tiap aturan per preset tidak berubah tanpa persetujuan | [x] |
| P-22 | `coherence`: satu-satunya error keras adalah pencampuran | [x] |
| P-23 | `legacy-friendly`: tidak ada yang memblokir | [x] |
| P-24 | Format YAML tetap terbaca oleh parser lama (subset `key: value` + list `- item`) | [x] |
| P-25 | Preset bisa ditambah tanpa menyentuh kode inti | [x] (cukup menaruh `.yml` di `assets/presets/`) |

## 4. Instruksi agent

| # | Kontrak | Status | Bukti |
|---|---|---|---|
| P-30 | Blok berpagar `<!-- ironclad:begin v1 -->` / `<!-- ironclad:end -->` | [x] | `agent_files.py:25-26` |
| P-31 | Pasang dua kali → `unchanged`, blok tidak dobel | [x] | install sandbox |
| P-32 | Uninstall mencabut blok, **tidak** menyentuh tulisan pengguna | [x] | sandbox: `.claude/` kosong, isi lain utuh |
| P-33 | `--mode house` tidak turun ke `ask` saat reinstall | [x] | `detect_installed_body():166-184` |
| P-34 | Tidak membuat direktori config agent yang belum ada | [x] | `:219-222` |
| P-35 | 5 target per-repo + 7 target global tetap didukung | [x] | `:78-100` |
| P-36 | Laporan jujur bila nol agent ditulis (`IRONCLAD_AGENTS_WRITTEN=0`) | [x] | `:232`, `install.sh:381-390` |
| P-37 | Blok tetap di bawah ~1.500 char (anggaran konteks agent) | [x] | ask 1.063 / house ±1.208 |

## 5. Installer

| # | Kontrak | Status |
|---|---|---|
| P-40 | `npx` dan `curl \| bash` menjalankan installer yang sama | [x] |
| P-41 | Urutan sumber: lokal → `IRONCLAD_BASE` → mirror → GitHub | [x] |
| P-42 | Tolak jalan tanpa `python3` (exit 3), jangan klaim sukses | [x] |
| P-43 | `--uninstall` menyapu semua lokasi yang dikenal | [x] |
| P-44 | `--purge` hanya menghapus berkas proyek | [x] |
| P-45 | Semua flag yang ada tetap bekerja | [x] |
| P-46 | Payload **lengkap** di semua jalur (dijaga tes `curl|bash` nyata) | [x] **DIPERBAIKI** |
| P-47 | `install.sh` tidak mengubah source code aplikasi | [x] |

## 6. Drill & grader

| # | Kontrak | Status |
|---|---|---|
| P-50 | `--selftest` deterministik, exit 0 saat semua lulus | [x] (20 PASS) |
| P-51 | `--grade` menerima FK inline **dan** table-level | [x] |
| P-52 | `--grade <dir>` menggabungkan berkas sekitarnya | [x] |
| P-53 | Grader tidak memanggil model | [x] |
| P-54 | `--prompt` tidak membocorkan jawaban | [x] |

## 7. Update check

| # | Kontrak | Status |
|---|---|---|
| P-60 | Tidak pernah memblokir (timeout 6 s) | [x] |
| P-61 | Tidak pernah mengubah exit code perintah lain | [x] |
| P-62 | Maksimal sekali per 24 jam (cache) | [x] |
| P-63 | Tidak bertanya tanpa TTY | [x] |
| P-64 | `--check` memakai exit 10 | [x] |
| P-65 | Tidak pernah auto-install | [x] |

## 8. Dokumentasi & rilis

| # | Kontrak | Status |
|---|---|---|
| P-70 | Versi tunggal dari `SKILL.md`, dibaca generator | [x] |
| P-71 | `release-check.sh` gagal bila versi tidak konsisten | [x] |
| P-72 | 18 halaman × 2 bahasa tetap ada | [x] |

---

## 9. Fitur yang diminta tapi **belum ada** (bukan regresi)

Ini target, bukan kontrak:

- `ironclad doctor`
- `ironclad rules list` / `--explain`
- `ironclad preset list`
- `ironclad init` yang mendeteksi stack
- Domain selain database
- Output SARIF untuk GitHub code scanning
- Baseline/suppression yang stabil

---

## 10. Matriks paritas ringkas

| Area | Jumlah kontrak | Terverifikasi | Rusak | Belum diuji |
|---|---|---|---|---|
| check | 10 | 10 | 0 | 0 |
| aturan DB | 9 | 9 | 0 | 0 |
| preset | 6 | 5 | 0 | 1 |
| instruksi agent | 8 | 8 | 0 | 0 |
| installer | 8 | 8 | 0 | 0 |
| drill/grader | 5 | 5 | 0 | 0 |
| update | 6 | 6 | 0 | 0 |
| docs/rilis | 3 | 3 | 0 | 0 |
| **Total** | **55** | **54** | **0** | **1** |

Ketiga bug (P-08, P-46, dan BUG-C yang ditemukan saat memperbaikinya) sudah
diperbaiki di Fase 0.5 dan dikunci oleh `tests/test_regressions.py` — 19
pemeriksaan, dijalankan di CI. Satu kontrak masih belum diuji (P-25).
