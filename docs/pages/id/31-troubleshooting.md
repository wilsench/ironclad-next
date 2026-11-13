---
title: Troubleshooting
slug: troubleshooting
group: Operasional
order: 31
summary: Gejala yang paling sering muncul, penyebabnya, dan perbaikannya. Diurutkan dari yang paling sering.
---

# Troubleshooting

## Skill tidak terdeteksi

**Gejala:** agent tidak pernah menyebut Ironclad, walau sudah dipasang.

Cek satu per satu:

```bash
ls ~/.agents/skills/ironclad/SKILL.md
head -4 ~/.agents/skills/ironclad/SKILL.md
```

Yang benar:

```
---
name: ironclad
description: Use when several developers share one database — make sure everyone stores status the same way before the agent writes schema.
```

| Penyebab | Perbaikan |
|---|---|
| Nama file bukan `SKILL.md` | huruf besar semua |
| Frontmatter tanpa `name`/`description` | agent tidak bisa memilihnya |
| Agent belum restart | daftar skill dibaca saat start |
| Dipasang di folder yang tidak dibaca agent itu | pakai `--target` yang benar |
| Dua skill bernama sama | hapus duplikatnya |

## Mulai dari sini: `ironclad doctor`

Sebelum membaca halaman ini sampai habis, jalankan itu. Ia menjawab empat
pertanyaan yang membuat halaman ini ada: apakah instalasinya lengkap, lapisan
config mana yang dibaca, berkas apa yang terlihat, dan aturan mana yang benar-benar
akan menyala.

```bash
ironclad doctor
```

Exit `3` berarti instalasinya sendiri rusak — jalankan ulang installer. Exit `1`
berarti instalasinya baik dan reponya yang butuh perhatian. Ia tidak pernah menulis
apa pun.

## `unknown preset strict`

**Gejala:** checker jalan, tapi `--preset` apa pun ditolak.

**Penyebab:** `scripts/presets/` tidak ikut tersalin ke repo. Checker mencari preset di dua tempat — `scripts/presets/` (saat disalin ke repo) dan `assets/presets/` (saat jalan dari skill).

```bash
python3 scripts/check_schema.py --list-presets   # kalau kosong, ini penyebabnya
```

**Perbaikan:**

```bash
npx github:wilsench/ironclad#v{{VERSION}} --project . --preset balanced
```

## `no files any rule can read found`

**Gejala:** checker bilang tidak ada berkas, padahal repo penuh migration.

**Penyebab:** path yang diberikan menunjuk folder yang salah, atau folder dilewati otomatis (`node_modules`, `vendor`, `dist`, `build`, `.git`).

```bash
python3 scripts/check_schema.py . --json | head -5     # cek "files"
find . -name "*.sql" -not -path "*/node_modules/*" | head
```

## CI merah di semua PR

**Penyebab:** seluruh repo digate, bukan hanya file yang berubah.

```yaml
# ✗ gate seluruh repo
run: python scripts/check_schema.py .

# ✓ gate hanya yang berubah
CHANGED=$(git diff --name-only --diff-filter=d origin/${{ github.base_ref }}...HEAD \
  | grep -E '\.(sql|php|prisma)$' || true)
[ -z "$CHANGED" ] && exit 0
python scripts/check_schema.py $CHANGED
```

## Aturan menyala pada kode yang saya tahu benar

Dua kemungkinan, dan jawabannya berbeda.

**Kena batas aturannya.** Baca dulu:

```bash
ironclad rules explain ARCH-01
```

Bagian *apa yang menolak ia putuskan* ada persis untuk kasus ini. Kalau kodemu di
luar yang bisa ia lihat, turunkan tanpa mematikannya — di `.agent/standards.yml`:

```yaml
rules:
  ARCH-01: warn        # atau: off
```

**Aturannya yang salah.** Itu bug yang layak dilaporkan, dan laporan yang berguna
memuat berkas, baris, dan kenapa kodenya benar. Beberapa aturan di alat ini
dipersempit atau dibuang justru karena ada yang melaporkan seperti itu.

## False positive pada kolom yang bukan status

**Gejala:** `mimeType`, `prototype`, `fileType` dilaporkan sebagai kolom status.

Checker mencocokkan kata utuh per segmen, jadi kasus umum sudah ditangani. Kalau kamu menemukan yang lolos, dua pilihan:

1. **Tambahkan pengecualian** di `.agent/standards.yml`:

```yaml
exceptions:
  - migrations/2024_add_mime_columns.sql
```

2. **Laporkan polanya** — kalau itu benar false positive, perbaikan regex lebih baik daripada pengecualian per berkas.

## Angka berbeda antar mesin

**Gejala:** di laptopmu 4 error, di CI 9.

**Penyebab paling sering:** berkas config berbeda. Checker menyebutkan sumbernya di baris terakhir:

```
preset: balanced (.agent/standards.yml)
```

Kalau salah satu mesin menulis `preset: builtin:balanced`, berarti `.agent/standards.yml` tidak ada di sana — belum di-commit, atau dijalankan dari folder yang salah.

## `git push` ditolak `fetch first`

Repo dibuat dengan README atau `.gitignore` sehingga tidak kosong.

```bash
git pull --rebase origin main
git push -u origin main
```

## `Permission denied (publickey)` saat push

GitHub tidak menerima password akun untuk git. Pakai PAT sebagai password, atau pasang SSH key:

```bash
ssh-keygen -t ed25519 -C "you@example.com"
cat ~/.ssh/id_ed25519.pub     # tempel di GitHub → Settings → SSH keys
```

## Installer gagal mengambil berkas

**Gejala:** `failed to fetch from GitHub and from the mirror`.

Installer mencoba GitHub lebih dulu, lalu mirror. Kalau keduanya gagal, biasanya jaringan:

```bash
curl -sI https://wilsench.my.id/ironclad/pkg/SKILL.md | head -1
curl -sI https://raw.githubusercontent.com/wilsench/ironclad/main/skills/ironclad/SKILL.md | head -1
```

Salah satu harus `200`. Kalau mirror 200 tapi installer tetap gagal, paksa lewat mirror:

```bash
IRONCLAD_BASE=https://wilsench.my.id/ironclad/pkg \
  bash -c "$(curl -fsSL https://wilsench.my.id/ironclad/install.sh)"
```

## Agent memuat skill tapi tidak mengikutinya

Itu berbeda dari "tidak terdeteksi". Agent membaca instruksi lalu memilih jalan lain.

Yang membantu:
- sebut aturan spesifik: "ikuti DB-04 untuk kolom status"
- minta laporannya mengutip ID aturan
- jalankan checker sebelum commit — model boleh lupa, CI tidak

Yang tidak membantu: menambah teks peringatan di skill. Instruksi bukan penegakan.

## Setelah install, `ironclad version` masih versi lama

`npx` menyimpan cache, dan tanpa tag ia mengikuti `main` apa adanya. Periksa
versinya dulu:

```bash
ironclad version
```

Kalau angkanya bukan versi yang kamu tuju:

```bash
npx --yes github:wilsench/ironclad#v{{VERSION}} --force
```

`--force` membuat installer menimpa payload yang ada. Kalau masih lama, bersihkan
cache npm: `npm cache clean --force`.

Kalau `ironclad` malah tidak ditemukan, berarti `~/.local/bin` belum ada di `PATH` —
installer mencetak baris yang perlu ditambahkan ke `~/.bashrc`.

## Agent-nya tidak bertanya padahal sudah install

Cek dua hal, berurutan:

1. **Apakah bloknya benar-benar ditulis?** Installer mencetak `created`/`updated`
   per agent. Kalau yang tercetak justru "no agent config directory was found",
   berarti folder konfigurasi agent itu belum ada di mesinmu — buka agent-nya sekali,
   lalu jalankan installer lagi.
2. **Apakah agent membaca file itu?** Untuk Antigravity/`agy`, aturan global ada di
   `~/.gemini/AGENTS.md` dan `~/.gemini/GEMINI.md`. Untuk Claude Code di
   `~/.claude/CLAUDE.md`. Kalau file ada tapi agent tetap diam, agent itu tidak
   memuat file tersebut — laporkan, jangan diasumsikan bekerja.

Reparasi tanpa install ulang: `ironclad attach --global`.
