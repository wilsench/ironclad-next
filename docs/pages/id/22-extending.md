---
title: Memperluas
slug: extending
group: Referensi
order: 22
summary: Menambah aturan ke domain yang ada, atau membuat domain baru — tanpa merusak aturan yang sudah bekerja.
---

# Memperluas

Set aturan dibagi menjadi **domain**, satu berkas per domain. Tidak ada bagian
mesin yang tahu apa itu kolom status atau siklus impor; domain database adalah
klien pertama dari antarmuka itu, bukan kasus khusus di dalamnya.

```
skills/ironclad/ironclad_core/
├── __init__.py        Finding, Position, RuleMeta — bentuk yang dipakai semua domain
├── engine.py          jalankan aturan, agregasi, hitung cakupan
├── discovery.py       berkas mana yang dibaca, mana yang tak terbaca
├── config.py          lapisan preset, deteksi stack
├── report.py          keluaran manusia dan JSON
├── rules.py           `ironclad rules`
├── doctor.py          `ironclad doctor`
├── cli.py             argparse, stdout, exit code — tidak lebih
└── domains/
    ├── database.py     DB-01 … DB-08
    ├── api.py          API-01, API-02, API-07
    ├── security.py     SEC-01 … SEC-03
    └── architecture.py ARCH-01, ARCH-02
```

## Menambah aturan ke domain yang sudah ada

1. **Pilih ID berikutnya yang kosong.** ID tidak pernah dipakai ulang walau
   aturannya dicabut — berkas config atau baseline CI seseorang masih menyebut
   nomor lama.
2. **Tulis kelasnya** di `domains/<domain>.py`. `Rule` menilai satu berkas;
   `ProjectRule` menilai proyek dan berjalan sekali.
3. **Deklarasikan apa yang dibacanya.** `extensions` adalah klaim aturan, dan
   gabungan semua klaim itulah yang dipindai. Aturan yang tidak mengklaim apa pun
   tidak membaca apa pun.
4. **Buktikan ia menyala.** Fixture yang melanggar, dan — lebih penting —
   fixture yang *terlihat* melanggar tapi benar. Separuh tes domain di repo ini
   adalah kasus negatif, karena aturan yang menyala pada kode yang bekerja lebih
   buruk daripada tidak ada aturan.
5. **Set keparahan di keempat preset.** Aturan tanpa entri jatuh ke default-nya
   sendiri — itu cara sebuah preset `strict` diam-diam berhenti ketat.
6. **Tulis batasnya.** Tambahkan entri ke `LIMITS` di `ironclad_core/rules.py`
   yang menyebut apa yang menolak ia putuskan. `ironclad rules explain` mencetaknya,
   dan menuliskannya adalah yang menjaga aturan tetap jujur.
7. **Jalankan semua gerbang** sebelum commit:

```bash
python3 tests/test_regressions.py
python3 tests/test_api_domain.py        # atau domain yang kamu sentuh
python3 tests/capture_behaviour.py after > /tmp/new.json
python3 tests/capture_behaviour.py diff /tmp/baseline.json /tmp/new.json
```

Yang terakhir yang paling penting: ia membandingkan 108 perilaku tercatat dan
harus melaporkan `0 changed` pada exit code dan temuan.

## Menambah domain baru

Buat `domains/<nama>.py` dengan fungsi `register(reg)`. `load_all()` menemukannya
dengan menelusuri paket, jadi tidak ada daftar yang perlu diperbarui dan tidak ada
apa pun di inti yang perlu diedit.

```python
DOMAIN = "performance"

class Perf01NPlusOne(ProjectRule):
    meta = RuleMeta(id="PERF-01", domain=DOMAIN,
                    title="query di dalam loop",
                    default_severity="warn", scope="project")
    extensions = (".php", ".js", ".ts")

    def applies_to(self, ctx): ...
    def check(self, contexts, cfg): ...

def register(reg):
    reg.add(Perf01NPlusOne())
```

Tiga aturan untuk domain baru:

- **Satu ruang nama ID per domain.** `SEC-01` tidak boleh bertabrakan dengan
  `DB-01`, dan awalannya harus memberi tahu berkas mana yang dibuka.
- **Domain tidak mengimpor domain lain.** Kalau `api` butuh sesuatu dari
  `database`, hal itu milik `core`.
- **Sebut apa yang tidak bisa kamu baca.** Domain yang diam-diam melewati satu
  stack adalah cara seluruh alat ini kehilangan kepercayaan.

## Apa yang membuat aturan layak ditambahkan

Diukur, bukan diasumsikan. Sebelum menulis aturan, jalankan pada repo nyata dan
hitung apa yang akan ia laporkan. Tiga aturan yang diusulkan untuk proyek ini
gugur setelah pengukuran itu:

| Usulan | Terukur | Putusan |
|---|---|---|
| "controller tidak boleh menyentuh model" | 6 dari 7 controller di repo Laravel nyata | ditolak — itu idiom resmi framework |
| "test yang selalu skip" | 0 kemunculan di semua repo di mesin ini | ditolak — aturan yang tak pernah menyala tak diketahui bekerja |
| "test tidak sejajar modul" | 15 berkas test untuk 3 workspace | ditolak — pemetaan 1:1 tak pernah ada |

Sebuah aturan layak kalau ia:

1. **deterministik** — input sama, putusan sama, tanpa model di tengahnya
2. **murah diperiksa** — regex atau penelusuran graf, bukan build
3. **mahal dibalik** — keputusan skema atau arsitektur, bukan preferensi format
4. **diam pada kode yang benar** — satu-satunya uji yang menentukan

Format itu urusan formatter. Gaya itu urusan linter dengan autofix. Ironclad untuk
keputusan yang sampai produksi dan tinggal di sana.

## Yang jangan ditambahkan

- aturan yang butuh database berjalan
- aturan yang bergantung pada keadaan repo lain
- aturan yang butuh menebak niat aplikasi ("apakah status ini bermakna?")
- apa pun yang deskripsinya memuat "kadang-kadang"
- apa pun yang akan menyala pada sebagian besar repo nyata yang bekerja

## Mengubah skill-nya sendiri

`SKILL.md` adalah kontrak yang diikuti agent. Kalau kamu menambah aturan yang
harus diterapkan agent *sebelum* menulis kode, ia harus muncul di dua tempat:

1. `references/<domain>.md` — alasannya
2. bagian **Procedure** di `SKILL.md` — langkah yang dieksekusi agent

Aturan yang hanya didokumentasikan di `references/` akan dibaca hanya kalau agent
merasa perlu. Bagian procedure yang diikuti.
