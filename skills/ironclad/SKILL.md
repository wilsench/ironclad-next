---
name: ironclad
description: "Use when several developers share one codebase — make sure the agent follows this project's existing decisions (schema, endpoints, secrets, module boundaries) instead of quietly adding a second style."
version: 0.11.1
author: Chia Wilsen, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [conventions, database, schema, team-consistency, code-review]
    related_skills: [requesting-code-review, codebase-inspection]
---

# Ironclad

**What this is:** a way to make an AI agent understand one thing before it writes
code — that this project's decisions belong to the team, not to the agent.

**What this is not:** a style guide. There is no house rule about how to write a
query, and no requirement that you adopt one. Read this section and you have the
whole idea.

## The failure it exists to prevent

Two developers, one database, both adding a status. One writes:

```sql
status ENUM('new','paid','cancelled')
```

The other writes:

```sql
status_code smallint NOT NULL  -- 1 new, 2 paid, 3 cancelled
```

Both are correct. Both pass review. Together they make the project unmaintainable:
reports need a branch per table, new code has to guess, "how do we add a status?"
has two answers, and nobody can say which one is current. It shows up months later,
when the data is already split.

The problem is not `enum`. The problem is **nobody agreed**, and the agent that
wrote the second one never noticed the first.

## What the agent should do

One question, before writing anything that stores status:

> **Ironclad: which way does this project store status — and should I follow the
> codebase, or check with the team first?**

Then:

1. **Look first.** `grep -rn status` in the repo — migrations, models, the actual
   data layer. The codebase wins over the agent's preference. If it is already
   consistent, follow it silently; no ceremony.
2. **If it is inconsistent, name it once** — both styles, both files — and ask which
   becomes the project standard. Do not choose for the team.
3. **Do not add a second style while a decision is pending.** Ask, then wait.

If the repo has **nothing** to follow yet, the answer depends on one setting — the
mode you installed with:

- **`ask`** (default) — ask which style this project wants, then wait.
- **`house`** — this team already decided: `status_code SMALLINT` + lookup table
  (`code` PK, `label`) + FK, named constants in code. Any integer codes are fine.
  Say "house default: status_code + lookup" in one line and write it; do not ask.

Both modes do the same thing when the repo already has an answer: follow it.

That is the entire behaviour. The agent does not need to know which style is
"better"; it needs to know that it is not the one who decides.

## Why asking beats a rule

A rule in a skill is advice to one model in one session. The next developer uses a
different agent, or the same agent in a new chat, and the rule is gone. Agreement
that lives only in a prompt is not agreement.

So the durable form is: **the repo answers, and the agent asks the repo.**

If your team wants that answer written down and checked automatically, Ironclad
ships optional tooling for it — a policy file, a linter, presets. You do not need
any of it to get the understanding. Skip the rest of this file if that is all you
wanted.

## Optional: write the answer down

If you want the decision to survive a new teammate and a new agent:

```bash
ironclad init                 # writes .agent/standards.md — a human-readable record
git add .agent && git commit  # the answer now travels with the code
```

`.agent/standards.md` is prose, not a rulebook. It answers one question: *how do we
store status here, and why.* Reviewers read it, agents read it, and a disagreement
becomes a diff instead of an argument.

## Optional: let a machine check it

`ironclad check` reads the repo and reports where status is stored more than one
way. It is a **consistency detector**, not a style enforcer.

```bash
ironclad check                # does this repo store status one way?
ironclad check --json         # same, for CI
ironclad verify               # did my agent actually understand? (see below)
```

It reads four things, and `ironclad rules` prints them as the engine actually
registers them:

| Domain | What it looks at | Rules |
|---|---|---|
| database | how status is stored | DB-01 … DB-08 |
| API | how endpoints answer | API-01, API-02, API-07 |
| security | what leaked, and what is about to | SEC-01 … SEC-03 |
| architecture | how modules depend on each other | ARCH-01, ARCH-02 |

They exist so the tool can point at evidence. Nothing in this skill requires your
code to pass them, and a repo that ignores the checker is not "wrong" — it just has
no automated record.

Every rule has a written limit — what it refuses to decide. `ironclad rules explain
SEC-01` prints it. That section is not decoration: SEC-01 can see that git tracks a
`.env`, and cannot know whether those credentials are still live.

## Optional: prove the agent understood

Talking to an agent about rules proves nothing; a model will agree with anything.
This runs the agent in a clean repo and grades the schema it produced against what
the repo already does:

```bash
ironclad drill --prompt       # hands the agent a task with no hints
ironclad drill answer.sql     # scores the result, exit 1 if it drifted
```

`ironclad drill --selftest` checks the grader itself still works.

## When to use this skill

- Two or more people (or agents) write schema in one database
- You are about to add a status/state/type field and are not sure of the convention
- An agent is about to write a migration in a repo it has never seen

**Do not use it** for one-off scripts with no persistence, or to enforce formatting
preferences nobody on the team asked for.

## Pitfalls

1. **Treating the agent's preference as the standard.** It should read the repo, not
   decide. If it proposes `integer + lookup` in a repo that uses `enum`, that is the
   exact failure — even though integer is often the better default.
2. **Letting the question become a gate.** One line, then work. An agent that stops
   to interrogate the user about every field is not helping.
3. **Assuming a skill auto-loads.** Skills are picked by relevance; the standing
   instruction in `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` is what makes the agent ask
   reliably. That block is installed for you.
4. **Mistaking a green check for an agreed standard.** A checker can only see what it
   can parse. A repo with no files any rule can read exits 2 — that is "I could not
   look", not "all clear". `ironclad doctor` says which of the two happened.
5. **Silencing the checker to ship.** If it is wrong, say so and change
   `.agent/standards.yml` in a review. Never `|| true` your way past it.

## Files

- `references/database.md` — the eight database rules, with examples
- `references/presets.md` — severity levels, if you use the checker
- `references/extending.md` — applying the same idea beyond databases, and how a
  rule domain is registered
- `templates/standards.md` — the prose record to copy into a repo
- `assets/presets/*.yml` — `balanced` (default), `coherence`, `strict`,
  `legacy-friendly`
- `ironclad_core/domains/` — one file per domain; `database.py`, `api.py`,
  `security.py`, `architecture.py`
- `scripts/check_schema.py` — entry point kept for compatibility
- `scripts/agent_files.py` — writes/removes the standing instruction block
- `scripts/drill.py` — `--prompt`, `--grade`, `--selftest`
- `bin/ironclad` — the `check` / `init` / `preset` / `drill` / `attach` / `update` command
