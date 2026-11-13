# Fase 6 — Distribusi & publikasi

**Status:** kode selesai dan teruji. **Penerbitan belum dilakukan** — menunggu
persetujuan eksplisit, sesuai aturan repo.

---

## Dua bug yang membuat fase ini ada

Sebelum menulis satu baris untuk fase ini, `bash scripts/release-check.sh`
dijalankan. Hasilnya:

```
Release state agrees everywhere. Safe to hand out: npx github:wilsench/ironclad#v0.10.2
exit 0
```

Itu **salah**. Mirror live menyajikan `SKILL.md` versi lama, dan `pkg/` tidak
memuat `ironclad_core/` sama sekali:

```
$ curl -o /dev/null -w '%{http_code}' https://wilsench.my.id/ironclad/pkg/ironclad_core/engine.py
404
```

Dua bug terpisah, keduanya tidak terlihat dari repo:

| # | Bug | Akibat |
|---|---|---|
| 1 | `sync-mirror.sh` tidak pernah menyalin `ironclad_core/` | mirror membawa SKILL.md yang menjanjikan empat domain, tanpa satu pun aturan di dalamnya |
| 2 | `release-check.sh` membandingkan **string versi** | mirror `0.10.2` + repo `0.10.2` = "agrees everywhere", walau payload-nya tidak bisa jalan |

Bug 1 hanya menimpa jalur `curl\|bash`. Jalur `npx github:` menyalin seluruh
repo, jadi ia tetap bekerja — dan itu sebabnya bug ini tidak pernah terlihat.
Ini persis pola yang sama dengan manifest tulisan tangan di 0.10.2: jalur lokal
selamat, jalur pengguna baru rusak.

**Dibuktikan, bukan disimpulkan.** Instalasi `curl|bash` ke HOME sandbox:

```
sebelum: assets references scripts SKILL.md templates       ← 0 berkas mesin
sesudah: assets ironclad_core references scripts SKILL.md templates
         13 berkas mesin; `ironclad check` jalan; `doctor` melihat 4 domain
```

Bug 2 lebih halus: penjaga rilis yang membandingkan nomor tidak bisa membedakan
"versi sama" dari "isi sama". Ia melaporkan hijau pada payload yang tidak bisa
di-import. Itu kelas *lulus palsu* yang sama dengan Django `exit 0` di Fase 4.

---

## Yang diperbaiki

### `scripts/sync-mirror.sh`

- Menyalin `ironclad_core/**/*.py` (13 berkas) ke mirror.
- **Menolak jalan** kalau `ironclad_core/` tidak ada di payload — lebih baik gagal
  di mesin penerbit daripada mengirim cangkang kosong.
- Menerbitkan `DIGEST`: satu sha256 atas `sha256sum` setiap berkas payload,
  dalam urutan byte (`LC_ALL=C sort`).

### `scripts/release-check.sh`

Tiga pemeriksaan baru, semuanya berbasis isi:

1. `engine on mirror` — `pkg/ironclad_core/engine.py` harus HTTP 200.
2. `mirror digest` — `DIGEST` yang diterbitkan mirror harus sama dengan digest
   yang dihitung ulang dari checkout. Beda satu byte = gagal.
3. `rules registered` — mencetak jumlah aturan yang benar-benar terdaftar
   (`load_all().rule_ids()`), supaya "empat domain" di dokumen punya angka.

Dijalankan pada keadaan hari ini, penjaga yang baru **menolak**:

```
live mirror                        0.10.2
engine on mirror                   MISSING — mirror has no ironclad_core/
mirror digest                      none
MISMATCH                           mirror publishes no DIGEST
rules registered                   16
NOT READY TO RELEASE.
exit 1
```

### `install.sh`

Daftar fallback (cabang ketiga: tidak ada checkout, tidak ada `MANIFEST`)
sekarang memuat seluruh `ironclad_core/`. Daftar itu ditulis tangan, dan itulah
tempat mesin hilang sekali — jadi ia diuji berkas per berkas di
`tests/test_distribution.py`.

### Bug ketiga, ditemukan oleh tes yang baru

`DIGEST` yang diterbitkan tidak cocok dengan yang dihitung ulang — di mesin yang
sama. Sebabnya `sort` mengikuti locale: `LC_ALL` di mesin ini `en_US.UTF-8`,
sehingga urutan berkas berbeda dari urutan byte yang dipakai pembaca lain.
Digest yang bergantung pada locale akan selalu "berbeda" di mesin orang lain.
Diperbaiki dengan `LC_ALL=C` di ketiga tempat (penerbit, penjaga, tes).

---

## Gerbang Fase 6

| Gerbang | Hasil |
|---|---|
| `test_regressions` | 22/22 |
| `test_api_domain` | 31/31 |
| `test_security_domain` | 29/29 |
| `test_architecture_domain` | 23/23 |
| `test_dx_commands` | 43/43 |
| `test_distribution` | **45/45** (baru) |
| `capture_behaviour` 108 kasus | 0 exit code / 0 temuan berubah |
| `drill --selftest` | exit 0 |
| `sync-mirror.sh` ke direktori sandbox | 30 berkas, 13 mesin, DIGEST konsisten |
| `curl\|bash` dari mirror sandbox | mesin terpasang, `check` + `doctor` jalan |
| `npx github:wilsench/ironclad-next#main` | 13 berkas mesin, SKILL.md baru |
| `release-check.sh` pada mirror live | **exit 1** — menolak, dan itu benar |

`test_distribution.py` menegaskan dua hal yang tidak bisa ditegaskan oleh
pembacaan kode: bahwa setiap berkas payload benar-benar sampai ke mirror, dan
bahwa `DIGEST` bisa dihitung ulang dari isi mirror itu sendiri.

---

## Yang belum dilakukan, dan kenapa

**Penerbitan.** Belum ada satu pun dari ini yang menyentuh server:

- `sync-mirror.sh` belum dijalankan ke `/home/wilsench/htdocs/.../ironclad/pkg`
- `rsync` docs ke situs live belum dijalankan
- belum ada tag rilis baru
- versi masih `0.10.2` padahal isinya sudah berbeda jauh dari `0.10.2` yang
  diterbitkan

Urutan yang benar, kalau disetujui:

```bash
# 1. naikkan versi (isi berubah, nomor harus berubah)
#    skills/ironclad/SKILL.md + package.json → 0.11.0

# 2. bangun ulang docs dan sinkronkan mirror
python3 docs/build.py
./scripts/sync-mirror.sh
rsync -a --delete site/ /home/wilsench/htdocs/wilsench.my.id/public/ironclad/ \
  --exclude pkg --exclude install.sh
chown -R wilsench:wilsench /home/wilsench/htdocs/wilsench.my.id/public/ironclad

# 3. tag, lalu buktikan
git tag v0.11.0 && git push origin main --tags
bash scripts/release-check.sh v0.11.0     # harus exit 0 sekarang
```

Langkah 3 hanya sah kalau langkah 2 sudah selesai: penjaga yang baru akan
menolak tag yang tidak cocok dengan mirror, dan itu memang tujuannya.

**Satu keputusan yang bukan wewenang saya:** apakah `0.11.0` atau `1.0.0`.
Argumen untuk `1.0.0`: empat domain, CLI stabil, jaminan kompatibilitas diuji
108 kasus. Argumen untuk `0.11.0`: belum ada pengguna di luar tim, dan
`init`/`doctor` masih bisa berubah bentuk. Saya cenderung `0.11.0` — nomor
mayor yang salah lebih sulit ditarik daripada nomor minor yang salah.
