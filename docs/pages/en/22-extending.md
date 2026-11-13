---
title: Extending
slug: extending
group: Reference
order: 22
summary: Adding a rule to an existing domain, or a whole new domain — without breaking the rules that already work.
---

# Extending

The rule set is split into **domains**, one file each. Nothing in the engine knows
what a status column or an import cycle is; the database domain is the first client
of the interface, not a special case inside it.

```
skills/ironclad/ironclad_core/
├── __init__.py        Finding, Position, RuleMeta — the shape every domain shares
├── engine.py          run rules, aggregate, count coverage
├── discovery.py       which files to read, and which are unreadable
├── config.py          preset layering, stack detection
├── report.py          human and JSON output
├── rules.py           `ironclad rules`
├── doctor.py          `ironclad doctor`
├── cli.py             argparse, stdout, exit codes — nothing else
└── domains/
    ├── database.py     DB-01 … DB-08
    ├── api.py          API-01, API-02, API-07
    ├── security.py     SEC-01 … SEC-03
    └── architecture.py ARCH-01, ARCH-02
```

## Adding a rule to an existing domain

1. **Pick the next free ID.** IDs are never reused, even after a rule is retired —
   someone's config file or CI baseline still names the old one.
2. **Write the rule class** in `domains/<domain>.py`. A `Rule` judges one file; a
   `ProjectRule` judges the project and runs once.
3. **Declare what it reads.** `extensions` is what the rule claims, and the union
   of every declared extension is what gets scanned. A rule that claims nothing
   reads nothing.
4. **Prove it fires.** A fixture that violates it, and — more important — a
   fixture that *looks* like a violation but is correct. Half of this repo's
   domain tests are negative, because a rule that fires on working code is worse
   than no rule.
5. **Set the severity in all four presets.** A rule with no entry falls back to its
   own default, which is how a `strict` preset silently stopped being strict.
6. **Write the limit.** Add an entry to `LIMITS` in `ironclad_core/rules.py`
   saying what the rule refuses to decide. `ironclad rules explain` prints it, and
   writing it down is what keeps the rule honest.
7. **Run every gate** before committing:

```bash
python3 tests/test_regressions.py
python3 tests/test_api_domain.py        # or whichever domain you touched
python3 tests/capture_behaviour.py after > /tmp/new.json
python3 tests/capture_behaviour.py diff /tmp/baseline.json /tmp/new.json
```

The last one is the important one: it compares 108 recorded behaviours and must
report `0 changed` on exit codes and findings.

## Adding a whole new domain

Create `domains/<name>.py` with a `register(reg)` function. `load_all()` finds it
by walking the package, so there is no list to update and nothing in the core to
edit.

```python
DOMAIN = "performance"

class Perf01NPlusOne(ProjectRule):
    meta = RuleMeta(id="PERF-01", domain=DOMAIN,
                    title="a query inside a loop",
                    default_severity="warn", scope="project")
    extensions = (".php", ".js", ".ts")

    def applies_to(self, ctx): ...
    def check(self, contexts, cfg): ...

def register(reg):
    reg.add(Perf01NPlusOne())
```

Three rules for a new domain:

- **One ID namespace per domain.** `SEC-01` must never collide with `DB-01`, and
  the prefix must tell you which file to open.
- **No domain imports another.** If `api` needs something from `database`, that
  thing belongs in `core`.
- **Say what you cannot read.** A domain that silently skips a stack is how the
  whole tool becomes untrustworthy.

## What makes a rule worth adding

Measured, not assumed. Before writing a rule, run it against real repositories and
count what it would report. Three rules proposed for this project were dropped
after that measurement:

| Proposed | Measured | Verdict |
|---|---|---|
| "controller must not touch a model" | 6 of 7 controllers in a real Laravel repo | rejected — it is the framework's documented idiom |
| "skipped test" | 0 occurrences across every repo on this machine | rejected — a rule that never fired is a rule nobody knows works |
| "test does not mirror its module" | 15 test files across 3 workspaces | rejected — the 1:1 mapping never existed |

A rule earns its place when it is:

1. **deterministic** — same input, same verdict, no model in the loop
2. **cheap to check** — a regex or a graph walk, not a build
3. **expensive to reverse** — a schema or architecture decision, not a formatting
   preference
4. **quiet on correct code** — the only test that matters

Formatting belongs in a formatter. Style belongs in a linter with autofix.
Ironclad is for decisions that reach production and stay there.

## What not to add

- rules that need a running database
- rules that depend on another repository's state
- rules that require reading application intent ("is this status meaningful?")
- anything with "sometimes" in the description
- anything that would fire on most of a real, working repository

## Changing the skill itself

`SKILL.md` is the contract an agent follows. If you add a rule the agent should
apply *before* writing code, it must appear in both:

1. `references/<domain>.md` — the reasoning
2. the **Procedure** section of `SKILL.md` — the step the agent executes

A rule documented only in `references/` will be read only if the agent feels like
it. The procedure section is what gets followed.
