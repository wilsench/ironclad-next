---
title: Using it without commands
slug: no-commands
group: Start
order: 6
summary: Three steps. After that you run nothing — the agent asks and does the checking.
---

# Using it without commands

If you do not want to remember commands, this is the path. Three steps, once, and
you are done.

## 1. Install

```bash
npx github:wilsench/ironclad-next#v{{VERSION}}
```

## 2. Done — actually done

After step 1 there is **no second step**. The installer already wrote the rules into
each agent's global config on this machine:

```
created  .claude/CLAUDE.md          (Claude Code)
created  .codex/AGENTS.md           (Codex)
created  .gemini/AGENTS.md          (Antigravity / agy)
created  .gemini/GEMINI.md          (Gemini CLI)
```

That is what the agent reads **at the start of every session, in any repo** — with
nothing for you to run.

## 3. Optional: record the project's decision

If you want the answer to "how does this project store status" committed — so a new
teammate and a new agent read the same thing — run this once:

```bash
cd your-repo
ironclad init
```

It asks one question:

```
How strict should this repo be?
  1) balanced  (default) — enum and text status block, the rest warn
  2) strict    — everything blocks; use for new or clean repos
  3) legacy-friendly — everything warns; use for an old repo with debt
  4) coherence — no style punished; only mixing enum and integer fails
Choose 1-4 [1]:
```

Then writes:

```
wrote   .agent/standards.yml      ← this repo's rules (reviewable in a PR)
wrote   .agent/standards.md       ← the explanation, for humans and agents
wrote   scripts/check_schema.py   ← the checker CI can run

  created        AGENTS.md                             (Codex, opencode, etc.)
  created        CLAUDE.md                             (Claude Code)
  created        GEMINI.md                             (Gemini CLI)
  created        .cursor/rules/ironclad.mdc            (Cursor)
  created        .github/copilot-instructions.md       (GitHub Copilot)
```

Then commit:

```bash
git add .agent scripts AGENTS.md CLAUDE.md GEMINI.md .cursor .github
git commit -m "chore: adopt ironclad standards"
```

That last part is the trick. The agent **reads those files by itself** every time
you open the repo — no instruction from you, no slash command, no skill to
activate.

Without `ironclad init` the agent still asks and still uses the `balanced` default
from the skill. You only lose two things: the rules are not in git, and CI has no
file to run.

## 4. Work as usual

Open your agent, ask for any feature that touches the database. What happens:

> **You:** add a status column to the orders table
>
> **Agent:** Ironclad: how does this project store status — and should I follow the
> existing codebase, or check with the team first?

Then it **reads the repo first** (`grep -rn status`, migrations, models). If your
project is already consistent it follows it silently — no ceremony. If it finds two
different styles it names both, with the files, and asks which one becomes the
standard. It does not pick for you.

You type no commands.

## Why this works

A skill is only loaded when the agent judges it relevant — and that judgement
often comes too late: the code is written before the skill is read. Files like
`AGENTS.md` and `CLAUDE.md` are different: they are read **every session, up
front**, before the agent answers anything.

What goes into those files is deliberately short — understanding, not a rulebook:

- the failure being prevented: two people storing the same thing two ways
- the one question to ask before writing anything about status
- read the repo first, and the codebase wins over the agent's preference
- do not add a second style while the decision is pending

No "use integers" list, no query-writing rules. If you do want the answer recorded,
`ironclad init` writes `.agent/standards.md` containing *your project's* decision —
not mine.

## Choosing a preset without being asked

```bash
ironclad init strict
ironclad init legacy-friendly
```

The default is `balanced`. Without `ironclad init`, the agent simply reads the
codebase — it does not stop to interrogate you about presets.

## If you do not want AGENTS.md touched

```bash
ironclad init --no-agent-files
```

Or at install time: `npx github:wilsench/ironclad-next#v{{VERSION}} --no-agent-files`.

Without that block the agent only knows the rules if it loads the skill — so you
are back to a world that needs commands. The option exists for repos that already
maintain their own `AGENTS.md` and do not want it edited.

## Removing just that block

```bash
ironclad attach . --remove
```

Only the block marked `<!-- ironclad:begin v1 -->` is removed. Your own text in
the same file is untouched. Tested: a `CLAUDE.md` holding office rules survives
intact after the Ironclad block is pulled out.
