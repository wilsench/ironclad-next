---
title: Cara pakai tanpa command
slug: no-commands
group: Mulai
order: 6
summary: Tiga langkah. Setelah itu kamu tidak menjalankan perintah apa pun — agent yang bertanya dan mengerjakannya.
---

# Cara pakai tanpa command

Kalau kamu tidak ingin mengingat perintah, ini jalurnya. Tiga langkah, sekali,
lalu selesai.

## 1. Pasang

```bash
npx github:wilsench/ironclad#v{{VERSION}}
```

## 2. Selesai — benar-benar selesai

Setelah langkah 1, **tidak ada langkah kedua**. Installer sudah menulis aturan ke
konfigurasi global tiap agent yang ada di mesinmu:

```
created  .claude/CLAUDE.md          (Claude Code)
created  .codex/AGENTS.md           (Codex)
created  .gemini/AGENTS.md          (Antigravity / agy)
created  .gemini/GEMINI.md          (Gemini CLI)
```

Itu yang dibaca agent **di awal setiap sesi, di repo mana pun** — tanpa kamu
menjalankan apa pun.

## 3. Opsional: catat keputusan proyek

Kalau kamu ingin jawaban "di proyek ini status disimpan bagaimana" ikut git —
supaya anggota tim baru dan agent baru membaca hal yang sama — jalankan sekali:

```bash
cd repo-kamu
ironclad init
```

Ia menanyakan satu hal:

```
How strict should this repo be?
  1) balanced  (default) — enum and text status block, the rest warn
  2) strict    — everything blocks; use for new or clean repos
  3) legacy-friendly — everything warns; use for an old repo with debt
  4) coherence — no style punished; only mixing enum and integer fails
Choose 1-4 [1]:
```

Lalu menulis:

```
wrote   .agent/standards.md       ← catatan keputusan proyek, bukan buku aturan
wrote   .agent/standards.yml      ← tingkat pemeriksaan, kalau kamu memakai checker
wrote   scripts/check_schema.py   ← opsional: pendeteksi gaya campur, bisa dipakai CI

  created        AGENTS.md                             (Codex, opencode, dll)
  created        CLAUDE.md                             (Claude Code)
  created        GEMINI.md                             (Gemini CLI)
  created        .cursor/rules/ironclad.mdc            (Cursor)
  created        .github/copilot-instructions.md       (GitHub Copilot)
```

Lalu commit:

```bash
git add .agent scripts AGENTS.md CLAUDE.md GEMINI.md .cursor .github
git commit -m "chore: adopt ironclad standards"
```

Yang terakhir itu kuncinya. Agent **membaca berkas-berkas itu sendiri** setiap
kali kamu buka repo — tanpa kamu menyuruh, tanpa slash command, tanpa skill yang
harus diaktifkan.

Tanpa `ironclad init`, agent tetap bertanya dan tetap membaca kodebase. Yang hilang
cuma dua: keputusan proyek tidak tercatat di git, dan CI tidak punya berkas untuk
dijalankan.

## 4. Kerjakan seperti biasa

Buka agent, minta fitur apa pun yang menyentuh database. Yang terjadi:

> **Kamu:** tolong tambahkan kolom status ke tabel orders
>
> **Agent:** Ironclad: di proyek ini status disimpan bagaimana — dan saya ikuti
> kodebase yang ada, atau cek dulu ke tim?

Lalu ia **membaca repo lebih dulu** (`grep -rn status`, migrasi, model). Kalau
proyekmu sudah konsisten, ia ikut diam-diam — tidak ada upacara. Kalau ternyata
ada dua gaya berbeda, ia menyebut keduanya beserta berkasnya dan menanyakan mana
yang jadi standar. Ia tidak memilih sendiri.

Kamu tidak mengetik perintah apa pun.

## Kenapa ini bekerja

Skill hanya dimuat kalau agent menilai ia relevan — dan penilaian itu sering
terlambat: kode sudah ditulis sebelum skill dibaca. Berkas seperti `AGENTS.md`
dan `CLAUDE.md` berbeda: itu dibaca **setiap sesi, di awal**, sebelum agent
menjawab apa pun.

Isi yang ditanamkan ke berkas itu sengaja pendek — pemahaman, bukan buku aturan:

- masalah yang dicegah: dua orang menyimpan hal yang sama dengan dua cara
- satu pertanyaan yang harus diajukan sebelum menulis apa pun soal status
- perintah membaca repo dulu, dan bahwa kodebase menang atas preferensi agent
- larangan menambah gaya kedua selagi keputusan belum ada

Tidak ada daftar "pakai integer", tidak ada aturan penulisan query. Kalau kamu
memang ingin jawabannya dicatat, `ironclad init` menulis `.agent/standards.md`
berisi keputusan proyekmu — bukan aturan dari saya.

## Kalau kamu ingin memilih preset tanpa ditanya

```bash
ironclad init strict
ironclad init legacy-friendly
```

Defaultnya `balanced`, dan agent akan tetap menanyakan preset kalau `.agent/`
belum ada — bukan memilih diam-diam.

## Kalau tidak ingin menyentuh AGENTS.md

```bash
ironclad init --no-agent-files
```

Atau saat install: `npx github:wilsench/ironclad#v{{VERSION}} --no-agent-files`.

Tanpa blok itu, agent hanya tahu aturannya kalau ia memuat skill — jadi kamu
kembali ke dunia yang butuh command. Pilihan ini ada untuk repo yang sudah punya
`AGENTS.md` sendiri dan tidak mau dicampuri.

## Mencopot blok itu saja

```bash
ironclad attach . --remove
```

Yang dihapus hanya blok bertanda `<!-- ironclad:begin v1 -->`. Tulisanmu sendiri
di berkas yang sama tidak disentuh. Sudah diuji: `CLAUDE.md` yang berisi aturan
kantor tetap utuh setelah blok Ironclad dicabut.
