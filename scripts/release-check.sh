#!/usr/bin/env bash
# Release guard. Run before telling anyone a version exists.
#
# Three failures this catches, all of which have actually happened here:
#   1. docs advertised 0.5.0 while the skill was 0.8.2 (hardcoded VERSION)
#   2. the tag v0.8.3 pointed at a commit whose SKILL.md said 0.8.2
#   3. the live mirror served an older payload than the tag
#
# Usage: bash scripts/release-check.sh [vX.Y.Z]
set -uo pipefail
cd "$(dirname "$0")/.."

PAYLOAD="skills/ironclad"
SKILL_VER="$(sed -n 's/^version: *//p' skills/ironclad/SKILL.md | head -1)"
PKG_VER="$(python3 -c 'import json;print(json.load(open("package.json"))["version"])')"
WANT="${1:-v$SKILL_VER}"
fail=0

say() { printf '%-34s %s\n' "$1" "$2"; }

say "skill version" "$SKILL_VER"
say "package.json version" "$PKG_VER"

if [ "$SKILL_VER" != "$PKG_VER" ]; then
  say "MISMATCH" "package.json != SKILL.md"; fail=1
fi

# The tag must exist, point at a commit, and the SKILL.md INSIDE that tag must agree.
if ! git rev-parse -q --verify "refs/tags/$WANT" >/dev/null; then
  say "tag $WANT" "MISSING"; fail=1
else
  TAG_VER="$(git show "$WANT:skills/ironclad/SKILL.md" 2>/dev/null | sed -n 's/^version: *//p' | head -1)"
  say "tag $WANT contains" "$TAG_VER"
  [ "$TAG_VER" = "$SKILL_VER" ] || { say "MISMATCH" "tag content != SKILL.md"; fail=1; }

  # And the tag must be reachable from the branch people install from.
  if git merge-base --is-ancestor "$WANT" origin/main 2>/dev/null; then
    say "reachable from origin/main" "yes"
  else
    say "reachable from origin/main" "NO — tag is on an unmerged commit"; fail=1
  fi
fi

# The live mirror is what curl and the docs actually serve.
#
# Comparing version numbers here is not enough, and this guard proved it: the
# mirror served a 0.10.2 SKILL.md promising four domains while pkg/ contained
# no ironclad_core at all. Every string agreed; the payload was a shell. So the
# mirror is checked three ways: the version, the engine's presence, and a digest
# of the served files against a digest computed from the checkout.
LIVE="$(curl -fsS --max-time 15 https://wilsench.my.id/ironclad/pkg/SKILL.md 2>/dev/null | sed -n 's/^version: *//p' | head -1)"
say "live mirror" "${LIVE:-unreachable}"
[ "$LIVE" = "$SKILL_VER" ] || { say "MISMATCH" "mirror != SKILL.md"; fail=1; }

# The engine must be on the mirror, not only in the repo.
if curl -fsS --max-time 15 https://wilsench.my.id/ironclad/pkg/ironclad_core/engine.py >/dev/null 2>&1; then
  say "engine on mirror" "yes"
else
  say "engine on mirror" "MISSING — mirror has no ironclad_core/"; fail=1
fi

# Content, not version strings: recompute the digest the mirror publishes.
if command -v sha256sum >/dev/null; then
  MIRROR_DIGEST="$(curl -fsS --max-time 15 https://wilsench.my.id/ironclad/pkg/DIGEST 2>/dev/null | tr -d '\n')"
  LOCAL_DIGEST="$( cd "$PAYLOAD" && find . -type f \
      ! -path './.git/*' ! -path '*/__pycache__/*' ! -name '*.pyc' \
      | sed 's|^\./||' | LC_ALL=C sort \
      | while IFS= read -r f; do sha256sum "$f"; done | sha256sum | cut -d' ' -f1 )"
  say "mirror digest" "${MIRROR_DIGEST:-none}"
  if [ -z "$MIRROR_DIGEST" ]; then
    say "MISMATCH" "mirror publishes no DIGEST — cannot verify content"; fail=1
  elif [ "$MIRROR_DIGEST" != "$LOCAL_DIGEST" ]; then
    say "MISMATCH" "mirror payload differs from checkout"; fail=1
  fi
fi

# Every install command in the docs must pin the tag that exists.
DOC_TAGS="$(grep -rhoE 'v[0-9]+\.[0-9]+\.[0-9]+' docs/pages README.md 2>/dev/null | sort -u | tr '\n' ' ')"
say "tags used in docs" "${DOC_TAGS:-none}"
for t in $DOC_TAGS; do
  [ "$t" = "$WANT" ] || { say "MISMATCH" "docs pin $t, want $WANT"; fail=1; }
done

# What the docs promise must exist in the engine. "Five domains" shipped in
# ROADMAP while four were registered; this counts what is actually there.
REGISTERED="$(cd "$PAYLOAD" && python3 -c '
from ironclad_core.domains import load_all
print(len(load_all().rule_ids()))
' 2>/dev/null)"
say "rules registered" "${REGISTERED:-?}"

# The site header number.
SITE="$(curl -fsS --max-time 15 https://wilsench.my.id/ironclad/ 2>/dev/null | grep -oE 'v0\.[0-9]+\.[0-9]+' | sort -u | tr -d 'v' | tr '\n' ' ')"
say "version on site" "${SITE:-unreachable}"
case " $SITE " in *" $SKILL_VER "*) ;; *) say "MISMATCH" "site != SKILL.md"; fail=1 ;; esac

echo
if [ "$fail" -ne 0 ]; then
  echo "NOT READY TO RELEASE."
  exit 1
fi
echo "Release state agrees everywhere. Safe to hand out: npx github:wilsench/ironclad#$WANT"
