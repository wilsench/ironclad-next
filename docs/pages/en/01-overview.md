---
title: What this is, and who it is for
slug: overview
group: Start
order: 1
summary: One page without jargon — the problem it solves, what you decide for yourself, and what you never have to touch.
---

# Ironclad, without the jargon

**Ironclad keeps one project consistent when more than one person — or more than
one AI — works on its database.**

Not an app. Not a subscription. Not a replacement for code review. It is one
understanding that agents read before writing code, one decision file that lives
in git, and one checker you can use if you want to.

## Where to start

| If you are… | Read |
|---|---|
| **not a programmer** — you commission or oversee this work | keep reading this page, then [For teams](/en/team/) |
| **a developer who wants to try before installing** | [Try it without installing](#try-it-without-installing) below |
| **a developer who is already convinced** | [Quickstart](/en/quickstart/) |
| **a developer who wants to know why it is built this way** | [Three layers](/en/three-layers/), then [Modes](/en/modes/) |

## The problem: two developers, two styles

This is not a story about AI. It is a story about teams.

One project. Three developers. All three touch the database.

Developer A stores order status as an **enum**:

```sql
status ENUM('new', 'paid', 'shipped')
```

Developer B stores the same thing as an **integer**:

```sql
status_code smallint NOT NULL
```

Both work. Both pass review, because each one makes sense on its own. What is
missing is a shared decision about which one this project uses.

Six months later: one table enum, one integer, one free text. A report needs three
different queries for the same thing. When a client asks for a new status,
developer C has to work out which table does which — because adding an enum value
and adding a lookup row are two very different jobs.

Nobody did anything wrong. One thing is missing: **a decision, written down and
read before anyone starts.** AI makes that gap wider — it writes in seconds,
across many files, and never asks "how does this project usually do it?"

## Four things you can configure

Ironclad has four parts. Each works on its own, and none is mandatory.

**1. The understanding that sits next to your agent.**
On install, a short block is written into the global config of whichever agents
are on the machine. It is read at the start of every session, in any repo: *read
the repo first, follow the style already there, never add a third.* This is the part
that stops an agent inventing its own taste.

**2. The decision that lives in git.**
`.agent/standards.md` holds what the team already agreed. Not one person's
preference — something you can quote in a PR review and a new hire can read on day
one.

**3. How hard the rules bite — a *preset*.**
Four levels, from "everything warns" to "everything blocks". This decides whether
CI goes red. See [Presets](/en/presets/).

**4. Who decides when the repo has no answer yet — a *mode*.**
Two choices: `ask` (the agent asks) or `house` (the agent applies the office
default). This is what separates "a neutral tool for anyone" from "a tool for one
team". See [Modes](/en/modes/).

Presets and modes get confused constantly. One sentence:

> **Mode** decides what happens *before* a decision exists.
> **Preset** decides what happens *after* the code is written.

## Ironclad has an opinion, and you do not have to share it

We lean toward **integer + lookup table** for status. The reason is technical, not
aesthetic: adding an enum value means `ALTER TABLE`, which can lock a large table;
adding an integer code means adding one row. Code `88` is safe as long as `88`
exists in the lookup and is guarded by a foreign key; `87` is rejected.

But that is an **opinion**, not a law. If you already use enums consistently and do
not want to change, use the `coherence` preset: no style is punished there. Only one
thing fails — the same concept stored two different ways in one project. That is the
one claim we can defend to anybody, and it is also exactly the problem our own
office had.

## Try it without installing

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} check .
```

Runs the checker, prints findings, exits. **No files written, no agent config
touched.** If it comes back clean, your repo is already coherent and you do not
need to install anything.

If you want the neutral reading — the one that does not consider enums a defect:

```bash
npx github:wilsench/ironclad-next#v{{VERSION}} check . --preset coherence
```

## If you are not the one writing the code

You can still use this, and you never have to read a line of code.

**Send this page to your developer.** Ask them to run the two commands in the
[Quickstart](/en/quickstart/), then commit the result.

**Then ask these four questions.** The answers tell you whether this was actually
installed or merely promised:

1. **"Is this repo consistent, or mixed?"** — the right answer names a number of
   findings, not "it's done".
2. **"Which preset is it on?"** — one of `legacy-friendly`, `strict`, `balanced`,
   or `coherence`. If the answer is "what is a preset", it hasn't been run.
3. **"Does a violating pull request actually fail?"** — if they have never tested
   it with a real PR, the gate is unproven.
4. **"When a new table needs a status, who decides the style?"** — a good answer
   names one file (`.agent/standards.md`) or one mode (`house`). "Depends on the
   developer" means the problem is still there.

**What you do not need to learn:** how the checker works, what a foreign key is,
or what is in the YAML file.

## What Ironclad does not do

- **It is not a replacement for a programmer.** It writes no features, fixes no bugs.
- **It is not a replacement for review.** It catches patterns; it cannot know whether
  your business logic is right.
- **It is not a security audit.** It checks three things a file can prove — a
  credential in a file git could ship, a credential hardcoded in source, and an
  `.env.example` that has drifted from `.env`. It does not find access-control
  holes, injection, or anything that needs the app running.
- **It does not change how your app looks.** Nothing to do with design.
- **It sends no data anywhere.** Everything runs on your own machine.

## The honest limits

- **The checker matches patterns, it does not understand code.** It can flag
  something correct and miss something wrong. A human stays the last layer.
- **The scope is deliberately narrow.** Sixteen rules across four domains — how
  status, money and time are stored; how endpoints answer; what leaked; and how
  the modules depend on each other. Not two hundred rules. A tool that tries to
  catch everything loses to a dedicated linter, and nobody installs it twice.
- **Several rules were dropped after measuring them.** "A controller must not
  touch a model" fired on 6 of 7 controllers in a real Laravel repo. It is not in
  the tool.
- **Unsupported frameworks stop honestly** (`exit 2`) instead of pretending to be green.
- **It cannot force anyone to read.** If CI is not wired up and
  `.agent/standards.md` is ignored, nothing catches it. The gate does the work, not
  good intentions.
- **There are no users outside our own team yet.** We cannot claim this helps
  strangers — only that it solves one real problem here.
- **There is no auto-update.** For a new version, run the installer again.

## Where next

| If you want to… | Read |
|---|---|
| know the vocabulary used here | [Glossary](/en/glossary/) |
| install now | [Install](/en/install/) |
| know the difference between mode and preset | [Modes](/en/modes/) · [Presets](/en/presets/) |
| see the full walkthrough | [Quickstart](/en/quickstart/) |
| know when a new version exists | [Updating](/en/update/) |
| know which rules are checked | [Rules](/en/rules/) |
| know why tools like this get abandoned | [Three layers](/en/three-layers/) |
