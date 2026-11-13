---
title: Modes — ask or house
slug: modes
group: Concepts
order: 9
summary: Who decides the status style when the repo has no answer yet. One flag at install, and it is what separates a neutral tool from a team's tool.
---

# Modes — who decides

This is the question people skip, and the reason two people can install the same
tool and get different results:

> This repo has no table with a status column. You ask the agent to add an
> `invoices` table. **Who decides how its status is stored?**

Three answers are possible, and we only support two:

- the agent guesses → **no**, that is the original problem
- the agent asks → mode **`ask`**
- the agent applies the team decision → mode **`house`**

## The difference is one row

| | `ask` (default) | `house` |
|---|---|---|
| Repo already has a style | follow it | follow it |
| Repo has two styles | stop, name both | stop, name both |
| Repo has nothing yet | **ask first** | **write `status_code` + lookup** |
| Fits | anyone, any repo | one team with a shared decision |

Note the second row: **`house` does not force an old repo to standardise.** If your
repo consistently uses enums, `house` keeps following enums. What gets installed is
not "integer everywhere", it is "if no decision exists yet, here is ours".

## Installing

```bash
# neutral — the agent asks when nothing exists yet
npx github:wilsench/ironclad-next#v{{VERSION}}

# office — the agent applies the agreed style immediately
npx github:wilsench/ironclad-next#v{{VERSION}} --mode house
```

Without the flag you get `ask`. That is deliberate: someone who found this from a
search engine is not thereby agreeing with another company's database choices.

## What `house` writes into the agent block

Only the `house` mode gets this paragraph:

```markdown
- **no status anywhere yet** -> use the house default. Do not ask.
  `status_code SMALLINT NOT NULL` + lookup table (`code` PK, `label`) + FK
  from the column, plus named constants in code. Any integer codes are fine
  (10/20/30, 1/2/3) as long as every code exists in the lookup table and is
  never reused.
  Say "house default: status_code + lookup" in one line, then write it.
```

Three things matter in that wording:

- **"Do not ask"** — the agent does not hang waiting for an answer that will never
  arrive in an automated session.
- **"Any integer codes are fine"** — codes need not step by 10. `88` and `99` are
  valid, as long as they exist in the lookup and are guarded by a foreign key.
- **"Say it in one line"** — you still learn which decision was taken, without a
  dialogue. One line in the agent's reply, not a question.

## Changing the mode later

The mode is stored in a file, not just in your shell environment. So:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} --mode ask     # back to neutral
npx github:wilsench/ironclad-next#v{{VERSION}} --mode house   # back to opinionated
```

The installer reads the stored mode first. A `house` machine that gets reinstalled
without the flag **stays** `house` — it does not silently drop because you forgot
the flag.

## A mode is not a decision

`house` only fills a gap. It does not:

- unify two styles that already exist (that is migration work, not an installer)
- change old tables
- override a `.agent/standards.md` you already wrote — that file always wins,
  because a project decision is more specific than a tool default

If you want to **enforce** uniformity in a repo that is already mixed, that is
[Presets](/en/presets/) and `DB-08`, not the mode.

## If you do not use an AI agent

The mode is irrelevant without agents — there is nobody to inform. What is still
useful: `check` to see whether the repo is mixed, and `init` to record the team
decision. See [Checker](/en/checker/).
