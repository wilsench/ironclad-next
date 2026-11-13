#!/usr/bin/env bash
# Ganti placeholder <owner> / wilsench dengan username GitHub kamu.
#
#   ./scripts/set-repo-owner.sh yourname
#   ./scripts/set-repo-owner.sh yourname --dry-run
#
# Menyentuh: README.md, index.html, PUBLISH.md, install.sh

set -euo pipefail

OWNER="${1:-}"
DRY=""
[ "${2:-}" = "--dry-run" ] && DRY=1

if [ -z "$OWNER" ]; then
  echo "usage: $0 <github-username> [--dry-run]" >&2
  exit 2
fi
if ! printf '%s' "$OWNER" | grep -Eq '^[A-Za-z0-9]([A-Za-z0-9-]{0,38})$'; then
  echo "not a valid GitHub username: $OWNER" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FILES="README.md index.html PUBLISH.md install.sh"
COUNT=0

for f in $FILES; do
  [ -f "$f" ] || continue
  hits=$(grep -c '<owner>\|wilsench/ironclad-next' "$f" || true)
  [ "$hits" = "0" ] && continue
  if [ -n "$DRY" ]; then
    echo "$f: $hits hit(s)"
    grep -n '<owner>\|wilsench/ironclad-next' "$f" | sed 's/^/    /'
  else
    sed -i \
      -e "s|<owner>/ironclad|${OWNER}/ironclad|g" \
      -e "s|wilsench/ironclad|${OWNER}/ironclad|g" \
      "$f"
    echo "$f: $hits replaced"
  fi
  COUNT=$((COUNT + hits))
done

if [ -n "$DRY" ]; then
  echo "dry run — $COUNT hit(s), nothing written"
else
  echo "done — $COUNT replacement(s) with owner '$OWNER'"
  echo "next: git diff && git commit -am \"docs: point install URLs at $OWNER\""
fi
