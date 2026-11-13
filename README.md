# Ironclad

**Make the AI agent understand that the project belongs to the team — not to it.**

A skill for AI coding agents. Two developers, one database: one stores status as
`ENUM('paid')`, the other as `status_code = 2`. Both pass review. Six months later
reports need a branch per table, new code has to guess, and nobody can say which is
current.

Ironclad changes one thing: before an agent writes anything that stores status, it
**asks which way this project does it, and reads the codebase to check** — instead of
quietly adding a second style.

The same question applies past the schema, so the checker now reads four things: how
a project stores status, how its endpoints answer, what leaked into a file git can
carry, and how its modules depend on each other.

**It is not a style guide.** There is no house rule about how to write a query, and
you do not have to adopt one. If you want your team's answer written down and checked
automatically, the repo ships that as optional tooling; if you only wanted the
understanding, the install is enough.

## Install

```bash
npx github:wilsench/ironclad-next#v0.11.0
```

Same installer without Node:

```bash
curl -fsSL https://wilsench.my.id/ironclad/install.sh | bash
```

No questions, no second step. It puts the skill where your agent looks, adds an
`ironclad` command to `~/.local/bin`, and writes the rule block into each agent's
**global** config (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/AGENTS.md`, `~/.gemini/GEMINI.md`,
`~/.cursor/rules/`, `~/.config/opencode/AGENTS.md`, `~/.agents/AGENTS.md`) — only for
agents whose config directory already exists.

That last part is why there is nothing else to do: the agent reads it at the start of
every session, in any repo, and asks **"which way does this project store status —
follow the codebase, or check with the team first?"** before touching schema.

Optional, once per repo, to record your project's decision in git:

```bash
ironclad init           # writes .agent/standards.md — a decision record
ironclad check          # does this repo store status more than one way?
ironclad preset strict  # severity levels, if you use the checker
```

`init` writes `.agent/standards.md` (the decision record) plus, if you use the
checker, `.agent/standards.yml`, `scripts/check_schema.py`, and `scripts/presets/`.
Commit them — otherwise the next teammate reads a different answer.

**Needs Python 3.8+** (preinstalled on macOS, most Linux, Termux) to write the block
and to run the checker. Without `python3` the installer exits 3 and tells you how to
install it, instead of claiming success with nothing written. `--no-agent-files`
installs the skill alone.

**Targets:** `agents` (Codex, Cursor, opencode, Antigravity — default), `claude`, `hermes`, `gemini`, `opencode`, or `--all`. Docs: <https://wilsench.my.id/ironclad/>

Format is [agentskills.io](https://agentskills.io/specification), so the same
folder works in Hermes, Claude Code, Codex, Cursor, opencode, and Antigravity.
Hermes users can also install through the hub:

```bash
hermes skills install wilsench/ironclad-next/skills/ironclad
```

## Optional: the checker

Everything below is for teams that want machine-checked consistency. None of it is
required for the agent to understand the problem, and a repo that skips it is not
"wrong" — it just has no automated record.

`ironclad init` defaults to `balanced`. The choice lands in `.agent/standards.yml`
inside your repo — committed, reviewable, changeable later with `ironclad preset`,
no reinstall.

| Preset | Blocks the build | Only warns | For |
|---|---|---|---|
| `legacy-friendly` | — | everything | a repo that already has debt |
| `coherence` | DB-08 | the rest | anyone who does not want a style imposed |
| `balanced` **(default)** | DB-01, DB-02, DB-04 | the rest | normal product work |
| `strict` | everything | — | finance, health, anything audited |

`init` asks which level once, when a human is at the terminal, and stays silent in CI. Switch whenever:

```bash
python3 scripts/init_standards.py . --preset strict --force
python3 scripts/check_schema.py . --preset legacy-friendly   # one-off, no file change
python3 scripts/check_schema.py --list-presets
```

Or just edit `.agent/standards.yml` — one line per rule, `error` / `warn` / `off`. See [presets.md](skills/ironclad/references/presets.md).

## Staying up to date

No daemon, no telemetry. One check you run yourself:

```bash
ironclad update            # ask once, in plain words
ironclad update --check    # 0 = current, 10 = newer exists
ironclad update --mute     # stop asking on this machine
```

It never blocks, never runs in CI or a pipe, never checks more than once per 24h, and
never changes the exit code of `ironclad check`. See [docs/update](https://wilsench.my.id/ironclad/update/).

## Why three layers

| Layer | File | Enforced by |
|---|---|---|
| Policy — what the team wants | `.agent/standards.md` | Code review |
| Procedure — how the agent decides | `SKILL.md` + `references/` | The agent |
| Mechanism — what a machine checks | `ironclad check` (`scripts/check_schema.py`) | CI / pre-commit |

A skill alone is advice; a model can ignore advice. The checker is what actually holds twenty programmers to one standard. Install both, then wire the checker into CI.

## Rules

Database — how this project stores status:

```
DB-01  no native enum in schema (unless justified in the migration comment)
DB-02  no magic numbers compared against status fields
DB-03  status integer must carry a FK or CHECK
DB-04  never store a human label as the status
DB-05  boolean only for genuine binaries
DB-06  money exact (`numeric` fixed scale or bigint minor units), never float
DB-07  timestamps carry a timezone
DB-08  one project stores status one way (no enum table beside an integer table)
```

API — how the endpoints answer:

```
API-01  endpoint paths named in more than one style        warn
API-02  an error payload returned under a 2xx status       warn
API-07  the same route declared twice                      error
```

Security — what leaked, and what is about to:

```
SEC-01  a .env that git tracks                             error (warn if untracked + not ignored)
SEC-02  a credential written as a literal in source        error on strict
SEC-03  .env.example missing variables the code reads      warn
```

Architecture — the shape of a project, read from its imports:

```
ARCH-01  a cycle in the import graph                       error on strict
ARCH-02  an import pointing at a file that does not exist  warn
```

`ironclad rules` prints this list as the engine actually registers it, with the
effective severity for your preset. `ironclad rules explain SEC-01` also prints
what the rule refuses to decide.

## Verified, not asserted

Same fixture, three presets — this is the actual output:

```
$ ironclad check examples/bad.sql --preset balanced
[DB-01] ERROR SQL/prisma enum column; use integer code + lookup table (see DB-03)
[DB-05] warn  `is_status` is not a binary concept; use a code column
[DB-04] ERROR status stored as text (`stock_state`); use smallint code + lookup table
[DB-03] warn  `status_code` has no FK to a lookup table or CHECK constraint
[DB-08] warn  status is stored 3 different ways in this project: enum, text, integer
→ 1 file(s), 2 error(s), 3 warning(s) — exit 1

$ ironclad check examples/bad.sql --preset legacy-friendly
→ 1 file(s), 0 error(s), 5 warning(s) — exit 0
  (warnings do not fail the build; use --strict to escalate)

$ ironclad check examples/good.sql --preset strict
→ 1 file(s), 0 error(s), 0 warning(s) — exit 0
```

Run them yourself before trusting the block above; it is a fixture in this repo,
not a screenshot.

## Honest limitations

- The checker is **pattern- and import-based**, not a real SQL/Prisma parser and not a type checker. It reads SQL DDL, Laravel migrations, Prisma schema, route declarations, credential assignments, and import statements. It does not see your ORM's query builder, runtime-built SQL, or resolved types.
- **Every finding is a shape, not a runtime fact.** SEC-01 sees that git tracks a `.env`; it cannot know whether those credentials are still live. ARCH-01 sees a cycle; it cannot tell a deliberate one from an accident.
- It will not catch a status field that is *semantically* wrong but syntactically fine. A human reviewer is still the last line.
- Run it report-only first, then gate changed files. Gating an entire legacy repo on day one is how the check gets deleted from CI by lunch.

## Arbitrary codes are fine — undocumented codes are not

`88` for "empty stock", `99` for "departed" — that works, and this skill does not fight it. Integer codes are exactly what the policy asks for. Two things make it safe:

```sql
INSERT INTO stock_state (code, label) VALUES (88, 'empty'), (89, 'low'), (90, 'available');
--                        ^ single source of truth: the DB rejects 87
```

```ts
const STOCK = { EMPTY: 88, LOW: 89, AVAILABLE: 90 } as const;   // no bare 88 in app code
```

The gaps are the point — reserve `8x` for stock states, `9x` for departure states, and the number carries meaning to a human reading a query six months later. What the checker blocks is the *bare literal*: `if (status === 88)` scattered through the codebase. That is the same number with no name, no foreign key, and no reviewer.

## Repo layout

```
skills/ironclad/
├── SKILL.md                  # procedure + pitfalls the agent follows
├── references/
│   ├── database.md           # decision table, worked SQL/TS/PHP
│   ├── presets.md            # strictness levels, custom presets
│   └── extending.md          # adding rules and rule domains
├── templates/standards.md    # policy file for your repo
├── assets/presets/*.yml      # balanced · coherence · legacy-friendly · strict
├── ironclad_core/            # the engine
│   ├── engine.py             # run rules, aggregate, count coverage
│   ├── discovery.py          # which files are read, which are unreadable
│   ├── config.py             # preset layering, stack detection
│   ├── report.py             # human and JSON output
│   ├── rules.py              # `ironclad rules`
│   ├── doctor.py             # `ironclad doctor`
│   └── domains/
│       ├── database.py       # DB-01 … DB-08
│       ├── api.py            # API-01, API-02, API-07
│       ├── security.py       # SEC-01 … SEC-03
│       └── architecture.py   # ARCH-01, ARCH-02
├── bin/ironclad              # the `ironclad` command
└── scripts/
    ├── check_schema.py       # entry point kept for compatibility
    └── init_standards.py     # bootstrap
```

Publishing your own fork: `./scripts/set-repo-owner.sh <username>`, then follow [PUBLISH.md](PUBLISH.md).

## License

MIT

