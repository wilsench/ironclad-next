# Architecture Proposal — Ironclad Next

**Status:** usulan, belum diimplementasikan. Fase 0 selesai; ini bahan keputusan
untuk Fase 1.

**Tujuan:** lima domain (database, API, security, architecture, testing) berbagi
satu mesin, tanpa mesin itu tahu apa pun tentang domain.

---

## 1. Prinsip yang mengikat

1. **Nol dependensi wajib.** Parser pihak ketiga boleh dipakai **bila ada**,
   tapi tidak boleh menjadi syarat agar alat ini berjalan. Ini yang membuat
   checker bisa jalan di CI kosong (`check_schema.py:140-143`).
2. **Exit code adalah kontrak.** 0 bersih, 1 temuan, 2 salah pakai, 10 = ada
   pembaruan. Tidak boleh ada yang menggeser ini.
3. **Domain tidak boleh saling mengimpor.** `domains/api` tidak boleh
   `import domains.database`. Kalau butuh, itu tanda konsepnya milik `core`.
4. **Aturan adalah data, bukan blok `if`.** Setiap aturan punya ID, domain,
   severity default, dan fungsi `check()` sendiri.
5. **Core tidak tahu nama aturan.** Tidak boleh ada `if rule.id == "DB-01"` di
   luar domain database.
6. **Kejujuran cakupan dipertahankan.** Kalau domain tidak bisa membaca sesuatu,
   ia melaporkan `skipped` dengan alasan — tidak pernah diam.

---

## 2. Struktur yang diusulkan

```
ironclad/
  core/
    __init__.py
    model.py          Finding, Severity, RuleMeta, ScanResult, Position
    registry.py       pendaftaran domain & aturan, penemuan otomatis
    engine.py         orkestrasi: pilih berkas → jalankan aturan → agregasi
    discovery.py      penemuan berkas, deteksi bahasa, hormati .gitignore
    config.py         preset berlapis + override CLI (memperbaiki BUG-B)
    report/
      text.py         output manusia
      json.py         output mesin (skema stabil, versi)
      sarif.py        (nanti) GitHub code scanning
    parserpool.py     cache parser per berkas; fallback ke teks mentah
  domains/
    database/
      domain.py       registrasi
      rules/db01.py … db08.py
      parsers/        sql.py (sqlglot opsional), laravel.py, prisma.py
      presets/        balanced.yml, strict.yml, legacy-friendly.yml, coherence.yml
    api/              (fase 2)
    security/         (fase 3)
    architecture/     (fase 4)
    testing/          (fase 4)
  cli/
    main.py           dispatcher (menggantikan bin/ironclad)
    commands/         check.py init.py doctor.py rules.py preset.py update.py
  agent/
    blocks/           ask.md, house.md (sumber tunggal blok)
    agent_files.py    penulis blok (dipertahankan)
```

**Catatan penting:** `skills/ironclad/` tetap ada sebagai bentuk distribusi
(skill Agent Skills). Ia menjadi pembungkus tipis yang mengeksekusi `cli/main.py`,
bukan tempat logika. Ini menjaga instalasi `~/.agents/skills/ironclad` tetap sah.

---

## 3. Model hasil (Finding)

```python
@dataclass(frozen=True)
class Position:
    line: int
    column: int | None = None

@dataclass(frozen=True)
class Finding:
    rule_id: str          # "DB-01"
    domain: str           # "database"
    severity: Severity    # error | warn | info | off
    message: str
    file: str
    position: Position
    remediation: str | None = None
    fingerprint: str      # hash stabil: domain+rule+file+normalized span
    evidence: str | None = None   # potongan baris, dipangkas
```

Perubahan dari sekarang:

| Sekarang | Usulan | Alasan |
|---|---|---|
| dict anonim | `Finding` bertipe | reporter & domain baru tidak menebak kunci |
| tanpa `domain` | ada | agregasi & filter per domain |
| tanpa `fingerprint` | ada | baseline/suppression stabil (syarat `legacy-friendly` jujur) |
| tanpa `remediation` | ada | `--explain` dan saran perbaikan |
| `line: int` | `Position` | domain API/security butuh kolom |

**Kompatibilitas output:** reporter `json` mempertahankan kunci lama
(`rule`, `severity`, `line`, `msg`, `file`) **dan** menambahkan yang baru. Kunci
lama tidak dihapus sampai major berikutnya.

---

## 4. Interface aturan

```python
class Rule(Protocol):
    meta: RuleMeta          # id, domain, title, default_severity, docs_url
    def applies(self, ctx: FileContext) -> bool: ...
    def check(self, ctx: FileContext) -> Iterable[Finding]: ...
```

`FileContext` — satu-satunya cara aturan menyentuh berkas:

```python
@dataclass
class FileContext:
    path: Path
    text: str
    language: str                    # "sql" | "php" | "prisma" | ...
    _parsers: ParserPool
    def ast(self, kind: str):        # cached; None bila tak tersedia
    def lines(self) -> list[str]:    # cached
```

Konsekuensi yang disengaja:

- Aturan **tidak** membuka berkas sendiri → mudah diuji dengan teks literal.
- Aturan boleh regex (DB-01 memang regex-able) **atau** AST (architecture butuh
  ini) tanpa mengubah mesin.
- `applies()` memisahkan "berkas ini relevan" dari "berkas ini melanggar",
  sehingga aturan lintas-berkas (DB-08) bisa menjadi aturan
  `scope=project` alih-alih perlakuan khusus di `main()`.

---

## 5. Registry & eksekusi

```python
# domains/database/domain.py
def register(reg: Registry) -> None:
    reg.add_domain("database", title="Database & schema")
    reg.add_rule(Db01Enum())
    ...
```

Penemuan: `core/registry.py` memindai `domains/*/domain.py`, mengimpor, memanggil
`register()`. Tidak ada daftar hardcoded → menambah domain = menambah direktori.

Eksekusi (`core/engine.py`):

1. Muat config (preset + override) → peta `rule_id -> severity`.
2. Temukan berkas (`discovery`).
3. Untuk tiap berkas: buat `FileContext`, tanyakan `applies()` per aturan yang
   domainnya aktif.
4. Jalankan aturan; kumpulkan `Finding`.
5. Agregasi: aturan `scope=project` dievaluasi sekali setelah semua berkas.
6. Reporter memformat.

Yang membuat ini menyelesaikan BUG-B: severity diambil dari **satu** peta hasil
merge, bukan dari argumen CLI. `--preset` mengisi peta, `--config` menimpanya,
dan urutan argumen tidak lagi berarti apa-apa.

---

## 6. Konfigurasi

Format tetap kompatibel dengan yang sekarang:

```yaml
name: balanced            # dipertahankan
rules:
  DB-01: error
domains:                  # BARU, opsional
  database: true
  api: false
  security: warn-only
exceptions: []
boolean_allowlist: [...]
```

Aturan resolusi (menggantikan `bin/ironclad:58`):

```
built-in preset  →  .agent/standards.yml  →  --config  →  --preset  →  --severity ID=sev
        (paling lemah)                                              (paling kuat)
```

Setiap lapisan punya `source` yang dilaporkan, sehingga `--json` bisa menjawab
"kenapa aturan ini warn, bukan error".

---

## 7. Pemisahan mekanisme vs kebijakan

Ini pelajaran dari preset `coherence` (`check_schema.py:501-505`) yang
digeneralisasi:

```python
class RuleMeta:
    id: str
    default_severity: str = "warn"
    advice: str | None = None      # saran netral
    house_advice: str | None = None  # saran yang mengandaikan gaya kantor
```

Pesan memilih `advice` kecuali preset aktif adalah `house`-flavored. Dengan
begitu, aturan API/security baru tidak akan mengulang bug "mengiklankan selera
kepada orang yang tidak memintanya".

---

## 8. Domain pertama: database (bukti interface cukup)

Pemetaan aturan lama → modul baru:

| Sekarang | Baru |
|---|---|
| `ENUM_PATTERNS` (`:67-77`) + DB-01 | `domains/database/rules/db01.py` |
| `MAGIC_*` (`:91-96`) + DB-02 | `db02.py`, dengan `HTTP_RECEIVER` sebagai helper parser |
| blok DB-03 (`:396-422`) | `db03.py`, `scope=project` |
| `VARCHAR_STATUS` (`:98-102`) + DB-04 | `db04.py` |
| `BOOL_NAMES` (`:104`) + DB-05 | `db05.py` |
| `MONEY_*` (`:106-109`) + DB-06 | `db06.py` |
| `TIMESTAMP_*` (`:111-115`) + DB-07 | `db07.py` |
| `status_styles` (`:270-289`) + DB-08 | `db08.py`, `scope=project` |
| `find_unsupported` (`:237-255`) | `domains/database/coverage.py` |

**Kriteria selesai Fase 1:** `drill.py --selftest` tetap **20/20 PASS** tanpa
mengubah satu pun berkas fixture. Itu bukti refactor tidak mengubah perilaku.

---

## 9. Domain berikutnya — apa yang benar-benar dibutuhkan

| Domain | Butuh parser? | Alasan |
|---|---|---|
| **API** | Sebagian | OpenAPI = JSON/YAML (parser ada di stdlib); route & status bisa AST ringan |
| **Security** | Ya | Regex pada secret = false positive tinggi (string contoh, test fixture). Butuh entropi + allowlist + `.env.example` awareness |
| **Architecture** | Ya | Graf impor & siklus butuh AST (Python `ast`, TS via regex terbatas, PHP via tokenizer) |
| **Testing** | Tidak banyak | Struktur folder, keberadaan test, ambang coverage dari file konfigurasi |

Urutan ini sengaja: **API dulu** karena paling murah dan paling jelas
kontraknya. **Security jangan diregex** — itu domain yang paling mudah menjadi
alat yang dimatikan orang.

---

## 10. Yang **tidak** diusulkan

- Menulis ulang installer dalam Node. Shim 70 baris sekarang benar; menggandakan
  logika adalah kelas bug yang alat ini ada untuk mencegah (`cli/index.mjs:5-8`).
- Menambah database aturan berbasis server, telemetri, atau akun. Alat ini harus
  berguna tanpa jaringan.
- Memindahkan semua aturan ke AST. Regex tepat untuk banyak pola schema; memaksa
  AST akan menambah dependensi tanpa manfaat.
- Mengubah nama ID aturan (`DB-01` dst). Itu ada di skrip CI orang.

---

## 11. Risiko arsitektur yang sudah terlihat

| Risiko | Tanda awal | Mitigasi |
|---|---|---|
| Core terlalu pintar | ada `if domain == "database"` di core | review: core tidak menyebut nama domain |
| Parser pool jadi ketergantungan tersembunyi | aturan butuh `ast("sql")` tapi tak ada fallback | setiap parser wajib punya fallback teks + `coverage` warning |
| Blok agent membengkak | blok > 1.500 char | anggaran konteks diuji di CI |
| Lima domain = lima kali false positive | pengguna mematikan alat | default `off` untuk domain baru sampai terbukti; `warn` sebelum `error` |
| Refactor mengubah perilaku diam-diam | selftest tetap hijau tapi fixture berubah | fixture dibekukan; perubahan fixture = commit terpisah dengan alasan |

---

## 12. Pertanyaan yang perlu keputusan Anda sebelum Fase 1

1. **Distribusi**: tetap `skills/ironclad/` sebagai bentul utama (dengan
   `core/`+`domains/` di dalamnya), atau repo Python paket biasa dengan skill
   sebagai artefak turunan?
2. **Bahasa core**: tetap Python (nol dependensi, sudah terbukti) — atau pindah
   ke Node agar satu bahasa dengan `npx`? Rekomendasi saya: **tetap Python**.
3. **Domain default saat instalasi baru**: semuanya `warn` dulu, atau `error`
   hanya untuk database dan sisanya `off`?
4. **Repo `ironclad-next`**: dibuat sekarang sebagai salinan (agar riwayat
   terpisah sejak awal), atau setelah Fase 1 stabil?
