#!/usr/bin/env bash
# Put the "general version" banner on the *internal* Ironclad docs.
#
# Why nginx and not the docs itself: /ironclad/ is the published 0.10.2 build that
# belongs to the office repo. Editing its HTML would mean owning that repo's
# output, and the next rebuild from upstream would silently drop the banner again.
# A response filter keeps the origin byte-identical and puts the pointer where it
# belongs — at the edge — so it survives any rebuild of the files underneath.
#
# Safety order matters: build the candidate, test the candidate, and only then
# replace the live file. An earlier version copied first and tested second, which
# left nginx pointed at a config it refused to parse.
set -euo pipefail

CONF="/etc/nginx/sites-enabled/wilsench.my.id.conf"
MARK_BEGIN="# >>> ironclad-banner (managed by scripts/install-banner.sh) >>>"
MARK_END="# <<< ironclad-banner <<<"
BACKUP_DIR="/root/backups"

[ -f "$CONF" ] || { echo "no $CONF"; exit 1; }

# Nginx sub_filter wants a single line: no raw newlines, and every quote escaped.
# Writing HTML inline in nginx config is brittle enough that the banner is kept as
# one dense line with no double quotes at all — single quotes are valid HTML here
# and keep the config parser out of it.
ID_BANNER='<div style="background:#1b1416;color:#f3e9d2;border-bottom:2px solid #b8863b;font:500 13px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;padding:9px 16px;display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;text-align:center"><span style="letter-spacing:.09em;text-transform:uppercase;font-size:10.5px;color:#d9b06a">Edisi internal &middot; v0.10.2</span><span style="opacity:.45">&middot;</span><span>Mencari versi publik? <b style="font-weight:700">Ironclad Next</b> lebih lengkap: empat domain &mdash; database, API, keamanan, arsitektur &mdash; dan bisa dipasang.</span><a href="https://wilsench.my.id/ironclad-next/" style="color:#1b1416;background:#d9b06a;text-decoration:none;font-weight:700;padding:3px 10px;border-radius:2px;white-space:nowrap">Baca Ironclad Next &rarr;</a></div>'

EN_BANNER='<div style="background:#1b1416;color:#f3e9d2;border-bottom:2px solid #b8863b;font:500 13px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;padding:9px 16px;display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;text-align:center"><span style="letter-spacing:.09em;text-transform:uppercase;font-size:10.5px;color:#d9b06a">Internal edition &middot; v0.10.2</span><span style="opacity:.45">&middot;</span><span>Looking for the general version? <b style="font-weight:700">Ironclad Next</b> is the public release: four domains &mdash; database, API, security, architecture &mdash; and it installs.</span><a href="https://wilsench.my.id/ironclad-next/" style="color:#1b1416;background:#d9b06a;text-decoration:none;font-weight:700;padding:3px 10px;border-radius:2px;white-space:nowrap">Read Ironclad Next &rarr;</a></div>'

CAND="$(mktemp)"; trap 'rm -f "$CAND"' EXIT
python3 - "$CONF" "$CAND" "$MARK_BEGIN" "$MARK_END" "$ID_BANNER" "$EN_BANNER" <<'PY'
import sys, re
conf, out, mb, me, idb, enb = sys.argv[1:7]
src = open(conf, encoding="utf-8").read()

if mb in src:                        # re-run: drop the previous managed block
    lo = src.index(mb)
    hi = src.index(me) + len(me)
    src = src[:lo].rstrip("\n") + "\n" + src[hi:].lstrip("\n")

def block(prefix, banner):
    return (
        f"{mb}\n"
        f"location ^~ {prefix} {{\n"
        f"  alias /home/wilsench/htdocs/wilsench.my.id/public{prefix};\n"
        f"  index index.html;\n"
        f"  add_header Cache-Control \"public, max-age=300\";\n"
        f"  sub_filter_once on;\n"
        f"  sub_filter '<body>' '<body>{banner}';\n"
        f"}}\n"
        f"{me}"
    )

# Nginx picks the longest matching prefix, so /ironclad/en/ can carry the English
# bar while /ironclad/ carries the Indonesian one.
new = block("/ironclad/en/", enb) + "\n\n" + block("/ironclad/", idb)

m = re.search(r"location \^~ /ironclad/ \{.*?\n  }\n", src, re.S)
if not m:
    sys.exit("could not find the existing 'location ^~ /ironclad/' block")
src = src[:m.start()] + new + "\n" + src[m.end():]
open(out, "w", encoding="utf-8").write(src)
PY

# Test *before* touching the live file, against a tree that includes the candidate.
TESTROOT="$(mktemp -d)"; trap 'rm -rf "$TESTROOT" "$CAND"' EXIT
mkdir -p "$TESTROOT/sites-enabled"
cp /etc/nginx/nginx.conf "$TESTROOT/nginx.conf"
for f in /etc/nginx/sites-enabled/*; do
  b="$(basename "$f")"
  if [ "$b" = "wilsench.my.id.conf" ]; then cp "$CAND" "$TESTROOT/sites-enabled/$b"; else cp "$f" "$TESTROOT/sites-enabled/$b"; fi
done
# Point the candidate tree's includes at its own sites-enabled.
python3 - "$TESTROOT/nginx.conf" "$TESTROOT" <<'PY'
import sys, re
p, root = sys.argv[1], sys.argv[2]
s = open(p).read()
s = re.sub(r'/etc/nginx/sites-enabled/\*', f'{root}/sites-enabled/*', s)
s = re.sub(r'sites-enabled/(\*|[a-z0-9._-]+\.conf)', f'{root}/sites-enabled/\\1', s)
open(p, "w").write(s)
PY

if ! nginx -t -c "$TESTROOT/nginx.conf" 2>&1 | grep -q "test is successful"; then
  echo "candidate config is invalid — live file untouched"
  nginx -t -c "$TESTROOT/nginx.conf" 2>&1 | grep -E "emerg|error" | head -3
  exit 1
fi

mkdir -p "$BACKUP_DIR"
cp "$CONF" "$BACKUP_DIR/wilsench.my.id.conf.pre-banner-$(date +%Y%m%d-%H%M%S)"
cp "$CAND" "$CONF"
if ! nginx -t 2>/dev/null; then
  echo "live config rejected — restoring backup"
  cp "$(ls -t $BACKUP_DIR/wilsench.my.id.conf.pre-banner-* | head -1)" "$CONF"
  exit 1
fi
systemctl reload nginx
echo "banner installed"
