#!/usr/bin/env bash
# Ironclad — one rulebook for every AI coding agent.
#
#   curl -fsSL https://wilsench.my.id/ironclad-next/install.sh | bash
#
# That is the whole install. No questions. It puts the skill where your agent
# looks for it and adds an `ironclad` command to ~/.local/bin.
#
# Then, inside any repo:
#   ironclad check      # instant verdict, nothing written
#   ironclad init       # commit the policy + checker (preset: balanced)
#   ironclad preset strict
#
# Flags, for CI and for people who like flags:
#   --target NAME        agents | claude | hermes | gemini | opencode | all
#   --dir PATH           explicit skills directory (overrides --target)
#   --no-bin             skip the ~/.local/bin/ironclad launcher
#   --no-agent-files     skip writing AGENTS.md / CLAUDE.md / GEMINI.md / .cursor
#                        (the standing instruction that makes the agent ask first)
#   --mode ask|house     ask  = follow the repo, ask when nothing exists yet (default)
#                        house = also apply this team's default when nothing exists
#   --project PATH       bootstrap policy + checker into that repo, then exit
#   --preset NAME        balanced (default) | strict | legacy-friendly
#   --policy-only        with --project: write .agent/ only, skip the checker
#   --repo OWNER/REPO    payload repo (default: wilsench/ironclad-next)
#   --ref REF            git branch or tag (default: main)
#   --uninstall          remove the skill from every agent dir + the launcher
#   --purge              with --uninstall: also delete this project's .agent/ and
#                        scripts/ files (default is to leave them — they are a repo
#                        decision, not an installer artefact)
#   -h, --help
#
# Payload source order: $IRONCLAD_BASE → wilsench.my.id mirror → GitHub.
# The mirror is tried first so the script and the payload always match.
#
# Needs curl + bash. Python is NOT needed to install or to write the policy;
# Python 3.8+ is needed only to RUN the checker.

set -euo pipefail

SKILL_NAME="ironclad"
REPO="${REPO:-wilsench/ironclad-next}"
REF="${REF:-main}"
TARGET="agents"
DEST=""
PROJECT=""
PRESET="balanced"
POLICY_ONLY=""
UNINSTALL=""
PURGE=""
NO_BIN=""
NO_AGENT_FILES=""
MODE=""
ALL=""

while [ $# -gt 0 ]; do
  case "$1" in
    --target)      TARGET="${2:?--target needs a value}"; shift 2 ;;
    --dir)         DEST="${2:?--dir needs a value}"; shift 2 ;;
    --project)     PROJECT="${2:?--project needs a value}"; shift 2 ;;
    --preset)      PRESET="${2:?--preset needs a value}"; shift 2 ;;
    --policy-only) POLICY_ONLY=1; shift ;;
    --repo)        REPO="${2:?--repo needs a value}"; shift 2 ;;
    --ref)         REF="${2:?--ref needs a value}"; shift 2 ;;
    --all)         ALL=1; shift ;;
    --uninstall)   UNINSTALL=1; shift ;;
    --purge)       PURGE=1; shift ;;
    --no-bin)      NO_BIN=1; shift ;;
    --no-agent-files) NO_AGENT_FILES=1; shift ;;
    --mode)        MODE="${2:?--mode needs a value (ask|house)}"; shift 2 ;;
    -y|--yes)      shift ;;
    -h|--help)     sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1 (try --help)" >&2; exit 2 ;;
  esac
done

[ -n "$ALL" ] && { [ "$TARGET" != "agents" ] && { echo "--all conflicts with --target" >&2; exit 2; }; TARGET="all"; }

case "$TARGET" in
  agents|claude|hermes|gemini|opencode|all) ;;
  *) echo "unknown target: $TARGET" >&2; exit 2 ;;
esac
case "$PRESET" in
  balanced|strict|legacy-friendly|coherence) ;;
  *) echo "unknown preset: $PRESET (balanced|strict|legacy-friendly|coherence)" >&2; exit 2 ;;
esac
case "${MODE:-}" in
  ""|ask|house) ;;
  *) echo "unknown mode: $MODE (ask|house)" >&2; exit 2 ;;
esac

# ---- preflight ---------------------------------------------------------------
# The standing instruction and the checker are Python. Without it the installer
# used to print "your agent now asks" after writing nothing — a green light over an
# empty directory. Refuse up front instead, while the fix is still one command.
if [ -z "$NO_AGENT_FILES" ] && [ -z "$UNINSTALL" ]; then
  if ! command -v python3 >/dev/null 2>&1; then
    cat >&2 <<'PY'
ironclad: python3 is required, and it is not on PATH.

  Debian/Ubuntu   sudo apt install python3
  Fedora          sudo dnf install python3
  macOS           brew install python3
  Termux          pkg install python

Without it the installer cannot write the rule block your agent reads at startup,
so it would finish "successfully" while doing nothing. Re-run after installing it,
or pass --no-agent-files to install the skill alone.
PY
    exit 3
  fi
fi

dest_for() {
  case "$1" in
    agents)   echo "$HOME/.agents/skills" ;;
    claude)   echo "$HOME/.claude/skills" ;;
    hermes)   echo "$HOME/.hermes/skills" ;;
    gemini)   echo "$HOME/.gemini/config/skills" ;;
    opencode) echo "$HOME/.config/opencode/skills" ;;
  esac
}

if [ -n "$DEST" ]; then
  DESTS="$DEST"
elif [ "$TARGET" = "all" ]; then
  DESTS=""
  for t in agents claude hermes gemini opencode; do
    parent="$(dirname "$(dest_for "$t")")"
    if [ -d "$parent" ]; then DESTS="$DESTS $(dest_for "$t")"; fi
  done
  [ -z "$DESTS" ] && DESTS="$(dest_for agents)"
else
  DESTS="$(dest_for "$TARGET")"
fi

find_project_root() {
  local d="$PWD"
  while [ "$d" != "/" ]; do
    if [ -d "$d/.agent" ] || [ -d "$d/scripts/presets" ]; then echo "$d"; return 0; fi
    d="$(dirname "$d")"
  done
  return 1
}

# ---- uninstall --------------------------------------------------------------
# Removing only one target leaves working copies behind in the other agents, and
# the skill keeps loading there with no command to manage it. So: sweep every
# known location, plus --dir if given, and say what was actually there.
if [ -n "$UNINSTALL" ]; then
  # Locate the helper before the skill directory is deleted — after that there is
  # nothing left to parse the AGENTS.md block out with.
  SELF_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
  AF=""
  for cand in "$SELF_DIR/skills/ironclad/scripts/agent_files.py" \
              "$SELF_DIR/scripts/agent_files.py" \
              "$HOME/.agents/skills/ironclad/scripts/agent_files.py" \
              "$HOME/.claude/skills/ironclad/scripts/agent_files.py" \
              "$HOME/.hermes/skills/ironclad/scripts/agent_files.py"; do
    if [ -f "$cand" ]; then
      # Copy it out first: the removal loop below deletes the directory it lives in,
      # and the helper is needed AFTER that to strip the AGENTS.md block.
      AF="$(mktemp)"; cp "$cand" "$AF"; break
    fi
  done

  if [ -n "$AF" ] && [ -z "$NO_AGENT_FILES" ]; then
    python3 "$AF" --global --remove
    if [ -d "$PWD/.agent" ] || [ -f "$PWD/AGENTS.md" ] || [ -f "$PWD/CLAUDE.md" ]; then
      python3 "$AF" --project "$PWD" --remove
    fi
    echo
  fi

  SCAN="$DESTS"
  for t in agents claude hermes gemini opencode; do
    SCAN="$SCAN $(dest_for "$t")"
  done
  FOUND=0
  SEEN=""
  for d in $SCAN; do
    case ":$SEEN:" in *":$d:"*) continue ;; esac
    SEEN="$SEEN:$d:"
    [ -d "$d/$SKILL_NAME" ] || continue
    rm -rf "$d/$SKILL_NAME"
    echo "removed $d/$SKILL_NAME"
    FOUND=$((FOUND + 1))
  done
  [ -f "$HOME/.local/bin/$SKILL_NAME" ] && {
    rm -f "$HOME/.local/bin/$SKILL_NAME"
    echo "removed $HOME/.local/bin/$SKILL_NAME"
    FOUND=$((FOUND + 1))
  }
  [ "$FOUND" -eq 0 ] && echo "nothing to remove — not installed in any known location"

  # The instruction block is ours, not the user's, so it always comes out. The
  # project policy is a repo decision and survives unless --purge is given.
  # The policy in a project is a repo decision, not an installer artefact, so it
  # survives by default. --purge is for "I am dropping this entirely".
  if [ -n "$PURGE" ]; then
    ROOT="$(find_project_root)"
    if [ -z "$ROOT" ]; then
      echo "purge: no .agent/ or scripts/presets/ found at or above $PWD — nothing to purge"
    else
      for rel in "$ROOT/.agent/standards.yml" "$ROOT/.agent/standards.md" \
                 "$ROOT/scripts/check_schema.py" "$ROOT/scripts/presets"; do
        if [ -e "$rel" ]; then
          rm -rf "$rel"
          echo "purged  ${rel#$ROOT/}"
        fi
      done
      rmdir "$ROOT/.agent" "$ROOT/scripts" 2>/dev/null || true
      echo "purged project files — if they were committed, finish with: git rm -r .agent scripts"
    fi
  else
    echo
    echo "Project files were left alone: .agent/standards.{md,yml}, scripts/check_schema.py,"
    echo "scripts/presets/. They are a repo decision — delete them in a commit, or rerun with"
    echo "--uninstall --purge to remove them from disk."
  fi
  exit 0
fi

SELF_DIR_TMP="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
SELF_PAYLOAD="$SELF_DIR_TMP/skills/$SKILL_NAME"

# ---- fetch ------------------------------------------------------------------
PRIMARY="https://raw.githubusercontent.com/${REPO}/${REF}/skills/${SKILL_NAME}"
MIRROR="${IRONCLAD_MIRROR:-https://wilsench.my.id/ironclad-next/pkg}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# What the installer must fetch when the payload is not already on disk.
#
# This list used to be maintained by hand, and it drifted: 0.10.2 shipped
# `ironclad update` and the `coherence` preset but never added
# scripts/update_check.py and assets/presets/coherence.yml here. The local
# checkout path still worked (it copies the whole directory), so the bug only
# ever hit the curl|bash path — the one new users take. A hand-written manifest
# of files that also exist on disk is a bug waiting to happen, so it is now
# derived from the payload itself.
_manifest() {
  # 1. A checkout: the payload is on disk. List it, so nothing can be forgotten.
  if [ -d "$SELF_PAYLOAD" ]; then
    ( cd "$SELF_PAYLOAD" && find . -type f \
        ! -path './.git/*' ! -path '*/__pycache__/*' ! -name '*.pyc' \
        | sed 's|^\./||' | sort | tr '\n' ' ' )
    return 0
  fi
  # 2. curl|bash: the script arrived alone. The mirror publishes an index of the
  #    payload it is serving, so the list comes from the publisher, not from this
  #    script's memory of it.
  local idx
  if idx="$(curl -fsSL --max-time 20 "$MIRROR/MANIFEST" 2>/dev/null)" && [ -n "$idx" ]; then
    printf '%s ' $idx
    return 0
  fi
  # 3. No index either (old mirror). The floor: everything a usable install needs.
  printf '%s ' \
    SKILL.md templates/standards.md \
    references/database.md references/presets.md references/extending.md \
    assets/presets/balanced.yml assets/presets/strict.yml \
    assets/presets/legacy-friendly.yml assets/presets/coherence.yml \
    scripts/check_schema.py scripts/init_standards.py scripts/drill.py \
    scripts/agent_files.py scripts/update_check.py bin/ironclad \
    ironclad_core/__init__.py ironclad_core/engine.py ironclad_core/discovery.py \
    ironclad_core/config.py ironclad_core/report.py ironclad_core/rules.py \
    ironclad_core/doctor.py ironclad_core/cli.py ironclad_core/domains/__init__.py \
    ironclad_core/domains/database.py ironclad_core/domains/api.py \
    ironclad_core/domains/security.py ironclad_core/domains/architecture.py
}

FILES="$(_manifest)"

fetch_from() {
  base="$1"; label="$2"
  for f in $FILES; do mkdir -p "$TMP/$(dirname "$f")"; done
  curl -fsSL --retry 1 --max-time 20 "$base/SKILL.md" -o "$TMP/SKILL.md" 2>/dev/null || return 1
  for f in $FILES; do
    [ "$f" = "SKILL.md" ] && continue
    curl -fsSL --retry 2 --max-time 30 "$base/$f" -o "$TMP/$f" 2>/dev/null || {
      echo "  incomplete payload from $label (missing $f)" >&2; return 1; }
  done
  SOURCE="$label"
  return 0
}

# When the script is run from a checkout (`git clone ... && bash ironclad/install.sh`),
# the payload is sitting next to it. Using the mirror in that case would install a
# different version than the script the user just read — so local wins.
copy_from_local() {
  local here="$1"
  [ -f "$here/skills/ironclad/SKILL.md" ] || return 1
  for f in $FILES; do
    [ -f "$here/skills/ironclad/$f" ] || { echo "  checkout is missing skills/ironclad/$f" >&2; return 1; }
  done
  cp -R "$here/skills/ironclad/." "$TMP/"
  SOURCE="local checkout"
  return 0
}

SOURCE=""
SELF_DIR_TMP="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
if copy_from_local "$SELF_DIR_TMP"; then
  :
elif [ -n "${IRONCLAD_BASE:-}" ]; then
  fetch_from "$IRONCLAD_BASE" "IRONCLAD_BASE" || { echo "failed: $IRONCLAD_BASE" >&2; exit 1; }
elif fetch_from "$MIRROR" "wilsench.my.id"; then
  :
elif fetch_from "$PRIMARY" "${REPO}@${REF}"; then
  :
else
  echo "failed to fetch from the mirror and from GitHub. Check network, then retry." >&2
  exit 1
fi

if ! head -5 "$TMP/SKILL.md" | grep -q "^name: ${SKILL_NAME}$"; then
  echo "downloaded SKILL.md does not look like ${SKILL_NAME} — aborting" >&2
  exit 1
fi

# ---- install ----------------------------------------------------------------
PRIMARY_DIR=""
for d in $DESTS; do
  [ -d "$d/$SKILL_NAME" ] && echo "updating $d/$SKILL_NAME"
  mkdir -p "$d/$SKILL_NAME"
  rm -rf "$d/$SKILL_NAME"
  mkdir -p "$d/$SKILL_NAME"
  cp -R "$TMP/." "$d/$SKILL_NAME/"
  rm -rf "$d/$SKILL_NAME/bin"
  # Bytecode is machine-specific and belongs to whoever ran the script, not to
  # the payload. A checkout's __pycache__ used to ride along into every install.
  rm -rf "$d/$SKILL_NAME/scripts/__pycache__"
  chmod +x "$d/$SKILL_NAME/scripts/"*.py 2>/dev/null || true
  [ -z "$PRIMARY_DIR" ] && PRIMARY_DIR="$d/$SKILL_NAME"
  echo "  → $d/$SKILL_NAME"
done

# ---- the `ironclad` command -------------------------------------------------
if [ -z "$NO_BIN" ]; then
  BIN_DIR="$HOME/.local/bin"
  mkdir -p "$BIN_DIR"
  sed "s|^IRONCLAD_HOME=.*|IRONCLAD_HOME=\"$PRIMARY_DIR\"|" "$TMP/bin/ironclad" > "$BIN_DIR/$SKILL_NAME"
  chmod +x "$BIN_DIR/$SKILL_NAME"
  # remember where it went, so a second install can replace the entry point
  echo "  → $BIN_DIR/$SKILL_NAME"
  case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "  note: $BIN_DIR is not on PATH — add it to use the bare command" ;;
  esac
fi

# ---- --project: bootstrap and exit -----------------------------------------
if [ -n "$PROJECT" ]; then
  [ -d "$PROJECT" ] || { echo "project not found: $PROJECT" >&2; exit 1; }
  AGENT_DIR="$PROJECT/.agent"
  mkdir -p "$AGENT_DIR"

  if [ -f "$AGENT_DIR/standards.yml" ] && [ "$PRESET" = "balanced" ]; then
    echo "kept    .agent/standards.yml"
  else
    cp "$TMP/assets/presets/$PRESET.yml" "$AGENT_DIR/standards.yml"
    echo "wrote   .agent/standards.yml (preset: $PRESET)"
  fi
  if [ -f "$AGENT_DIR/standards.md" ]; then
    echo "kept    .agent/standards.md"
  else
    cp "$TMP/templates/standards.md" "$AGENT_DIR/standards.md"
    echo "wrote   .agent/standards.md"
  fi
  if [ -z "$POLICY_ONLY" ]; then
    mkdir -p "$PROJECT/scripts/presets"
    cp "$TMP/scripts/check_schema.py" "$PROJECT/scripts/check_schema.py"
    cp "$TMP/assets/presets/"*.yml "$PROJECT/scripts/presets/"
    chmod +x "$PROJECT/scripts/check_schema.py"
    echo "wrote   scripts/check_schema.py + scripts/presets/"
  fi
  # The standing instruction, so the agent asks before writing schema instead of
  # waiting to be told. This is what removes the need to remember a command.
  if [ -z "$NO_AGENT_FILES" ]; then
    echo
    python3 "$TMP/scripts/agent_files.py" --project "$PROJECT"
  fi
  echo
  echo "Commit these, or the next teammate gets a different rulebook:"
  echo "  git add .agent scripts AGENTS.md && git commit -m 'chore: adopt ironclad standards'"
  exit 0
fi

# ---- standing instruction, global -------------------------------------------
# This is what removes the need to run anything in a repo: the rule block goes into
# each agent's own config dir, which the agent reads at startup wherever you open it.
# Only agents whose config dir already exists are touched.
AGENTS_WRITTEN=0
if [ -z "$NO_AGENT_FILES" ]; then
  echo
  AF_ARGS=(--global)
[ -n "${MODE:-}" ] && AF_ARGS+=(--mode "$MODE")
AF_OUT="$(python3 "$TMP/scripts/agent_files.py" "${AF_ARGS[@]}" 2>&1)" || {
    echo "$AF_OUT"
    echo "  could not write the standing instruction — the agent will not ask on its own" >&2
    ATTACH_FAILED=1
  }
  echo "$AF_OUT" | grep -v '^IRONCLAD_AGENTS_WRITTEN='
  AGENTS_WRITTEN="$(echo "$AF_OUT" | sed -n 's/^IRONCLAD_AGENTS_WRITTEN=//p')"
  AGENTS_WRITTEN="${AGENTS_WRITTEN:-0}"
fi

# ---- done -------------------------------------------------------------------
echo
echo "Installed ($SOURCE). Nothing else to configure."

# One line about the update check, so the hint that appears weeks later is not a
# surprise. No prompt here: this script runs in pipes and CI, where a question hangs.
echo
echo "From time to time, \`ironclad check\` will mention a newer version."
echo "It only asks when you run \`ironclad update\`, and \`ironclad update --mute\` stops it."
echo
if [ -n "${ATTACH_FAILED:-}" ]; then
  echo "WARNING: the skill is installed, but no agent config was written. Until you"
  echo "fix that, the agent will NOT ask on its own. Run: ironclad attach --global"
elif [ "${AGENTS_WRITTEN:-0}" = "0" ]; then
  # Nothing was written because no known agent config dir exists. Saying "your agent
  # now asks" here would be a lie, and the user would not know why it never fires.
  echo "The skill is installed, but no agent config directory was found, so nothing"
  echo "was added to any agent. Ironclad recognises:"
  echo "  ~/.claude  ~/.codex  ~/.gemini  ~/.cursor  ~/.config/opencode  ~/.agents"
  echo
  echo "If your agent is not in that list, run it once so it creates its config dir,"
  echo "then re-run the installer. Or tell the agent to read SKILL.md directly:"
  echo "  https://wilsench.my.id/ironclad-next/no-commands/"
elif [ -z "$NO_AGENT_FILES" ]; then
  echo "Your agent now asks before writing schema, in every repo, with no command"
  echo "from you. If it does not, the agent is not reading its config file — see"
  echo "https://wilsench.my.id/ironclad-next/no-commands/"
else
  echo "Skill only — you passed --no-agent-files, so no agent config was touched."
  echo "The agent will not ask on its own until you run: ironclad attach --global"
fi
echo
echo "Optional: run this once per repo to pin the rules in git, so every teammate"
echo "and CI share the same answer (the agent works either way):"
echo "  ironclad init"
