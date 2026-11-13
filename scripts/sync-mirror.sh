#!/usr/bin/env bash
# Copy the current skill payload to the public mirror that install.sh reads.
# Run after editing SKILL.md, references/, scripts/, templates/ or presets.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-/home/wilsench/htdocs/wilsench.my.id/public/ironclad-next/pkg}"
SKILL="$ROOT/skills/ironclad"
OWNER="wilsench:wilsench"

case "$DEST" in
  */public/ironclad/pkg|*/public/ironclad/*)
    echo "refusing to write into $DEST" >&2
    echo "that path serves the published 0.10.2 docs of the original repository." >&2
    echo "this release lives at /ironclad-next/." >&2
    exit 1 ;;
esac
[ -d "$DEST" ] || { echo "no mirror dir: $DEST" >&2; exit 1; }

# MANIFEST is the payload index. install.sh reads it when the script arrives on
# its own (curl|bash) and there is no payload beside it: the list of files to
# fetch comes from here instead of from a hand-written list inside the script.
# That hand-written list is what dropped update_check.py and coherence.yml from
# the 0.10.2 install, so this file is now generated, never typed.
manifest() {
  ( cd "$SKILL" && find . -type f \
      ! -path './.git/*' ! -path '*/__pycache__/*' ! -name '*.pyc' \
      | sed 's|^\./||' | sort )
}

mkdir -p "$DEST"/{assets/presets,bin,references,scripts,templates,ironclad_core/domains}
cp "$SKILL/SKILL.md"                 "$DEST/"
cp "$SKILL"/references/*.md          "$DEST/references/"
cp "$SKILL"/scripts/*.py             "$DEST/scripts/"
cp "$SKILL"/templates/*.md           "$DEST/templates/"
cp "$SKILL"/assets/presets/*.yml     "$DEST/assets/presets/"
cp "$SKILL"/bin/ironclad             "$DEST/bin/ironclad"
chmod +x "$DEST/bin/ironclad"

# The engine. Missing this whole directory once shipped a mirror whose SKILL.md
# promised four domains and whose payload contained none of them: the installer
# fetched a compatible-looking tree, `ironclad check` failed on import, and
# nothing in the release guard noticed because every version string agreed.
if [ -d "$SKILL/ironclad_core" ]; then
  ( cd "$SKILL/ironclad_core" && find . -type f -name '*.py' ! -path '*/__pycache__/*' ) \
    | while IFS= read -r rel; do
        mkdir -p "$DEST/ironclad_core/$(dirname "${rel#./}")"
        cp "$SKILL/ironclad_core/${rel#./}" "$DEST/ironclad_core/${rel#./}"
      done
else
  echo "no engine at $SKILL/ironclad_core — refusing to publish an empty shell" >&2
  exit 1
fi

# A stale file left on the mirror is worse than a missing one: the installer
# would happily fetch a preset or script that no longer exists in the repo.
# Mirror contents are generated, so anything the payload no longer has goes.
# MANIFEST itself is generated below, not part of the payload — skip it here.
while IFS= read -r old; do
  rel="${old#"$DEST"/}"
  [ "$rel" = "MANIFEST" ] && continue
  if ! manifest | grep -qxF "$rel"; then
    rm -f "$old"
    echo "  removed stale: $rel"
  fi
done < <(find "$DEST" -type f)

manifest > "$DEST/MANIFEST"

# A digest of the payload itself, so a release guard can compare content
# instead of comparing version strings and calling that agreement.
digest() {
  ( cd "$DEST" && find . -type f ! -name MANIFEST ! -name DIGEST \
      ! -path '*/__pycache__/*' ! -name '*.pyc' \
      | sed 's|^\./||' | LC_ALL=C sort \
      | while IFS= read -r f; do sha256sum "$f"; done ) | sha256sum | cut -d' ' -f1
}
digest > "$DEST/DIGEST"
chown -R "$OWNER" "$DEST"

# the installer itself lives beside the docs, not inside pkg/
cp "$ROOT/install.sh" "$(dirname "$DEST")/install.sh"
chown "$OWNER" "$(dirname "$DEST")/install.sh"

echo "mirror synced: $(find "$DEST" -type f | wc -l) files → $DEST"
echo "manifest: $(wc -l < "$DEST/MANIFEST") entries"
