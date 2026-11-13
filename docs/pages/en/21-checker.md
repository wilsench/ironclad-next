---
title: Checker
slug: checker
group: Reference
order: 21
summary: Full reference for check_schema.py — arguments, exit codes, JSON output, what it scans and what it skips.
---

# Checker

`scripts/check_schema.py` is the entry point over `ironclad_core/`, a small
package with no dependencies beyond the standard library. It reads schema and
source files across four domains — see [Rules](/en/rules/) for the current list.

The entry point stayed a single file on purpose: a repo that copied the checker
in with `--with-checker` can still run `python3 scripts/check_schema.py`, and the
engine travels beside it as `scripts/ironclad_core/`.

## Usage

```bash
ironclad check                      # current repo, uses .agent/standards.yml
ironclad check --json               # machine-readable
ironclad check app/database         # one directory
ironclad check migrations/001.sql   # one file

# equivalent, without the wrapper
python3 scripts/check_schema.py . --preset balanced
```

## Arguments

| Argument | Meaning |
|---|---|
| `paths…` | files or directories; default `.` |
| `--preset NAME` | `balanced`, `coherence`, `strict`, `legacy-friendly` |
| `--config FILE` | explicit config file; outranks `--preset` |
| `--strict` | escalate all warns to errors — **deprecated**, use `--preset strict` |
| `--json` | JSON on stdout instead of the human report |
| `--list-presets` | print the presets it can see, with error/warn counts |

Three more commands read the same config layering as `check`, so what they show is
what a run will do:

```bash
ironclad doctor                 # why is this not doing what I expected?
ironclad rules                  # every rule and its effective severity
ironclad rules explain SEC-01   # what it looks for, and what it refuses to decide
```

Precedence, weakest to strongest:

```
builtin:balanced  <  .agent/standards.yml  <  --preset  <  --config
```

`.agent/standards.yml` is **always** read — the repo's `exceptions` and
`boolean_allowlist` still apply when you pass `--preset`. The preset only
overrides per-rule severity. A file that contains nothing but `name: coherence`
(exactly what `ironclad preset` writes) is read as that preset, so both forms
are valid: a name alone, or explicit rules.

Without `--preset`, the checker looks for `.agent/standards.yml` **inside the
target**. It used to walk up parent directories, which meant checking
`~/projects/app` silently picked up `~/.agent/standards.yml` — a policy for a
different project, or for the machine. A parent policy is now an explicit act:
`--config ../.agent/standards.yml`.

The report's last line tells you which one it used —
`preset: balanced (.agent/standards.yml)` or `preset: strict (preset:strict)`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | clean, or only warnings on a preset that does not block them |
| `1` | at least one blocking error |
| `2` | misuse — unknown preset, config not found, no files to check |
| `3` | the install itself is broken (the engine is missing) |

Exit `2` is distinct on purpose: a typo in your CI configuration must not look
like a schema violation.

## Human output

```
bad.sql:4: [DB-01] ERROR SQL/prisma enum column; use integer code + lookup table (see DB-03)
bad.sql:6: [DB-04] ERROR status stored as text (`stock_state`); use smallint code + lookup table

preset: balanced (.agent/standards.yml)
1 file(s), 2 error(s), 2 warning(s)
```

The last line says **where** the preset came from — that is what you need when
two machines disagree and the cause is a config file that was never committed.

## JSON output

```bash
ironclad check --json
```

```json
{
  "preset": "balanced",
  "source": "preset:balanced",
  "files": 1,
  "findings": [
    {
      "rule": "DB-01",
      "severity": "error",
      "line": 4,
      "msg": "SQL/prisma enum column; use integer code + lookup table (see DB-03)",
      "file": "examples/bad.sql"
    }
  ],
  "errors": 1,
  "warnings": 0
}
```

## What it scans

Whatever the loaded domains declare they can read — currently `.sql`, `.php`,
`.prisma`, plus the source extensions the API, security and architecture domains
need (`.js`, `.ts`, `.tsx`, `.py`, …). Nothing in the core decides this: a domain
declares its own extensions, so adding one is a new file rather than an edit to
the engine.

Skipped everywhere: `node_modules`, `vendor`, `dist`, `build`, `.git`, `storage`,
`coverage`, virtualenvs, and nested dependency trees.

`3` files' worth of schema in a stack the checker cannot parse (Django `models.py`,
Rails migrations) makes the run exit `2` with a warning rather than `0`. A repo
that is merely *harder* to check must not look clean.

## What it does not do

- **Not a SQL parser.** It is regex-based. It can produce false positives and it
  will miss constructs a parser would catch. A human reviewer is still the last
  layer.
- **No autofix.** Changing a schema is a design decision.
- **Limited cross-file analysis.** DB-08 compares how status is stored across the
  whole project, and ARCH-01 builds an import graph — but neither knows that your
  lookup table lives in a different migration and is joined elsewhere.
- **No performance rules**, and no autofix anywhere.

## Testing the fixtures

```
examples/good.sql            balanced 0 error 0 warn   exit 0
                             strict   0 error 0 warn   exit 0
examples/bad.sql             balanced 2 error 2 warn   exit 1
                             legacy   0 error 4 warn   exit 0
examples/bad_migration.php   2 findings
examples/bad.prisma          1 finding
```

These numbers are asserted in this repo's own CI
(`.github/workflows/engineering-standards.yml`), so a broken checker is caught
here before it reaches a user.
