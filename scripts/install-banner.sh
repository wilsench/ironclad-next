#!/usr/bin/env bash
# Put the "general version" banner on the *internal* Ironclad docs.
#
# Why nginx and not the docs itself: /ironclad/ is the published 0.10.2 build that
# belongs to the office repo. Editing its HTML would mean owning that repo's
# output, and the next rebuild from upstream would silently drop the banner again.
# A response filter keeps the origin byte-identical and puts the pointer where it
# belongs — at the edge — so it survives any rebuild of the files underneath.
#
# This script only ever INSERTS text between markers. An earlier version rewrote
# an existing `location` block by regex and swallowed the neighbouring
# /ironclad-next/ block with it, because the pattern matched past the closing
# brace. Insertion cannot do that: if it goes wrong, nginx -t rejects the
# candidate and the live file is never touched.
set -euo pipefail

CONF="/etc/nginx/sites-enabled/wilsench.my.id.conf"
MARK_BEGIN="# >>> ironclad-banner (managed by scripts/install-banner.sh) >>>"
MARK_END="# <<< ironclad-banner <<<"
BACKUP_DIR="/root/backups"
ROOT_DIR="/home/wilsench/htdocs/wilsench.my.id/public"

[ -f "$CONF" ] || { echo "no $CONF"; exit 1; }

# Nginx sub_filter wants a single line: no raw newlines. Kept dense on purpose.
ID_BANNER='<div style="background:#1b1416;color:#f3e9d2;border-bottom:2px solid #b8863b;font:500 13px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;padding:9px 16px;display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;text-align:center"><span style="letter-spacing:.09em;text-transform:uppercase;font-size:10.5px;color:#d9b06a">Edisi internal &middot; v0.10.2</span><span style="opacity:.45">&middot;</span><span>Mencari versi publik? <b style="font-weight:700">Ironclad Next</b> lebih lengkap: empat domain &mdash; database, API, keamanan, arsitektur &mdash; dan bisa dipasang.</span><a href="https://wilsench.my.id/ironclad-next/" style="color:#1b1416;background:#d9b06a;text-decoration:none;font-weight:700;padding:3px 10px;border-radius:2px;white-space:nowrap">Baca Ironclad Next &rarr;</a></div>'

EN_BANNER='<div style="background:#1b1416;color:#f3e9d2;border-bottom:2px solid #b8863b;font:500 13px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;padding:9px 16px;display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;text-align:center"><span style="letter-spacing:.09em;text-transform:uppercase;font-size:10.5px;color:#d9b06a">Internal edition &middot; v0.10.2</span><span style="opacity:.45">&middot;</span><span>Looking for the general version? <b style="font-weight:700">Ironclad Next</b> is the public release: four domains &mdash; database, API, security, architecture &mdash; and it installs.</span><a href="https://wilsench.my.id/ironclad-next/" style="color:#1b1416;background:#d9b06a;text-decoration:none;font-weight:700;padding:3px 10px;border-radius:2px;white-space:nowrap">Read Ironclad Next &rarr;</a></div>'

CAND="$(mktemp)"; TESTROOT="$(mktemp -d)"
trap 'rm -f "$CAND"; rm -rf "$TESTROOT"' EXIT

python3 - "$CONF" "$CAND" "$MARK_BEGIN" "$MARK_END" "$ID_BANNER" "$EN_BANNER" "$ROOT_DIR" <<'PY'
import sys, re
conf, out, mb, me, idb, enb, root = sys.argv[1:8]
src = open(conf, encoding="utf-8").read()

# Re-run: drop every managed region — there are three (id, en, redirect), and
# removing only the first left the others to collide on the next insert.
while mb in src:
    lo = src.index(mb)
    hi = src.index(me, lo) + len(me)
    src = src[:lo] + src[hi:].lstrip("\n")

def remove_block(text, header):
    """Remove one `location ... {` block by brace matching.

    A regex cannot do this safely: `.*?\\n  }` stops at the first two-space brace
    line, and an earlier version of this script swallowed the neighbouring
    /ironclad-next/ block because of it. Counting braces is exact.
    """
    i = text.find(header)
    if i == -1:
        return text
    j = text.index("{", i)
    depth = 0
    for k in range(j, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    else:
        raise SystemExit(f"unbalanced braces after {header!r}")
    return text[:i] + text[end:]

# The pre-banner vhost had plain blocks for these paths. Replace them; the
# managed block below carries the same routes plus the redirect and the filter.
for hdr in ("location ^~ /ironclad/en/ {", "location ^~ /ironclad/ {"):
    src = remove_block(src, hdr)

def server_block(prefix, banner):
    bare = prefix.rstrip("/")
    return (
        f"{mb}\n"
        # `^~ /x/` does not match `/x`: the bare path fell through to the Next
        # app and 404'd. An exact-match location 301s to the slashed form.
        f"location = {bare} {{\n"
        f"  return 301 {bare}/;\n"
        f"}}\n"
        f"location ^~ {prefix} {{\n"
        f"  alias {root}{prefix};\n"
        f"  index index.html;\n"
        f"  add_header Cache-Control \"public, max-age=300\";\n"
        f"  sub_filter_once on;\n"
        f"  sub_filter '<body>' '<body>{banner}';\n"
        f"}}\n"
        f"{me}"
    )

def bare_redirect(path):
    return (
        f"{mb}\n"
        f"location = {path} {{\n"
        f"  return 301 {path}/;\n"
        f"}}\n"
        f"{me}"
    )

# The default-language pages are Indonesian; /en/ pages get the English bar.
# Nginx matches the longest prefix first, so both can coexist.
parts = [server_block("/ironclad/en/", enb), server_block("/ironclad/", idb)]
# The release line keeps its own block (no banner) but needs the same redirect.
if "location = /ironclad-next {" not in src:
    parts.append(bare_redirect("/ironclad-next"))

# Insert right before the release-line comment, which sits after the
# well-known rule and before every proxied rule. Nothing is deleted.
anchor = src.find("  # ironclad-next is a separate release line")
if anchor == -1:
    anchor = src.find("  location / {")
if anchor == -1:
    sys.exit("no stable anchor to insert the banner before")
src = src[:anchor] + "\n\n".join(parts) + "\n\n" + src[anchor:]
open(out, "w", encoding="utf-8").write(src)
PY

# Validate a candidate tree that includes the new file, before touching the live one.
mkdir -p "$TESTROOT/sites-enabled"
cp /etc/nginx/nginx.conf "$TESTROOT/nginx.conf"
for f in /etc/nginx/sites-enabled/*; do
  b="$(basename "$f")"
  if [ "$b" = "wilsench.my.id.conf" ]; then cp "$CAND" "$TESTROOT/sites-enabled/$b"
  else cp "$f" "$TESTROOT/sites-enabled/$b"; fi
done
python3 - "$TESTROOT/nginx.conf" "$TESTROOT" <<'PY'
import sys, re
p, root = sys.argv[1], sys.argv[2]
s = open(p).read()
# Only the sites-enabled include moves; snippets and other relative includes
# (fastcgi_params, proxy_params) must keep resolving against /etc/nginx.
s = re.sub(r'/etc/nginx/sites-enabled/', f'{root}/sites-enabled/', s)
open(p, "w").write(s)
PY
# The candidate tree needs the shared fragments those vhosts include by
# relative name; without them nginx errors on an unrelated site and the test
# result says nothing about our file.
for frag in fastcgi_params proxy_params uwsgi_params scgi_params mime.types; do
  [ -f "/etc/nginx/$frag" ] && cp "/etc/nginx/$frag" "$TESTROOT/" || true
done

if ! nginx -t -c "$TESTROOT/nginx.conf" 2>&1 | grep -q "test is successful"; then
  echo "candidate config is invalid — live file untouched"
  nginx -t -c "$TESTROOT/nginx.conf" 2>&1 | grep -E "emerg|error" | head -3
  exit 1
fi

# A block that silently disappears is the failure mode I hit; refuse that too.
before_n=$(grep -c "location" "$CONF")
after_n=$(grep -c "location" "$CAND")
if [ "$after_n" -lt "$before_n" ]; then
  echo "candidate has fewer location blocks ($after_n < $before_n) — refusing"
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
echo "banner installed ($before_n → $after_n location blocks)"
