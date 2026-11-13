---
title: For your team
slug: team
group: Start
order: 7
summary: How to roll this out without touching every repo at once, and who decides when the agent stops and asks.
---

# Rolling it out to a team

Ironclad is not a rule imposed from above. It is one small behaviour: before an agent
writes a status column, it reads that repo first, and stops if the repo already
disagrees with itself. Everything else — when to use it, in which repo, and which
style becomes the standard — is your call.

This page is the order that causes the least friction.

## The order that works

### 1. One pilot repo, not all of them

Pick the repo that has the most history with status: the one whose reports need
`CASE WHEN`, or whose migrations were patched two different ways. Not the biggest,
and not the quietest.

Run this once in that repo:

```bash
cd repo-pilot
ironclad check
```

That only reads. If it comes back clean, the repo is too tidy to be a useful pilot —
pick another one. A useful pilot is one that **produces findings**.

### 2. Write the decision down, do not leave it blank

The installer already plants a house default (`status_code` + lookup + FK) for new
tables. But a pilot repo usually **already** has its own style, and the repo's style
always wins.

The only decision you need to record in `.agent/standards.md` is one sentence: how
this project stores status, and why. If the repo is already consistent, write down
the style it already uses — not the default.

```bash
ironclad init      # only to pin the decision into git
```

An untouched template is replaced on upgrade. A file you filled in is not.

### 3. One developer tries it first

Send it to **one** person, ideally one who uses a different agent than you. All they
have to run is:

```bash
npx github:wilsench/ironclad#v{{VERSION}} --mode house
```

`--mode house` is what makes everyone default to the same style for new tables. Without
it the installer uses `ask`, and the agent asks instead of choosing.

Then ask them to open the pilot repo and ask their agent:

> Before writing a status column, what is the rule?

A correct answer names three things: read the repo first, follow the existing style,
and use `status_code` + lookup if there is none yet. If the agent only says "use an
integer" without mentioning reading the repo, the block did not load.

### 4. Then spread it

Once one person is working, hand out the same command. There is no per-repo setup and
nothing to commit, unless you want the decision pinned in git via `ironclad init`.

## When the agent stops and asks

There are two kinds of questions, and only one needs an answer from you.

**"May I write it now?"** — that is manners. Answer it.

**"This repo has two status styles, which one is the standard?"** — that is the one
that matters. The agent stopped on purpose, because choosing on its own would add a
third style. Whatever you answer that day becomes the repo's standard. Write it in
`.agent/standards.md` so the next agent — and the next person — does not ask again.

If you do not know the answer, "follow whichever is used most" is a valid answer. What
is not valid: silence, then letting the agent pick.

## Agree on these up front

Three things the tool does not decide for you, and that are better settled before you
spread it:

- **Status style for new repos** — the house default is `status_code` + lookup. If your
  team is more comfortable with a native `enum`, change it now, not after ten tables.
- **Money** — `numeric(14,2)` or integer minor units. Both are valid; only `float` is not.
- **Legacy repos** — leave them, or unify them slowly. Recommendation: leave them.
  Rewriting a working schema to chase a default is how you lose a weekend and gain a bug.

## If something does not work

Before anyone reports a problem, ask them for one thing:

```bash
ironclad version
```

That prints the skill version, its location, and the size of the installed block. Those
three numbers separate almost every failure: old version, wrong directory, or block
never written.

If the version is right and the agent still does not ask, then that agent is not loading
the file we wrote. That needs reporting — not assuming.
