---
title: Troubleshooting
slug: troubleshooting
group: Operations
order: 31
summary: The symptoms that come up most, their causes, and the fix. Ordered by frequency.
---

# Troubleshooting

## The agent does not use the skill

**Most common cause.** The skill is installed, but the agent never activated it —
activation is decided by the `description` in `SKILL.md` matching your task.

Check it is installed where the agent looks:

```bash
ls ~/.agents/skills/ironclad/SKILL.md      # generic / Codex / Cursor
ls ~/.claude/skills/ironclad/SKILL.md      # Claude Code
ls ~/.hermes/skills/ironclad/SKILL.md      # Hermes
```

If it is not there, the installer put it somewhere else — check the `→` lines it
printed, or re-run with an explicit `--dir`.

If it is there and still not used, name it: "use ironclad for this migration".
Codex users: Codex reads `.agents/skills` **inside the repo**, not `$HOME`.

## `ironclad: command not found`

`~/.local/bin` is not on `PATH`:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Or call it directly: `~/.local/bin/ironclad check`.

## `ironclad: skill not found at …`

The launcher points at a directory that no longer exists — usually because
`ironclad` was installed with `--target claude` and then someone removed it, or
`HOME` differs between the install shell and the current one.

Re-run the installer. It rewrites the launcher's `IRONCLAD_HOME` to the directory
it just used.

## Start here: `ironclad doctor`

Before reading the rest of this page, run it. It answers the four questions this
page exists for, in order: is the install complete, which config layers were read,
what files can be seen, and which rules will actually fire.

```bash
ironclad doctor
```

Exit `3` means the install itself is broken — re-run the installer. Exit `1` means
the install is fine and the repo needs attention. It never writes anything.

## `unknown preset` / exit code 2

Exit `2` is misuse, not a violation. Either the preset name is misspelled, or the
config file is missing where the checker expected it.

```bash
python3 scripts/check_schema.py --list-presets   # what it can actually see
```

A copied checker needs its presets beside it. `ironclad init` handles this by
writing `scripts/presets/`. If you copied `check_schema.py` by hand, copy the
presets too.

## `no files any rule can read found` (exit 2)

The path is wrong, or everything under it was skipped. The message names the
extensions the loaded domains were looking for — if that list looks wrong for your
stack, the install is old.

```bash
ironclad check app/database     # point at the schema, not the repo root
ironclad doctor                 # shows what was read and what was skipped
```

The message is followed by a second one when the repo has schema this checker
cannot parse (Django `models.py`, Rails migrations). Exit `2` in that case is not
"clean" — it is "do not treat this as a pass".

## Two machines, different results

Look at the last line of the report:

```
preset: balanced (.agent/standards.yml)    ← read from the repo
preset: balanced (preset:balanced)         ← fell back to the skill default
```

If one machine says `preset:balanced`, `.agent/standards.yml` is not there — not
committed, or the command ran from the wrong directory.

## A rule fires on code I know is correct

Two possibilities, and they need different answers.

**The rule has a limit you hit.** Read it:

```bash
ironclad rules explain ARCH-01
```

The *what it will not decide* section is there for exactly this. If your case is
outside what the rule can see, turn it down without turning it off — in
`.agent/standards.yml`:

```yaml
rules:
  ARCH-01: warn        # or: off
```

**The rule is wrong.** That is a bug worth reporting, and the useful report
includes the file, the line, and why the code is correct. Several rules in this
tool were narrowed or dropped because someone did exactly that.

## A finding appeared that I did not have before

`ironclad presets` shows the error/warn count per preset. If the number changed
between versions, a rule was added — not a rule that started misbehaving. Check
which one with `ironclad rules`, and see *Score got worse after adding a rule*.

## Score got worse after adding a rule

Expected. A new rule finds things the old set did not look for. Roll it out as
`warn` in `legacy-friendly` first, fix the findings, then promote it to `error`.

## `curl … | bash` seems to ignore my input

It does not read stdin — by design, there is nothing to answer. If you passed
flags and they were ignored, they must come after `-s --`:

```bash
npx github:wilsench/ironclad#v{{VERSION}} --target claude
```

Without `-s --`, the arguments go to `bash` itself, which ignores them.

## Behind a proxy, or the mirror is unreachable

```bash
IRONCLAD_BASE=https://raw.githubusercontent.com/wilsench/ironclad/main/skills/ironclad \
  npx github:wilsench/ironclad#v{{VERSION}}
```

`IRONCLAD_BASE` overrides the payload source entirely. Use it for an internal
mirror — the file list is fixed and printed in the installer's `FILES` variable.

## Nothing here matches

Open an issue at <https://github.com/wilsench/ironclad/issues> with:

- the command you ran
- the exact output (exit code included)
- `python3 --version`
- which agent, and where the skill is installed

## `ironclad version` still shows an old version after installing

`npx` caches, and without a ref it follows `main` as-is. Check what you actually have:

```bash
ironclad version
```

If that is not the version you meant to install:

```bash
npx --yes github:wilsench/ironclad#v{{VERSION}} --force
```

`--force` makes the installer overwrite the existing payload. If it is still stale,
clear the npm cache: `npm cache clean --force`.

If `ironclad` is not found at all, `~/.local/bin` is not on your `PATH` — the
installer prints the line to add to `~/.bashrc`.

## The agent does not ask, even though it is installed

Check two things, in order:

1. **Was the block actually written?** The installer prints `created`/`updated` per
   agent. If it printed "no agent config directory was found", that agent's config
   directory does not exist yet — launch the agent once, then re-run the installer.
2. **Does the agent read that file?** For Antigravity/`agy` the global rules live in
   `~/.gemini/AGENTS.md` and `~/.gemini/GEMINI.md`. For Claude Code, `~/.claude/CLAUDE.md`.
   If the file is there and the agent stays silent, that agent is not loading it —
   report it rather than assuming it works.

Repair without reinstalling: `ironclad attach --global`.
