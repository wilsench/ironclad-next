# Compatibility Plan

**Prinsip:** pengguna 0.10.2 harus bisa pindah ke Ironclad Next tanpa mengubah
skrip CI, tanpa mengubah ID aturan, dan tanpa mengubah exit code.

---

## 1. Permukaan publik yang dibekukan

Ini yang dilihat orang di luar repo. Mengubahnya = breaking change.

| Permukaan | Contoh | Boleh berubah? |
|---|---|---|
| ID aturan | `DB-01` … `DB-08`, `COVERAGE` | **Tidak** (ada di skrip CI) |
| Exit code | 0 / 1 / 2 / 10 / 3 | **Tidak** |
| Nama preset | `balanced`, `strict`, `legacy-friendly`, `coherence` | **Tidak** |
| Berkas konfigurasi | `.agent/standards.yml`, `.agent/standards.md` | **Tidak** |
| Kunci YAML | `name`, `rules`, `exceptions`, `boolean_allowlist` | Tidak dihapus; boleh ditambah |
| Nama perintah | `check`, `init`, `preset`, `status`, `version`, `drill`, `attach`, `update` | Tidak dihapus |
| Flag | lihat `install.sh:15-31` | Tidak dihapus |
| Sentinel blok | `<!-- ironclad:begin v1 -->` | Tidak (versi baru = sentinel baru + migrasi) |
| Target agent | `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursor/rules/*.mdc` | Tidak |

---

## 2. Perubahan yang dianggap aman

| Perubahan | Kenapa aman |
|---|---|
| Menambah kunci di JSON output | konsumen mengabaikan kunci tak dikenal |
| Menambah perintah baru | tidak mengubah yang lama |
| Menambah kunci `domains:` di YAML | parser lama mengabaikan |
| Menambah field di `Finding` | konsumen lama memakai kunci lama |
| Memperbaiki pesan | selama ID aturan & severity tidak berubah |
| Menambah preset baru | pilihan lama tetap ada |

---

## 3. Perubahan yang butuh migrasi eksplisit

| Perubahan | Jalur migrasi |
|---|---|
| Format blok agent baru | sentinel `v2` + `ironclad attach --upgrade` yang mengganti `v1` (tidak menumpuk) |
| Struktur `.agent/` | pembacaan **kedua** format selama 1 major |
| Hapus aturan | tidak dihapus; ubah ke `off` dan dokumentasikan |
| Rename perintah | alias dipertahankan minimal 1 major |

---

## 4. Jaminan untuk tiga profil pengguna

### 4.1 Pengguna `curl \| bash`

- Masih satu perintah.
- **Wajib** mendapat payload lengkap (BUG-A diperbaiki).
- Tetap tanpa pertanyaan interaktif (`ask_preset` sudah aman tanpa TTY).

### 4.2 Pengguna `npx`

- Perintah yang sama, perilaku yang sama (shim tetap meneruskan ke installer).
- Tag rilis dipertahankan; `npx ...#vX.Y.Z` harus terus bekerja.

### 4.3 Pengguna CI

Ini yang paling ketat — CI memakai exit code dan ID aturan.

```yaml
- run: ironclad check . --preset strict
```

Kontrak:
- exit 1 bila ada error, 0 bila bersih, **apa pun yang terjadi pada jaringan**;
- `--preset strict` **benar-benar** berlaku (BUG-B diperbaiki);
- output stabil untuk di-parse (`--json`).

---

## 5. Matriks uji kompatibilitas (harus dijalankan di Fase 1)

| # | Uji | Kriteria lulus |
|---|---|---|
| C-01 | Selftest 20 fixture lama | 20/20 PASS, fixture tidak diubah |
| C-02 | `examples/good.sql --preset strict` | exit 0 |
| C-03 | `examples/bad.sql --preset strict` | exit ≠ 0 |
| C-04 | `examples/bad.sql --preset legacy-friendly` | exit 0 |
| C-05 | Repo dengan `.agent/standards.yml` format lama | terbaca, severity sesuai |
| C-06 | `--config` menang atas `--preset` | sesuai dokumen |
| C-07 | `--preset` menang atas preset repo | sesuai dokumen (**BUG-B**) |
| C-08 | Install → install lagi | `unchanged`, blok tunggal |
| C-09 | Install → uninstall | tidak ada sisa blok; tulisan pengguna utuh |
| C-10 | Install lewat mirror (script sendirian) | `update_check.py` + `coherence.yml` ada |
| C-11 | `check` offline | exit code sama dengan saat online |
| C-12 | `check` tanpa `python3` | pesan jelas, exit 3 |
| C-13 | `--json` | JSON valid, kunci lama ada |
| C-14 | `.mdc` Cursor punya header YAML | tidak dobel saat reinstall |
| C-15 | `ironclad version` | `mode` = `ask`/`house`, `block` = angka char |
| C-16 | Python 3.8 | semua skrip jalan |

**C-01 adalah gerbang utama.** Selama fixture tidak berubah dan 20/20 tetap
hijau, refactor tidak mengubah perilaku.

---

## 6. Risiko yang sudah diketahui dan diterima

| Risiko | Status | Catatan |
|---|---|---|
| Checker berbasis regex, bukan parser SQL | diterima | false positive mungkin pada sintaks tak lazim; didokumentasikan |
| Framework Django/Rails/TypeORM/dll belum didukung | diterima | exit 2 / `COVERAGE` warning, bukan lulus diam-diam |
| Hanya Hermes + Antigravity yang diuji perilakunya | diterima | sisanya diverifikasi jalur file |
| `npx` meng-cache | diterima | pakai tag baru / `npm cache clean` |
| GitHub Releases API 404 → pakai daftar tag | diterima | catatan rilis diturunkan dari commit |

---

## 7. Rencana deprecation (bila perlu)

Tidak ada rencana menghapus apa pun di Next. Bila suatu saat perlu:

1. Tandai di dokumen + output (`deprecated` di JSON).
2. Pertahankan minimal **dua** rilis minor.
3. Sediakan `ironclad doctor` yang menunjukkan cara pindah.
4. Baru hapus di major.

---

## 8. Gerbang sebelum rilis Next

Sebuah rilis Next tidak boleh diberi tag kecuali:

- [ ] C-01 … C-16 semuanya lulus, hasilnya ditempel di catatan rilis
- [ ] BUG-A dan BUG-B tertutup dengan test regresi
- [ ] `release-check.sh` hijau
- [ ] `drill.py --selftest` hijau
- [ ] Instalasi nyata di HOME bersih (bukan hanya unit test)
- [ ] Dokumen `FEATURE_PARITY.md` diperbarui: tidak ada kontrak yang turun status
