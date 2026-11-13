---
title: Presets — how hard it bites
slug: presets
group: Concepts
order: 11
summary: Four enforcement levels. This is what turns CI red, and what separates "it warns" from "it refuses".
---

# Presets — how hard the rules bite

A preset does not change what Ironclad **knows**. It changes what **blocks**. A
legacy repo with hundreds of findings would kill the gate on day one if everything
were red — so the level is a setting.

> Confused with **mode**? That is a different question: who decides before code is
> written. See [Modes](/en/modes/).

## The four presets

| Preset | Blocks | Only warns | For |
|---|---|---|---|
| `legacy-friendly` | — | everything | a repo that already has debt |
| `coherence` | DB-08, API-07, SEC-01, SEC-02 | the rest | **anyone** who does not want a style imposed |
| `balanced` | DB-01, DB-02, DB-04, API-07, SEC-02 | DB-03, DB-05…DB-08, API-01, API-02, SEC-01, SEC-03, ARCH-01, ARCH-02 | normal product work; the office default |
| `strict` | everything | — | finance, health, anything audited |

Real numbers from the same fixture (`examples/bad.sql`):

```
balanced           errors=6 warns=11
coherence          errors=5 warns=11
legacy-friendly    errors=0 warns=15
strict             errors=17 warns=0
```

`legacy-friendly` turns the architecture rules off entirely: an older codebase has
cycles it will not fix this quarter, and a first run that opens with forty of them
is a first run nobody repeats.

Note that `coherence` has **fewer** errors than `balanced`, and that is the point.
Under that preset an enum is not punished. Only DB-08 fails — the same concept
stored two different ways in one project.

## Which one to pick

**You disagree that enums are wrong, and your repo is already consistent.**
→ `coherence`. It comes back green. That is correct, not a bug.

**You have a team that already agreed on integer + lookup.**
→ `balanced` (default). Enums and text status block; the rest warns.

**Your repo is old, mixed, and you are just starting.**
→ `legacy-friendly` first. Everything is reported, the build stays green. Tighten
after the baseline is clean.

**It handles money or audits.**
→ `strict`. Float money and naive timestamps block too.

## The automatic default

No question asked. `ironclad init` with no argument uses `balanced`:

```
$ ironclad init
wrote   .agent/standards.yml (preset: balanced)
wrote   .agent/standards.md
wrote   scripts/check_schema.py + scripts/presets/
```

A command that asks will hang in CI and in an agent with no TTY — and a hanging
command is worse than a choice you can change.

## Choosing at install time

```bash
npx github:wilsench/ironclad#v{{VERSION}} --project . --preset strict
```

Or later, from inside the repo:

```bash
ironclad init strict
```

## Changing it after install

Your choice lives in `.agent/standards.yml` **inside the repo**, not inside the
skill, so it is committed and visible in the PR diff.

**1. Rewrite from a preset:**

```bash
ironclad preset strict
```

**2. Edit it directly — reviewable:**

```yaml
name: coherence
rules:
  DB-01: warn       # enum use is reported, not blocked
  DB-02: error
  DB-03: warn
  DB-04: warn       # a coded text column is a style; only mixing is a defect
  DB-05: warn
  DB-06: warn
  DB-07: warn
  DB-08: error      # the only hard failure: two styles for one concept
exceptions: []
```

**3. One-off, without changing the file:**

```bash
python3 scripts/check_schema.py . --preset coherence
```

## An adoption order that does not hurt

| Stage | Preset | What happens |
|---|---|---|
| Week 1 | `legacy-friendly` | everything reported, the build stays green |
| Week 2–3 | `balanced` + gate only on changed files | new findings blocked, old debt left alone |
| Once the baseline is clean | `strict` | everything blocks |

Skipping the first stage is the fastest way to make a team hate this tool.

## Your own preset

Create `presets/team.yml`:

```yaml
name: team
title: Our internal rules
rules:
  DB-01: error
  DB-02: error
  DB-03: error
  DB-04: error
  DB-05: off        # this project really is full of binary flags
  DB-06: error
  DB-07: warn
  DB-08: error
exceptions:
  - migrations/2023_legacy_import.sql
boolean_allowlist:
  - is_active
  - is_deleted
```

```bash
python3 scripts/check_schema.py . --config presets/team.yml
```

> **`off` is not a mute button.** Turning a rule off is a reviewed, recorded
> decision, not a shortcut to a green build. If the reason cannot be written in one
> line of a PR, the rule does not need turning off yet.

## Read priority

```
--config  >  --preset  >  .agent/standards.yml  >  built-in preset
```

The rightmost is the safety net: if every file disappears, the checker still runs
instead of crashing.
