---
title: Rules
slug: rules
group: Reference
order: 20
summary: Sixteen rules across four domains, each with the wrong example the checker actually tests — and a note on what each one refuses to decide.
---

# Rules

Each rule has an ID. Use the ID in reviews, in commit messages, in CI output.
"Use DB-03 here" is a shorter conversation than a paragraph about foreign keys.
The prefix says which files the rule opens: `DB-` database schema, `API-` route
declarations, `SEC-` credentials and `.env` files, `ARCH-` the import graph.

## Summary

The **Status** column below is behaviour under the `balanced` preset (the
default). Under `strict` all sixteen become `error`. Under `legacy-friendly`
everything is `warn` and nothing blocks a build — except ARCH-01 and ARCH-02,
which are turned `off` entirely: import cycles in a legacy project usually
predate your arrival, and blocking every one on day one is how a rule gets
deleted from CI. Run `ironclad rules --preset <name>` for what applies to your
preset, rather than what is written here.

| ID | Rule | Status |
|---|---|---|
| DB-01 | No `enum` columns for status | error |
| DB-02 | No magic numbers compared against status | error |
| DB-03 | Status needs a lookup table + FK | warn |
| DB-04 | No human labels stored as status text | error |
| DB-05 | No boolean for a non-binary concept | warn |
| DB-06 | No money as `float`/`double` | warn |
| DB-07 | No `timestamp` without a timezone | warn |
| DB-08 | One status style per project — no mixing enum and integer | warn |

### API — how the endpoints answer

| ID | Rule | Status |
|---|---|---|
| API-01 | Endpoint paths named in more than one style | warn |
| API-02 | An error payload returned under a 2xx status | warn |
| API-07 | The same route declared twice | error |

### Security — what leaked, and what is about to

| ID | Rule | Status |
|---|---|---|
| SEC-01 | A credential in a file git could ship | warn (error when tracked) |
| SEC-02 | A credential hardcoded in source | error |
| SEC-03 | `.env.example` and `.env` disagree | warn |

### Architecture — the shape of the project

| ID | Rule | Status |
|---|---|---|
| ARCH-01 | Files import each other in a cycle | warn |
| ARCH-02 | An import points at a file that does not exist | warn |

Full detail for each domain is in `references/` inside the skill, and
`ironclad rules explain <ID>` prints the same reasoning plus **what the rule
refuses to decide** — the part that matters when you disagree with a finding.

## Why these four domains and not more

A rule set is a claim about what can be checked honestly from source alone. Each
of these was measured on real repositories before it shipped, and several
proposed rules were dropped because the measurement said no:

- "a controller must not touch a model" fired on **6 of 7** controllers in a real
  Laravel repo — that is the framework's documented idiom, not a defect.
- "a skipped test" fired **zero** times across every repo on the machine that
  built this tool. A rule that has never fired is a rule nobody knows works.
- "a test file per module" assumed a mapping that never existed in a real
  monorepo: 15 test files across three workspaces.

These are not opinions about style. They are the residue of measurements, and the
measurements are recorded in `docs/PHASE2_API_DOMAIN.md` through
`docs/PHASE5_DX.md` in the repository.

## DB-01 — no enum columns

```sql
-- wrong
status ENUM('pending', 'paid', 'shipped')

-- right
status_code smallint NOT NULL REFERENCES order_status(code)
```

`enum` forces every new value through a schema migration. In MySQL that means
`ALTER TABLE`, which locks the table while it rewrites. Business status always
grows: "scheduled", "awaiting confirmation", "delayed by weather", "partially
refunded".

## DB-02 — no magic numbers

```php
// wrong: what is 2 and what is 7?
if ($order->status_code === 2 || $order->status_code === 7) { ... }

// right
if (in_array($order->status_code, [OrderStatus::PAID, OrderStatus::PARTIAL_REFUND], true)) { ... }
```

The checker flags comparisons against bare integer literals on status-like
columns. `INSERT` values and `CHECK` constraints are exempt — those are where
codes are legitimately declared.

> This is not an argument against arbitrary codes. `88`, `99`, `990` are all
> fine. What is not fine is a bare `88` appearing in application logic in five
> places with no name attached.

## DB-03 — status needs a lookup table and a foreign key

```sql
-- wrong: any integer is acceptable, including 87, which means nothing
status_code smallint NOT NULL

-- right: the database rejects anything not registered
status_code smallint NOT NULL REFERENCES order_status(code)
```

This is the rule that makes arbitrary codes safe. Without it, `88` and `8` are
equally valid to the database and equally wrong.

## DB-04 — no human labels as status

```sql
-- wrong
stock_state varchar(32)   -- 'In Stock', 'Sold Out', 'in stock '

-- right
stock_state_code smallint NOT NULL REFERENCES stock_state(code)
```

Text status invites whitespace variants, casing variants, translated labels, and
a `WHERE` clause that misses half the rows.

## DB-05 — no boolean for a non-binary concept

```sql
-- wrong: what does true mean here?
is_status boolean

-- right
status_code smallint NOT NULL REFERENCES ...
```

A boolean is correct only when the domain is genuinely two-valued and expected to
stay that way: `is_active`, `is_deleted`, `email_verified`.

## DB-06 — money must be exact, not `float`

```sql
-- wrong
total        float
amount       double precision
price        real

-- right (both are fine)
total_cents   bigint NOT NULL          -- 1250000 = 12,500.00
currency      char(3) NOT NULL         -- 'IDR'

total_amount  numeric(14,2) NOT NULL   -- fixed scale, also exact
```

Binary floating point cannot represent `0.10`. Sum a thousand rows of `float` and
the total is off by real money.

`numeric`/`decimal` **are exact** and the checker does not reject them — only binary
float (`float`, `real`, `double precision`) is flagged. Integer minor units are the
safest against step-by-step rounding and ORM quirks; `numeric` is easier to read and
fits calculations that need fractions (rates, percentages). Either is correct; mixing
the two for the same column in different places is not.

## DB-07 — no timestamp without a timezone

```sql
-- wrong
created_at timestamp

-- right
created_at timestamptz NOT NULL DEFAULT now()
created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
```

A naive timestamp is ambiguous across servers, timezones and DST. The checker
does not flag camelCase columns like `createdAt` in Prisma schemas — Prisma
handles the mapping, and flagging them was a false positive.

## DB-08 — One project, one status style

This is the rule that answers the team problem most directly: **not** "enum is
wrong", but "do not let one project use three approaches at once".

```sql
-- wrong: one project, two different styles
CREATE TABLE orders (
  status ENUM('new','paid','shipped')
);
CREATE TABLE shipments (
  status_code smallint NOT NULL REFERENCES shipment_status(code)
);
```

```
a.sql:1: [DB-08] warn
  status is stored 2 different ways in this project:
  enum (a.sql), integer (b.sql)
  pick one for the whole project; integer + lookup is the default
```

```sql
-- right: every table uses the same approach
CREATE TABLE orders (
  status_code smallint NOT NULL REFERENCES order_status(code)
);
CREATE TABLE shipments (
  status_code smallint NOT NULL REFERENCES shipment_status(code)
);
```

**Why:** enum and integer both work — what does not work is both in the same
project. Every report needs two queries, every new developer has to guess, and "how
do we add a status?" has no single answer. DB-08 is the only rule that reads
**across files**, because inconsistency is a property of the project, not of one
table.

**Why integer is the default:** adding an integer code adds one row of data; adding
an enum value is `ALTER TABLE`, which locks the table. Not taste — cost, when status
grows.

**Deviating on purpose:** if the team chooses enum, write the reason in
`.agent/standards.md`. What is forbidden is not a different choice — what is
forbidden is having no choice at all.

If you would rather not manage a config file at all, the `coherence` preset does the
same thing project-wide: `DB-01` only warns there, and `DB-08` stays an error. A repo
that consistently uses enums stays green, a repo that mixes stays red — with nothing
for you to write.

---

## Rule IDs are permanent

Numbers are never reused. If `DB-03` is retired, that number is retired with it —
not reassigned, because old review comments would then point at the wrong rule.
