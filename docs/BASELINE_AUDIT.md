# Baseline Audit — Ironclad 0.10.2

**Tanggal audit:** 2026-11-13
**Objek:** `wilsench/ironclad` @ `a98029e` (main, tag `v0.10.2`)
**Metode:** pembacaan seluruh source code, plus eksekusi nyata (selftest, install,
uninstall, CLI) di HOME sandbox terpisah. Setiap klaim di dokumen ini punya
rujukan file:baris atau output perintah yang benar-benar dijalankan.

> Dokumen ini **tidak** mengubah apa pun. Repo asli tidak disentuh; semua uji
> dilakukan pada salinan di `/root/projects/ironclad-next` dan HOME sandbox
> `/root/audit_install/home*`.

---

## 1. Ringkasan eksekutif

Ironclad 0.10.2 adalah alat yang **matang untuk satu domain** (database/schema)
dan **belum punya arsitektur untuk domain lain**. Kekuatannya bukan pada jumlah
aturan — hanya 8 aturan — tapi pada hal yang jarang dimiliki linter:

1. **Invarian exit code.** `check` selalu 0/1/2 dan tidak pernah berubah karena
   jaringan atau pembaruan (`check_schema.py:544`).
2. **Kejujuran cakupan.** Kalau repo punya schema yang tidak bisa dibaca, alat
   ini menolak mengaku lulus (`check_schema.py:456-471`).
3. **Satu aturan lintas-berkas** (DB-08) yang menangkap masalah organisasi, bukan
   masalah sintaks (`check_schema.py:484-510`).
4. **Blok instruksi yang ditanam** ke konfigurasi agent, sehingga aturan berlaku
   sebelum kode ditulis — bukan sesudahnya (`agent_files.py:28-70`).

Kelemahan utamanya juga jelas: **semua domain masa depan akan menabrak satu
berkas 548 baris** yang mencampur pemuatan konfigurasi, penemuan file, mesin
aturan, delapan implementasi aturan, dan pelaporan.

**Dua bug nyata ditemukan saat audit** — keduanya sudah direproduksi, bukan
dugaan. Lihat §7.

---

## 2. Ikhtisar repository

| Properti | Nilai | Bukti |
|---|---|---|
| Total file (tanpa `.git`) | 119 (113 sebelum 5 dokumen audit ini) | `find . -type f \| wc -l` |
| Baris Python | 2.017 | `wc -l skills/ironclad/scripts/*.py` |
| Baris shell | 546 | `install.sh` + `bin/ironclad` + 2 skrip rilis |
| Baris JS (Node) | 70 | `cli/index.mjs` |
| Baris Markdown | 6.053 | docs ID/EN + skill |
| Ukuran `site/` (artefak build) | 788 KB | `du -sh site` |
| Ukuran `docs/` (sumber) | 308 KB | `du -sh docs` |
| Bahasa runtime | Python 3.8+, Bash, Node ≥18 | `package.json:20`, `install.sh:37` |
| Dependensi pihak ketiga | **nol** | semua `import` adalah stdlib |

Nol dependensi adalah keputusan sadar dan harus dipertahankan: checker berjalan
di CI tanpa `pip install`, dan parser YAML ditulis sendiri supaya alat ini tidak
gagal karena PyYAML tidak ada (`check_schema.py:140-168`).

### Struktur direktori

```
skills/ironclad/            ← payload yang di-install (ini produknya)
  SKILL.md                  ← 164 baris, "pemahaman", bukan buku aturan
  bin/ironclad              ← 215 baris, dispatcher perintah
  scripts/
    check_schema.py         ← 548 baris, 8 aturan DB + mesin
    drill.py                ← 579 baris, selftest + grader
    agent_files.py          ← 258 baris, blok instruksi ke config agent
    init_standards.py       ← 194 baris, bootstrap .agent/
    update_check.py         ← 438 baris, cek versi + menu 4 pilihan
  assets/presets/*.yml      ← 4 preset
  references/*.md           ← 3 dokumen rujukan
  templates/standards.md    ← 51 baris, catatan keputusan
cli/index.mjs               ← shim npx (tidak menyalin logika installer)
install.sh                  ← 402 baris, satu-satunya installer
docs/                       ← sumber dokumentasi (markdown per halaman)
site/                       ← hasil build (artefak, jangan diedit tangan)
examples/                   ← 4 fixture SQL/PHP
scripts/                    ← sync-mirror, release-check, set-repo-owner
.github/workflows/          ← CI: selftest gate
```

---

## 3. Stack teknologi

| Lapis | Teknologi | Catatan |
|---|---|---|
| Runtime aturan | Python stdlib | tanpa venv, tanpa pip |
| Distribusi | Bash installer + Node shim | `npx` hanya pembungkus |
| Dokumentasi | Python generator (`docs/build.py`) | markdown → HTML statis |
| Situs | HTML/CSS/JS statis | disajikan nginx, bukan Next.js |
| CI | GitHub Actions | `ubuntu-latest`, Python 3.11 |
| Integrasi agent | File konvensi (AGENTS.md, CLAUDE.md, GEMINI.md, .mdc) | bukan API, bukan plugin |

Tidak ada database, tidak ada layanan, tidak ada telemetri. Semua keadaan
tersimpan di repo pengguna (`.agent/`) dan satu berkas cache di
`~/.ironclad/update-check.json` (`update_check.py:39-40`).

---

## 4. Inventaris fitur yang ada

Semuanya **wajib dipertahankan**. Kolom "Bukti" menunjuk kode, bukan README.

### 4.1 Mesin aturan database (`check_schema.py`)

| Aturan | Arti | Default (balanced) | Bukti |
|---|---|---|---|
| DB-01 | native enum di schema | error | `:67-77`, `:324-328` |
| DB-02 | magic number pada field status | error | `:91-96`, `:339-355` |
| DB-03 | status integer tanpa FK/CHECK | warn | `:396-422` |
| DB-04 | status disimpan sebagai teks | error | `:98-102`, `:357-360` |
| DB-05 | boolean untuk konsep non-biner | warn | `:104`, `:362-365` |
| DB-06 | uang sebagai float biner | warn | `:106-109`, `:367-372` |
| DB-07 | timestamp tanpa timezone | warn | `:111-115`, `:374-383` |
| DB-08 | proyek mencampur gaya status | warn | `:484-510` |
| COVERAGE | ada schema yang tidak terbaca | warn | `:512-519` |

Detail yang mudah hilang saat refactor dan harus dijaga:

- **~30 pengecualian yang disengaja**, masing-masing dengan alasan di komentar:
  HTTP status bukan schema (`:79-88`), `CHECK` sebagai tempat sah untuk literal
  (`:330-337`), FK multi-baris (`:385-422`), `numeric(12,2)` bukan float
  (`drill.py:345-367`), idempoten `is_migration_like` (`:258-267`).
- **Deteksi stack tak didukung** untuk 9 ekstensi, karena lulus diam-diam pada
  repo yang separuh tak terbaca adalah kegagalan terburuk (`:125-137`).
- **Pencarian preset berlapis**: `--config` > `--preset` > `.agent/standards.yml`
  (menelusuri direktori induk) > `balanced` bawaan (`:171-215`).
- **Parser YAML tanpa dependensi** yang hanya mendukung subset yang dikirim
  sendiri (`:144-168`).

### 4.2 Preset (4 buah)

| Preset | Karakter | Bukti |
|---|---|---|
| `balanced` | default; enum & text blokir, sisanya warn | `assets/presets/balanced.yml` |
| `strict` | semua blokir | `assets/presets/strict.yml` |
| `legacy-friendly` | semua warn + allowlist boolean lebih luas | `assets/presets/legacy-friendly.yml` |
| `coherence` | tanpa selera; hanya **pencampuran** yang gagal | `assets/presets/coherence.yml` |

`coherence` adalah preset paling penting secara strategis: ia memisahkan
*mekanisme* dari *kebijakan*, sehingga orang yang tidak setuju dengan gaya kantor
tetap bisa memakai alat ini (`check_schema.py:501-505`).

### 4.3 Instruksi agent (`agent_files.py`)

- Dua badan instruksi: `ASK_BODY` (netral, 1.063 char) dan `HOUSE_BODY`
  (default kantor, ±1.208 char) (`:28-70`).
- Blok berpagar `<!-- ironclad:begin v1 -->` … `<!-- ironclad:end -->` sehingga
  pasang-ulang mengganti di tempat, dan uninstall mencabut **hanya** milik kita
  (`:25-26`, `:109-150`).
- 5 target per-repo (`:78-84`) + 7 target global (`:90-100`), dengan aturan:
  jangan buat direktori config agent yang tidak dipakai (`:219-222`).
- `detect_installed_body()` mencegah reinstall diam-diam menurunkan `house` ke
  `ask` (`:166-184`).
- Menghormati mode tersimpan; `--mode` hanya perlu sekali (`:201-206`).
- **Idempoten**: dipasang dua kali menghasilkan `unchanged` (diverifikasi, §6).

### 4.4 CLI (`bin/ironclad`)

`check`, `init`, `preset`, `status`, `version`, `drill`, `attach`, `update`.
Exit code: checker 0/1/2, installer 3 saat `python3` tidak ada, `update --check`
memakai 10 (bukan 1) supaya bisa dibedakan dari temuan schema.

### 4.5 Pemeriksaan pembaruan (`update_check.py`)

Cache 24 jam, time 6 detik, tidak pernah mengubah exit code perintah lain,
tidak pernah bertanya tanpa TTY, `--check`/`--notes`/`--hint`/`--mute`,
i18n `id`/`en`. Desain ini benar dan harus dipertahankan apa adanya
(`:1-17`).

### 4.6 Drill & grader (`drill.py`)

- `--selftest`: 20 pemeriksaan deterministik atas gate (dijalankan, §6).
- `--grade`: 8 kriteria atas jawaban agent, termasuk dua ejaan FK yang sah.
- `--prompt`: tugas tanpa petunjuk, dalam ID/EN.
- Prinsip yang harus dijaga: **grader tidak memanggil model** (`:17-19`).

### 4.7 Distribusi

- `install.sh` — satu-satunya installer (402 baris), mendukung `--target`,
  `--dir`, `--project`, `--preset`, `--policy-only`, `--repo`, `--ref`,
  `--uninstall`, `--purge`, `--no-bin`, `--no-agent-files`, `--mode`.
- Urutan sumber payload: checkout lokal → `IRONCLAD_BASE` → mirror
  `wilsench.my.id` → GitHub (`install.sh:264-277`).
- `cli/index.mjs` — shim 70 baris; **sengaja** tidak menyalin logika, supaya
  `npx` dan `curl|bash` menjalankan kode yang sama (`:5-8`). Keputusan ini benar.
- Menolak jalan tanpa `python3` (exit 3) alih-alih melapor sukses palsu
  (`install.sh:96-112`).

### 4.8 Dokumentasi

- 18 halaman × 2 bahasa (ID/EN) di `docs/pages/`.
- Generator `docs/build.py` membaca versi dari `SKILL.md`, bukan hardcoded
  (`:36-51`).
- `scripts/release-check.sh`: 7 pemeriksaan konsistensi rilis.
- `scripts/sync-mirror.sh`: menyalin payload ke mirror publik.

---

## 5. Inventaris integrasi CLI & agent

### 5.1 Permukaan perintah

| Perintah | Status | Perilaku |
|---|---|---|
| `ironclad check` | ada | read-only, exit 0/1/2 |
| `ironclad init` | ada | menulis `.agent/` + `scripts/` |
| `ironclad preset <n>` | ada | ganti preset |
| `ironclad status` | ada | info skill/repo/policy |
| `ironclad version` | ada | versi + mode + ukuran blok |
| `ironclad drill` | ada | selftest / prompt / grade |
| `ironclad attach` | ada | tulis blok ke config agent |
| `ironclad update` | ada | menu 4 pilihan |
| `ironclad doctor` | **tidak ada** | diusulkan di fase berikutnya |
| `ironclad rules list` | **tidak ada** | aturan hanya bisa dibaca dari kode |
| `ironclad preset list` | **tidak ada** | ada `check_schema.py --list-presets`, tapi bukan lewat CLI |

### 5.2 Target agent

| Agent | Per-repo | Global | Bukti |
|---|---|---|---|
| Claude Code | `CLAUDE.md` | `~/.claude/CLAUDE.md` | `agent_files.py:79,91` |
| Codex | `AGENTS.md` | `~/.codex/AGENTS.md` | `:79,92` |
| Gemini CLI / Antigravity | `GEMINI.md` | `~/.gemini/AGENTS.md` + `GEMINI.md` | `:80,95-96` |
| Cursor | `.cursor/rules/ironclad.mdc` | idem (global) | `:81,97` |
| GitHub Copilot | `.github/copilot-instructions.md` | — | `:82` |
| opencode | `AGENTS.md` | `~/.config/opencode/AGENTS.md` | `:79,98` |
| Hermes | — | `~/.agents/AGENTS.md` | `:99` |

Batasan jujur: **hanya Hermes dan Antigravity yang perilakunya pernah diuji.**
Claude Code, Codex, opencode, Cursor hanya diverifikasi jalur filenya.

---

## 6. Status pengujian saat ini

Semua dijalankan pada audit ini, bukan dikutip dari dokumen lain.

### 6.1 Selftest gate

```
$ python3 skills/ironclad/scripts/drill.py --selftest
  PASS  enum blocked in the default preset
  PASS  integer + lookup + fk accepted
  … (20 baris PASS)
  PASS  grade a directory: lookup in a sibling file counts
All checks passed.
EXIT=0
```

Catatan: di dalam output ada baris `FAIL` dan `7/8 criteria` — itu **hasil yang
diharapkan** dari uji negatif (grader menolak jawaban salah), bukan kegagalan
selftest.

### 6.2 Konsistensi rilis

```
$ bash scripts/release-check.sh
skill version 0.10.2 · package.json 0.10.2 · tag v0.10.2 contains 0.10.2
reachable from origin/main yes · live mirror 0.10.2
Release state agrees everywhere.
EXIT=0
```

### 6.3 Instalasi nyata (HOME sandbox, 3 skenario)

| Skenario | Hasil |
|---|---|
| Install dari checkout lokal | OK; 4 berkas agent ditulis; launcher dibuat |
| Install kedua kali | `unchanged` ×4; blok tidak dobel (`grep -c` = 1) |
| `--uninstall` | skill + launcher terhapus; `.claude/` bersih; file proyek dibiarkan |
| Install dari script sendirian (jalur mirror) | **OK tapi payload tidak lengkap** → §7.1 |

### 6.4 Yang **tidak** tercakup pengujian

- Tidak ada **satu pun** test unit (`grep -rl "def test_"` → kosong). Semua
  jaminan berasal dari `drill.py --selftest`, yang merupakan uji integrasi
  end-to-end. Tidak ada test untuk `agent_files.py`, `update_check.py` (selain
  2 fungsi murni), `install.sh`, atau `cli/index.mjs`.
- Tidak ada test yang menjalankan `install.sh` di CI. Bug §7.1 bisa lolos justru
  karena ini.
- Tidak ada test matriks Python 3.8 (versi minimum yang diklaim).

---

## 7. Bug nyata yang ditemukan saat audit

Keduanya **direproduksi**, bukan dugaan dari membaca kode.

### 7.1 BUG-A — Jalur `curl | bash` memasang skill tanpa `update_check.py` dan `coherence.yml`

**Keparahan: tinggi** (pengguna baru lewat jalur ini; lihat §8).

`install.sh:231-235` mendaftar berkas yang diunduh, dan daftar itu **tidak
menyertakan** dua berkas yang sudah ada di repo sejak 0.9.x/0.10.0:

```
FILES="SKILL.md templates/standards.md
references/database.md references/presets.md references/extending.md
assets/presets/balanced.yml assets/presets/strict.yml assets/presets/legacy-friendly.yml
scripts/check_schema.py scripts/init_standards.py scripts/drill.py
scripts/agent_files.py bin/ironclad"
```

Keduanya ada di mirror (diverifikasi: `HTTP 200`), hanya tidak ikut didaftar.
Jalur checkout lokal tidak terpengaruh karena `copy_from_local()` menyalin
seluruh direktori (`:253-262`).

**Dampak terukur** (HOME sandbox, install dari script sendirian):

```
$ ls .agents/skills/ironclad/scripts/
agent_files.py  check_schema.py  drill.py  init_standards.py      ← update_check.py TIDAK ADA
$ ls .agents/skills/ironclad/assets/presets/
balanced.yml  legacy-friendly.yml  strict.yml                     ← coherence.yml TIDAK ADA
$ ironclad update --check
ironclad: update check is missing at …/update_check.py (re-run the installer)
$ ironclad preset coherence
ironclad: unknown preset: coherence (balanced|strict|legacy-friendly|coherence)
```

Ini regresi yang ironis: 0.10.2 adalah rilis yang **menambahkan** `ironclad
update`, dan jalur instalasi utamanya tidak mengirim berkasnya.

### 7.2 BUG-B — `check --preset <nama>` diabaikan diam-diam

**Keparahan: sedang-tinggi** (menghasilkan "lulus" palsu di CI).

`bin/ironclad:58` menyusun argumen dengan `--preset` repo **di belakang**
argumen pengguna:

```bash
python3 "$CHECKER" "${@:-.}" --preset "$preset" || rc=$?
```

`argparse` memakai nilai **terakhir**, jadi `--preset` dari pengguna selalu
ditimpa. Dibuktikan:

```
$ check_schema.py m.sql --preset strict                        → 1 error   (benar)
$ check_schema.py m.sql --preset strict --preset balanced       → 0 error   (tertimpa)
$ ironclad check m.sql --preset strict                          → 0 error   ← bug
```

Artinya: skrip CI yang menulis `ironclad check . --preset strict` akan berjalan
sebagai `balanced` dan **lolos** padahal seharusnya gagal. Ini kelas kesalahan
yang paling berbahaya untuk sebuah gate.

Akar masalahnya arsitektural: nilai default disisipkan sebagai argumen CLI, bukan
sebagai nilai yang bisa ditimpa secara eksplisit.

### 7.3 BUG-C — Repo dengan preset `coherence` sama sekali tidak bisa diperiksa

**Keparahan: tinggi** (alat berhenti bekerja, bukan sekadar salah menilai).

Ditemukan saat memperbaiki BUG-B, dan penyebabnya satu akar dengan BUG-B:
wrapper mengubah *nama* preset repo menjadi argumen `--preset`, padahal
`load_preset` (`:183-190` di 0.10.2) **melewati** pencarian
`.agent/standards.yml` bila `--preset` diberikan:

```python
if not layers:          # hanya bila --preset TIDAK diberikan
    ...cari .agent/standards.yml...
```

Jadi `--preset coherence` dikirim, berkas repo tidak pernah dibaca, dan nama
`coherence` ditolak — bukan karena tidak ada, tapi karena presets dibaca dari
`assets/presets/` di direktori skill. Di mesin yang dipasang lewat `curl|bash`
berkas itu tidak ada (BUG-A), sehingga:

```
$ ironclad check .
unknown preset 'coherence' — available: balanced, legacy-friendly, strict
$ echo $?
2
```

Ini juga berarti **`exceptions` dan `boolean_allowlist` milik repo tidak pernah
dipakai** lewat wrapper, karena seluruh berkas repo dilewati.

Perbaikan BUG-B secara struktural (menghapus penyisipan `--preset`, membiarkan
checker membaca berkas repo sendiri) menutup BUG-C sekaligus. Tambalan kedua
diperlukan: berkas yang hanya berisi `name: <preset>` — persis yang ditulis
`ironclad preset` — harus diselesaikan ke aturan preset tersebut, dengan
`exceptions` repo tetap dipertahankan.

---

## 8. Kelemahan arsitektur

Diurutkan berdasarkan dampak terhadap evolusi ke 5 domain.

### 8.1 `check_schema.py` mencampur 5 tanggung jawab

| Baris | Tanggung jawab |
|---|---|
| `:28-137` | konstanta + 36 regex — **domain database** |
| `:144-168` | parser YAML — **infrastruktur** |
| `:171-215` | pemuatan preset berlapis — **konfigurasi** |
| `:219-289` | penemuan file & deteksi stack — **infrastruktur** |
| `:292-424` | eksekusi 8 aturan — **domain database** |
| `:427-544` | CLI, agregasi, pelaporan — **presentasi** |

Menambah domain API berarti menambahkan ±400 baris lagi ke berkas yang sama,
atau menyalin mesin di atas. Keduanya buruk. **Ini hambatan utama.**

### 8.2 Interface aturan tidak ada

Aturan adalah blok `if` di dalam satu loop baris (`:313-383`), bukan unit yang
bisa didaftarkan. Tidak ada cara menambah aturan tanpa menyunting loop inti, dan
tidak ada tempat untuk aturan yang butuh **parse** alih-alih regex.

### 8.3 Semua domain dipaksa regex

`check_schema.py` memakai 36 pemanggilan regex dan nol parser. Untuk DB ini
berhasil karena SQL/Laravel/Prisma lumayan regex-able. Untuk **security**
(deteksi secret, alur auth) dan **architecture** (graf dependensi, siklus),
regex akan menghasilkan false positive yang membunuh kepercayaan pengguna. Ini
persis kegagalan yang sudah dicatat di kode sendiri untuk HTTP status
(`:79-84`).

### 8.4 Tidak ada model hasil yang seragam

`findings` adalah dict anonim dengan kunci `rule`/`severity`/`line`/`msg`/`file`.
Tidak ada `domain`, `position`, `rule_version`, `remediation`, atau `fingerprint`.
Tanpa fingerprint, tidak mungkin membuat baseline/suppression yang stabil —
padahal `legacy-friendly` menjanjikan "gate hanya file baru".

### 8.5 Default via argumen CLI (penyebab BUG-B)

Tidak ada lapisan konfigurasi yang bisa ditimpa; default disisipkan sebagai
argumen (`bin/ironclad:58`). Setiap perintah baru berisiko mengulang bug ini.

### 8.6 `install.sh` menggandakan pengetahuan tentang isi paket

Daftar `FILES` (`:231-235`) adalah manifest kedua yang harus disinkronkan dengan
`package.json:9-15` dan `sync-mirror.sh:15-21`. Tiga daftar, satu kebenaran —
dan yang paling berbahaya (jalur remote) justru yang tidak diuji.

### 8.7 Tidak ada pemisahan "aturan" dari "kebijakan" di data

Severity ada di preset (benar), tapi setiap aturan masih membawa asumsi domain
di dalam kode (mis. saran "use integer code + lookup" `:327`). Saat domain
bertambah, tiap aturan perlu bisa menyatakan *apa yang disarankan* secara
terpisah dari *apakah ia memblokir*.

---

## 9. Usulan arsitektur multi-domain (ringkas)

Detail di `ARCHITECTURE_PROPOSAL.md`. Intinya:

```
core/        engine, registry, model hasil, reporter, config — tidak tahu domain
domains/     database/ api/ security/ architecture/ testing/ — tiap domain
             mendaftarkan aturan; boleh memakai parser sendiri
```

Interface aturan minimal:

```python
class Rule(Protocol):
    id: str            # "DB-01"
    domain: str        # "database"
    severity_default: str
    def check(self, ctx: FileContext) -> Iterable[Finding]: ...
```

`FileContext` menyediakan teks, path, bahasa terdeteksi, dan **parser yang di-cache**
(AST SQL via `sqlglot` bila ada, fallback regex), sehingga aturan tidak pernah
membuka berkas sendiri. Ini yang memungkinkan domain baru memakai parser tanpa
memaksa domain lama berubah.

---

## 10. Risiko kompatibilitas (ringkas)

| Risiko | Mitigasi |
|---|---|
| ID aturan `DB-0x` dipakai di skrip/CI orang | Pertahankan ID apa adanya; jangan renumber |
| Exit code berubah | Bekukan kontrak 0/1/2 (dan 10 untuk `update --check`) |
| Format `.agent/standards.yml` | Tetap dibaca; tambah kunci `domains:` tanpa merusak |
| Blok agent berubah → agent "lupa" | Sentinel `v1` dipertahankan; versi baru pakai sentinel baru + migrasi |
| `npx` + `curl` harus tetap identik | Satu manifest, dihasilkan dari filesystem |
| Pengguna `coherence` | Perilaku preset tidak boleh berubah |
| Python 3.8 | Jangan pakai sintaks 3.9+ (`dict \|`, `list[str]` di runtime) |

---

## 11. Urutan implementasi yang direkomendasikan

1. **Perbaiki dua bug** (§7) + test regresi untuk keduanya. Tidak ada alasan
   menunda; keduanya menghasilkan "lulus" palsu.
2. **Bekukan kontrak**: kumpulkan exit code, ID aturan, format YAML, dan format
   blok ke `docs/CONTRACT.md` sebagai acuan uji.
3. **Ekstrak core tanpa mengubah perilaku**: pindahkan mesin keluar dari
   `check_schema.py` sambil menjaga selftest tetap 20/20 hijau. Refactor murni,
   nol fitur baru.
4. **Domain database jadi plugin pertama** — bukti bahwa interface cukup.
5. **Domain API** — domain termurah berikutnya (OpenAPI/status/response shape).
6. **Security** — butuh parser dan kebijakan redaksi; jangan pakai regex mentah.
7. **Architecture + Testing** — butuh graf dependensi; paling akhir.
8. **DX**: `ironclad doctor`, `rules list`, `preset list`, `init` yang mendeteksi
   stack — setelah core stabil.
9. **Repo baru `ironclad-next`** dan publikasi: menunggu persetujuan eksplisit.

---

## 12. Kesimpulan

Fondasinya lebih baik daripada rata-rata alat sejenis: nol dependensi, exit code
stabil, jujur soal cakupan, dan punya konsep "instruksi yang ditanam" yang jarang.
Yang tidak ada adalah **struktur untuk tumbuh**.

Tiga bug yang ditemukan bukan cacat desain besar — semuanya kecil dan bisa
diperbaiki hari ini. Tapi ketiganya menunjukkan pola yang sama: **jalur yang tidak
diuji adalah jalur yang rusak**, dan jalur yang paling tidak diuji adalah jalur
yang dipakai pengguna baru.

---

## 13. Status perbaikan (Fase 0.5)

Ketiga bug diperbaiki dan dikunci dengan test regresi di
`tests/test_regressions.py` (19 pemeriksaan, dijalankan di CI).

| Bug | Perbaikan | Bukti |
|---|---|---|
| **A** — payload tidak lengkap | `install.sh` menurunkan daftar berkas dari payload (`_manifest`), bukan menulisnya tangan; `sync-mirror.sh` menerbitkan `MANIFEST` dan membuang berkas usang di mirror | Test `test_curl_only_install_gets_full_payload` memasang dari script sendirian: 14 berkas terpasang, `ironclad update` dan `init coherence` jalan |
| **B** — `--preset` ditelan | wrapper tidak lagi menyisipkan `--preset`; prioritas dipindah ke satu tempat di `load_preset` | `check . --preset strict` → exit 1 (dulu 0); `--preset legacy-friendly` pada repo `strict` → exit 0 |
| **C** — repo `coherence` tak bisa diperiksa | berkas repo selalu dibaca sebagai lapisan; `name: <preset>` diselesaikan ke aturannya, `exceptions` repo dipertahankan | `check .` pada repo coherence → exit 1 dengan DB-08 |

**Prioritas akhir yang berlaku** (didokumentasikan di `load_preset`):

```
builtin:balanced  <  .agent/standards.yml  <  --preset  <  --config
```

**Yang tidak berubah:** `drill.py --selftest` tetap 20/20, 8 ID aturan tetap,
exit code 0/1/2/10 tetap, nama preset tetap, format `standards.yml` tetap, dan
`bin/` tetap tidak dipasang ke direktori skill (perintah ada di
`~/.local/bin/ironclad` dengan `IRONCLAD_HOME` tertanam).

