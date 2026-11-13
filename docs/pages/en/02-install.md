---
title: Install
slug: install
group: Start
order: 3
summary: One command, no questions. The agent starts asking on its own — no second step.
---

# Install into your agent

```bash
npx github:wilsench/ironclad-next#v{{VERSION}}
```

Or, if you would rather not use Node:

```bash
curl -fsSL https://wilsench.my.id/ironclad-next/install.sh | bash
```

Both run the same installer. No questions, no menu, no second step.

## Pick a mode: `ask` or `house`

The mode decides what happens when a repo has **no** status storage yet.

```bash
npx github:wilsench/ironclad-next#v{{VERSION}}                          # = --mode ask
npx github:wilsench/ironclad-next#v{{VERSION}} --mode house             # house default
```

- **`ask`** (default) — follow the repo; if nothing exists, **ask** which style. It
  carries nobody's taste, so installing it does not mean agreeing with someone else's
  database choices.
- **`house`** — the same, plus one thing: if nothing exists, write `status_code` +
  lookup without asking. This is the setup for one team that already agreed.

The mode is read back from the file on re-install, so a `house` machine does not
silently drop to `ask` just because you ran the installer without flags.

Use a version tag (`#v{{VERSION}}`), not `main`. Without a tag, every commit you push becomes
the version your whole team runs — including commits that have not been tested. With a
tag, you hand out one state you have actually checked. To move forward, change the tag.

What it does:

1. puts the skill in `~/.agents/skills/ironclad/` — the directory Codex, Cursor,
   opencode and Antigravity read
2. adds an `ironclad` command to `~/.local/bin/`
3. writes the rule block into each agent's **global** config on this machine
   (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/AGENTS.md` and
   `~/.gemini/GEMINI.md` for Antigravity, `~/.config/opencode/AGENTS.md`, and so on)

Step 3 is what makes the agent ask in any repo without anything from you. Agents
whose config directory does not exist are left alone.

If `~/.local/bin` is not on your `PATH`, the installer tells you. Add one line to
`~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## After that, nothing is required

The agent already asks. These exist for when you **want** to check or pin something:

```bash
ironclad check          # score this repo's schema, writes nothing
ironclad init           # optional: pin the rules in git for teammates and CI
ironclad preset strict  # switch strictness whenever, no reinstall
```

`check` works immediately after install, without `init` — it falls back to the
preset shipped in the skill (`balanced`) until your repo has its own
`.agent/standards.yml`.

## Python

The installer needs **Python 3.8+**, not to download anything but to write the rule
block into `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`. Without `python3` it stops with
exit 3 and prints the install command for your platform, rather than reporting
success over an empty config.

It ships with macOS, nearly every Linux distribution, and Termux. If yours does not
have it: `sudo apt install python3` or `brew install python3`.

If you deliberately want the skill without touching any agent config, pass
`--no-agent-files`.

## Other agents

The default is `~/.agents/skills`. For agents with their own directory:

```bash
# Claude Code
npx github:wilsench/ironclad-next#v{{VERSION}} --target claude

# Hermes
npx github:wilsench/ironclad-next#v{{VERSION}} --target hermes

# opencode (native)
npx github:wilsench/ironclad-next#v{{VERSION}} --target opencode

# Antigravity, global
npx github:wilsench/ironclad-next#v{{VERSION}} --target gemini

# everything installed on this machine
npx github:wilsench/ironclad-next#v{{VERSION}} --all
```

| Agent | Directory |
|---|---|
| Codex | `.agents/skills/` **inside the repo** — use `--dir .agents/skills` |
| Cursor | `~/.agents/skills/` |
| Claude Code | `~/.claude/skills/` |
| Hermes | `~/.hermes/skills/` |
| opencode | `~/.config/opencode/skills/`, also reads `~/.agents/skills/` |
| Antigravity | `~/.gemini/config/skills/` (global), `.agents/skills/` (workspace) |

> **Codex has no global skill directory.** Per OpenAI's docs, Codex reads
> `$CWD/.agents/skills` and `$CWD/../.agents/skills`. If you use Codex, install
> inside the repo so it travels with the code:
>
> ```bash
> npx github:wilsench/ironclad-next#v{{VERSION}} --dir .agents/skills
> ```

## If you want the rules to travel with the repo

This is what makes a whole team use the same rulebook — the skill is in git, not
only on one person's laptop:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} --dir .agents/skills
git add .agents/skills/ironclad && git commit -m "chore: add ironclad skill"
```

## CI: nothing to skip

There are no prompts in the first place, so there is nothing to suppress. For a
pipeline that wants everything at once:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} --target agents --project . --preset legacy-friendly
```

## Uninstall

Two different things can be removed, and they have different owners. Understand
this first, so you do not delete a team's rules just because you wanted to retry an
install.

**1. The skill** — lives in your agent folders, not in the repo. One command,
sweeps every agent:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} --uninstall
```

Removes `~/.agents/skills/ironclad`, `~/.claude/skills/ironclad`,
`~/.hermes/skills/ironclad`, `~/.gemini/config/skills/ironclad`,
`~/.config/opencode/skills/ironclad`, and the `~/.local/bin/ironclad` command.
Locations that were never installed are skipped, not an error.

**2. The project policy** — `.agent/standards.{md,yml}`,
`scripts/check_schema.py`, `scripts/presets/`. This is a **repo decision**, not an
installer artefact, so it is left alone by default. To remove it from disk too:

```bash
cd your-repo
npx github:wilsench/ironclad-next#v{{VERSION}} --uninstall --purge
```

If those files were committed, purge only clears the disk — Git still tracks them:

```bash
git rm -r .agent scripts
git commit -m "chore: drop ironclad standards"
```

> **Do not remove `.agent/` just to upgrade the skill.** An agreed team policy is
> not install debris. `--uninstall` without `--purge` keeps it on purpose.

### If you installed via `hermes skills install`

That is a separate path, unknown to `install.sh`. Remove it with Hermes:

```bash
hermes skills uninstall ironclad
```

Check for leftovers anywhere:

```bash
ls -d ~/.agents/skills/ironclad ~/.claude/skills/ironclad ~/.hermes/skills/ironclad \
      ~/.gemini/config/skills/ironclad ~/.config/opencode/skills/ironclad 2>/dev/null
command -v ironclad
```

If both commands print nothing, it is gone.
