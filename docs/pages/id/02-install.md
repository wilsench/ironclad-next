---
title: Pasang di agent
slug: install
group: Mulai
order: 3
summary: Satu perintah, tanpa pertanyaan. Agent langsung bertanya sendiri — tidak ada langkah kedua.
---

# Pasang di agent kamu

```bash
npx github:wilsench/ironclad-next#v{{VERSION}}
```

Atau, kalau lebih suka tanpa Node:

```bash
curl -fsSL https://wilsench.my.id/ironclad-next/install.sh | bash
```

Keduanya menjalankan installer yang sama. Tidak ada pertanyaan, tidak ada menu, tidak
ada langkah kedua.

## Pilih mode: `ask` atau `house`

Mode menentukan apa yang terjadi kalau repo **belum punya** cara menyimpan status.

```bash
npx github:wilsench/ironclad-next#v{{VERSION}}                          # = --mode ask
npx github:wilsench/ironclad-next#v{{VERSION}} --mode house             # default rumah
```

- **`ask`** (default) — ikuti repo; kalau belum ada, **tanya** mau gaya apa. Tidak
  membawa selera siapa pun, jadi memasangnya tidak berarti menyetujui pilihan database
  orang lain.
- **`house`** — sama, ditambah satu hal: kalau belum ada, langsung `status_code` +
  lookup tanpa bertanya. Ini susunan untuk satu tim yang sudah sepakat.

Mode dibaca kembali dari file saat kamu install ulang, jadi mesin `house` tidak turun
jadi `ask` hanya karena kamu menjalankan installer tanpa flag.

Pakai tag versi (`#v{{VERSION}}`), bukan `main`. Tanpa tag, setiap commit baru langsung
menjadi versi yang dipakai seluruh tim — termasuk commit yang belum diuji. Dengan tag,
yang kamu gulirkan adalah satu keadaan yang sudah diperiksa. Naik versi = ganti tag.

Yang dilakukannya:

1. menaruh skill di `~/.agents/skills/ironclad/` — folder yang dibaca Codex, Cursor, opencode, dan Antigravity
2. menambahkan perintah `ironclad` ke `~/.local/bin/`
3. menulis blok aturan ke konfigurasi global tiap agent yang ada di mesinmu
   (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/AGENTS.md` dan
   `~/.gemini/GEMINI.md` untuk Antigravity/`agy`, `~/.config/opencode/AGENTS.md`, dan seterusnya)

Langkah 3 itulah yang membuat agent bertanya sendiri di repo mana pun, tanpa kamu
menjalankan apa-apa. Agent yang folder konfigurasinya tidak ada tidak disentuh.

Kalau `~/.local/bin` belum ada di `PATH`, installer memberi tahu. Tambahkan satu baris ke `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Setelah itu tidak ada yang wajib dijalankan

Agent sudah bertanya sendiri. Perintah-perintah ini ada kalau kamu **ingin** memeriksa
atau mengunci sesuatu:

```bash
ironclad check          # nilai schema repo ini, tidak menulis apa pun
ironclad init           # opsional: kunci aturan ke git untuk tim + CI
ironclad preset strict  # ganti tingkat penegakan kapan saja
```

`check` bisa dipakai langsung setelah install, tanpa `init` — ia memakai preset bawaan (`balanced`) sampai repo punya `.agent/standards.yml` sendiri.

## Python

Installer butuh **Python 3.8+**, bukan untuk mengunduh tapi untuk menulis blok aturan
ke `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`. Kalau `python3` tidak ada, installer
berhenti dengan exit 3 dan memberi perintah pemasangannya — bukan mencetak
"installed" padahal tidak menulis apa pun.

Sudah terpasang di macOS, hampir semua distro Linux, dan Termux. Kalau belum:
`sudo apt install python3` atau `brew install python3`.

Kalau kamu memang ingin skill-nya saja tanpa menyentuh konfigurasi agent:
`--no-agent-files`.

## Agent lain

Default-nya `~/.agents/skills`. Untuk agent yang punya folder sendiri:

```bash
# Claude Code
npx github:wilsench/ironclad-next#v{{VERSION}} --target claude

# Hermes
npx github:wilsench/ironclad-next#v{{VERSION}} --target hermes

# opencode (native)
npx github:wilsench/ironclad-next#v{{VERSION}} --target opencode

# Antigravity global
npx github:wilsench/ironclad-next#v{{VERSION}} --target gemini

# semua yang terpasang di mesin ini
npx github:wilsench/ironclad-next#v{{VERSION}} --all
```

| Agent | Folder |
|---|---|
| Codex | `.agents/skills/` **di dalam repo** — pakai `--dir .agents/skills` |
| Cursor | `~/.agents/skills/` |
| Claude Code | `~/.claude/skills/` |
| Hermes | `~/.hermes/skills/` |
| opencode | `~/.config/opencode/skills/`, juga membaca `~/.agents/skills/` |
| Antigravity | `~/.gemini/config/skills/` (global), `.agents/skills/` (workspace) |

> **Codex tidak punya folder skill global.** Menurut dokumentasi OpenAI, Codex membaca `$CWD/.agents/skills` dan `$CWD/../.agents/skills`. Kalau kamu pengguna Codex, pasang di dalam repo supaya ikut commit:
>
> ```bash
> npx github:wilsench/ironclad-next#v{{VERSION}} --dir .agents/skills
> ```

## Kalau ingin aturannya ikut repo

Ini yang membuat satu tim memakai aturan yang sama — skill ikut git, bukan cuma ada di laptop satu orang:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} --dir .agents/skills
git add .agents/skills/ironclad && git commit -m "chore: add ironclad skill"
```

## CI: lewati semua pertanyaan

Tidak ada pertanyaan sejak awal, jadi tidak ada yang perlu dilewati. Untuk pipeline yang ingin semuanya sekaligus:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} --target agents --project . --preset legacy-friendly
```

## Mencopot

Ada dua hal yang bisa dicopot, dan keduanya berbeda pemiliknya. Pahami ini dulu supaya tidak menghapus aturan tim hanya karena ingin mencoba ulang.

**1. Skill-nya** — ada di folder agent kamu, bukan di repo. Satu perintah, membersihkan semua agent sekaligus:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} --uninstall
```

Yang dihapus: `~/.agents/skills/ironclad`, `~/.claude/skills/ironclad`, `~/.hermes/skills/ironclad`, `~/.gemini/config/skills/ironclad`, `~/.config/opencode/skills/ironclad`, dan perintah `~/.local/bin/ironclad`. Yang tidak ada akan dilewati, bukan error.

**2. Aturan proyek** — `.agent/standards.{md,yml}`, `scripts/check_schema.py`, `scripts/presets/`. Ini **keputusan repo**, bukan milik installer, jadi secara default ia dibiarkan. Kalau memang mau dibuang dari disk:

```bash
cd repo-kamu
npx github:wilsench/ironclad-next#v{{VERSION}} --uninstall --purge
```

Kalau berkas itu sudah pernah di-commit, purge hanya menghapus dari disk — Git masih melacaknya. Selesaikan dengan commit:

```bash
git rm -r .agent scripts
git commit -m "chore: drop ironclad standards"
```

> **Jangan copot `.agent/` hanya karena ingin upgrade skill.** Aturan tim yang sudah disepakati bukan sampah instalasi. `--uninstall` tanpa `--purge` sengaja mempertahankannya.

### Kalau dulu memasang lewat `hermes skills install`

Itu jalur berbeda dan tidak dikenal oleh `install.sh`. Copot lewat Hermes sendiri:

```bash
hermes skills uninstall ironclad
```

Cek sisa pemasangan di mana saja:

```bash
ls -d ~/.agents/skills/ironclad ~/.claude/skills/ironclad ~/.hermes/skills/ironclad \
      ~/.gemini/config/skills/ironclad ~/.config/opencode/skills/ironclad 2>/dev/null
command -v ironclad
```

Kalau kedua perintah di atas tidak menghasilkan apa pun, sudah bersih.
