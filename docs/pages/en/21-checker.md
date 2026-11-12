---
title: Checker
slug: checker
group: Reference
order: 21
summary: Full reference for check_schema.py — arguments, exit codes, JSON output, what it scans and what it skips.
---

# Checker

`scripts/check_schema.py` is a single-file Python script with no dependencies
beyond the standard library. It scans `.sql`, `.php` (Laravel migrations), and
`.prisma` files.

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

Precedence, weakest to strongest:

```
builtin:balanced  <  .agent/standards.yml  <  --preset  <  --config
```

`.agent/standards.yml` is **always** read — the repo's `exceptions` and
`boolean_allowlist` still apply when you pass `--preset`. The preset only
overrides per-rule severity. A file that contains nothing but `name: coherence`
(exactly what `ironclad preset` writes) is read as that preset, so both forms
are valid: a name alone, or explicit rules.

Without `--preset`, the checker looks for `.agent/standards.yml` and walks up
from the target directory. The report's last line tells you which one it used —
`preset: balanced (.agent/standards.yml)` or `preset: strict (preset:strict)`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | clean, or only warnings on a preset that does not block them |
| `1` | at least one blocking error |
| `2` | misuse — unknown preset, config not found, no files |

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

`.sql`, `.php`, `.prisma` — recursively, skipping `node_modules`, `vendor`,
`dist`, `build`, `.git`, `storage`, and dot-directories.

## What it does not do

- **Not a SQL parser.** It is regex-based. It can produce false positives and it
  will miss constructs a parser would catch. A human reviewer is still the last
  layer.
- **No autofix.** Changing a schema is a design decision.
- **No cross-file analysis.** It does not know that your lookup table lives in a
  different migration.
- **No security, performance or API rules** — those are separate domains, see
  [extending](/extending/).

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
