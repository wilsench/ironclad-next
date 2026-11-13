---
title: Quickstart
slug: quickstart
group: Start
order: 5
summary: Two minutes from nothing to a green checker in one repo, without disturbing anyone else's work.
---

# Quickstart

Two minutes. No questions to answer, no files to hand-edit.

## 1. Install

```bash
npx github:wilsench/ironclad#v{{VERSION}}
```

Done. The skill is in `~/.agents/skills/ironclad/`, the `ironclad` command is in
`~/.local/bin/`.

## 2. Look first, change nothing

```bash
cd your-repo
ironclad check
```

This only reads. Output looks like this:

```
bad.sql:4: [DB-01] ERROR SQL/prisma enum column; use integer code + lookup table (see DB-03)
bad.sql:6: [DB-04] ERROR status stored as text (`stock_state`); use smallint code + lookup table

preset: balanced (preset:balanced)
1 file(s), 2 error(s), 2 warning(s)
```

If your repo is large, do not panic at the count. That is what step 4 is for.

## 3. Make it permanent

```bash
ironclad init
```

It writes four things, all meant to be committed:

```
wrote   .agent/standards.yml (preset: balanced)
wrote   .agent/standards.md
wrote   scripts/check_schema.py + scripts/presets/
```

```bash
git add .agent scripts
git commit -m "chore: adopt ironclad standards"
```

From that commit on, the agent reads `.agent/standards.md` before writing DDL,
and CI reads `.agent/standards.yml` to decide what blocks. One source, two
readers.

## 4. Pick a strictness that will not make the team disable CI

This is the step most people skip, and the main reason tools like this get ripped
out within a week.

| Your repo | Start with | Why |
|---|---|---|
| new, or already clean | `strict` | everything blocks, no debt |
| live product, normal debt | `balanced` (default) | enum & text-status block, the rest warns |
| repo already consistent on enums, do not want to change | `coherence` | no style punished; only mixing fails |
| old repo, hundreds of findings | `legacy-friendly` | everything warns, build stays green |

```bash
ironclad preset coherence         # consistent repo: green, no style imposed
ironclad preset legacy-friendly   # old repo: install, then clean up slowly
ironclad preset balanced          # once the baseline is clean
ironclad preset strict            # once nothing is left warning
```

Step up when the finding count drops, not when a date arrives.

## 5. Prove the gate actually works

```bash
ironclad drill --selftest
```

One command, nine assertions, using fixtures whose answers are already known:

```
  PASS  enum blocked in the default preset
  PASS  integer + lookup + fk accepted
  PASS  text label blocked in the default preset
  PASS  money as float blocks under strict
  PASS  naive timestamp blocks under strict
  PASS  mixed project flagged (DB-08) — the two-developer case
  PASS  consistent project stays silent (no false alarm)
  PASS  grader accepts table-level FOREIGN KEY syntax
  PASS  grader still rejects an enum answer
```

If anything says `FAIL`, stop. The gate is broken and every green check after it
means nothing.

Note lines four and five: under `balanced`, float money and naive timestamps only
**warn** — they do not block. That is deliberate, but it means `balanced` is not a
catch-all. Move to `strict` if you need everything to block.

## 6. Prove the agent actually understands

This is a different question from step 5. A working gate does not guarantee the
agent read the policy — and an agent that is right today can be wrong tomorrow.

```bash
ironclad drill --prompt
```

That prints a task to paste into your agent, and it deliberately mentions **no**
integer, no enum, no rule. If the agent really understood the policy it will land
on the same answer without being fed it.

Then grade what it wrote:

```bash
ironclad drill answer.sql
```

```
  PASS  policy check                           clean
  PASS  no enum column                         none
  PASS  lookup table for status                order_status
  PASS  status column has a foreign key        status_code → order_status
  PASS  statuses seeded as data (not schema)   1 INSERT statement(s)
  PASS  money is integer minor units           ok
  PASS  timestamps carry a timezone            ok
  PASS  cites a rule ID                        DB-01, DB-03, DB-08
8/8 criteria
```

The grader calls no model. A tool that grades a model by asking another model is
only grading itself. Every criterion above is read off the SQL text: is there an
`enum`, is there a lookup table, does the status column carry `REFERENCES`, are the
statuses seeded as data.

**If it scores below 8/8**, fix it in this order:

1. Make sure the agent actually loaded the skill — ask it to quote `.agent/standards.md`.
2. Ask it to name the rule IDs it followed. An agent that cannot name the rule was guessing.
3. Put the checker in CI. The skill is advice; the gate is the only thing that
   cannot be argued with at 2am.

Then open a PR that adds one `enum` column — it must go red on GitHub. If it does
not go red, your CI is wrong, not the checker.

## 7. Knowing when a new version exists

```bash
ironclad update
```

If you are current, it says so and stops. If there is something newer, it shows what
changed in plain words and offers four choices:

```
installed: 0.9.4
latest:    0.9.5
A newer version is available.

What changed since 0.9.4:
  1 change: 1 docs

  • three layers had the wrong first layer

What do you want to do?
  1) Install 0.9.5 now  (recommended)
  2) Stay on 0.9.4 for now  (nothing changes)
  3) Show me what changed
  4) Stop asking on this machine
Choose 1-4 [2]:
```

- **1** installs through the same command as the first time. The agent block is
  replaced in place; a `standards.md` you have already filled in is left alone.
- **2** changes nothing. The choice is remembered, so it does not ask again that day.
- **3** prints the list again and returns to the menu.
- **4** turns the check off for good on that machine.

The check never blocks: at most once per 24 hours, never in a pipe or in CI, and it
never changes the exit code of `ironclad check`. For the status without a prompt:

```bash
ironclad update --check    # 0 = current, 10 = newer exists
ironclad update --notes    # just the list of changes
```

## That is it

What remains is habit: `ironclad check` before you commit, and let CI run the same
thing on every PR.

If something does not work as described here, see
[Troubleshooting](/troubleshooting/) — organised by symptom, not by theory.
