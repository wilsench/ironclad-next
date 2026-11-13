---
title: FAQ
slug: faq
group: Operations
order: 32
summary: The questions that keep coming up, answered without circling.
---

# FAQ

## Do I have to run Python?

**To install: yes, Python 3.8+.** Not to download — the installer is bash + curl —
but to write the rule block into `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`. If
`python3` is missing the installer now stops with exit 3 and says so, instead of
printing "installed" over an empty config.

`python3` is preinstalled on macOS, most Linux distributions, and Termux. If yours
does not have it: `sudo apt install python3` (Debian/Ubuntu), `brew install python3`
(macOS).

**To run the checker: yes**, same requirement. The checklist itself is optional —
if all you want is the agent reading the rules, the skill plus `.agent/standards.md`
is enough.

## Does the skill activate automatically on every agent run?

Yes, but that does **not** mean it is always used. Every turn the agent sees a list
of skill names and descriptions. It loads the full `SKILL.md` only when the task
matches.

So: no command to run, and no "do you want to use this skill?" prompt. The agent
decides, the same way it decides which tool to call.

If you want certainty, name it: "use the ironclad skill for this migration".

## Can it be shorter than this?

Install:

```bash
npx github:wilsench/ironclad#v{{VERSION}}
```

Then, in a repo:

```bash
ironclad check      # look
ironclad init       # make it stick
```

One command. No clone, no reading required — and no `ironclad init` unless you want
the rules pinned in git for your team.

## Does the installer work for agents other than Hermes?

Yes — that is its main target. Six targets: Hermes, Claude Code, Codex, Cursor,
opencode, Antigravity. The format is the Agent Skills standard (`SKILL.md`), not
something Hermes-specific.

```bash
npx github:wilsench/ironclad#v{{VERSION}}  --all              # everything detected on this machine
npx github:wilsench/ironclad#v{{VERSION}}  --target claude
npx github:wilsench/ironclad#v{{VERSION}}  --target gemini    # Antigravity, global
npx github:wilsench/ironclad#v{{VERSION}}  --target opencode
```

## Can I use `wilsench/ironclad` directly?

For Hermes:

```bash
hermes skills install wilsench/ironclad/skills/ironclad
```

Other agents use `npx github:wilsench/ironclad#v{{VERSION}}` — that pulls the package
straight from the public repo, with nothing published to npm. If the machine has no
Node, the `install.sh` mirror on `wilsench.my.id` runs the same code.

## Is `curl | bash` safe?

The installer is about 190 lines of bash and you can read it first:

```bash
curl -fsSL https://wilsench.my.id/ironclad/install.sh | less
```

What it does: downloads 11 text files, copies them into one skill directory, and —
only if you pass `--project` — writes `.agent/` in the repo you named. No `sudo`,
no shell profile changes, no touching other skills.

## Does it work without git?

Yes. The skill is just a directory of files. The checker just needs a path. You
lose two things: `.agent/standards.md` has no history, and nothing runs in CI.

## Why not just use `enum`?

Because adding one value means `ALTER TABLE`. In MySQL, on a large table, that
locks the table while it rewrites. Business status always grows, and every growth
should not be a migration event.

But `enum` is **not banned outright**. If the values are deliberate and only
change through code review, write the reason in the migration comment — `balanced`
accepts that.

## What about codes like `88`, `99` instead of 0, 1, 2?

Completely fine. Codes do not have to be sequential or start at zero. What makes
them safe: the code is registered in a lookup table (so `87` is rejected by the
database) and used through named constants in application code.

Reserving blocks — `8x` for stock, `9x`/`99x` for departures — keeps raw numbers
readable when they show up in a query result six months later.

## Does this replace code review?

No. The checker catches syntactic patterns; it does not know whether
`status_code = 7` is correct business logic. It removes repetitive review work,
it does not replace the reviewer.

## What if our company rules are different?

That is the point. Edit `.agent/standards.md` and `.agent/standards.yml` in your
repo. The skill does not change, and nothing needs reinstalling. Rules that do not
fit can be set to `warn` or `off` — as long as the reason lands in a PR.

## Is there auto-update?

Not yet. `hermes skills update` reuses the URL from install; other agents need the
installer re-run. There is no versioned changelog. If you change the rules, what
you share is `.agent/standards.md` in your repo — it travels with git and reaches
everyone automatically.

## What is the context cost?

`SKILL.md` is roughly 7 KB, but the agent loads it only when the task matches.
What is always in context is one description line. The references
(`database.md`, `presets.md`) are read only when the agent needs detail.

## I already have other skills and rules installed. Does this conflict?

Nothing is overwritten. The installer only appends one fenced block at the **end** of
the config file that already exists:

```
<!-- ironclad:begin v1 -->  ...  <!-- ironclad:end -->
```

Rules, styles or other skills in that same file stay exactly where they are — before
and after the block. The only thing ever removed is what sits between those two
markers, and only when you re-run the installer or `--uninstall`.

Three things are tested:

- **Installing twice** — produces no duplicate block (`unchanged`).
- **Uninstall** — the file returns to exactly what it was, other rules intact,
  line count included.
- **`ironclad init` in a repo that already has `AGENTS.md` and `.agent/standards.md`** —
  the team's rules survive, and a `standards.md` you filled in is not replaced.

One thing that could count as interference: the block is read in **every session** of
the agent, for every repo, because that is the point. It is ~1,150 characters. If that
is too much, remove it with `--uninstall`; the skill and the tooling still work if you
invoke them by hand.

## I do not agree that enums are wrong. Can I still use this?

Yes — preset `coherence`:

```bash
npx github:wilsench/ironclad#v{{VERSION}} check . --preset coherence
```

Under that preset no style is punished: `enum`, a coded text column, and integer +
lookup are all acceptable. Only one thing fails — the same concept stored two different
ways in one project. That is the entire thesis; the rest is taste, and your taste does
not have to match anyone else's.

## Can I try it without installing?

```bash
npx github:wilsench/ironclad#v{{VERSION}} check .
```

That runs the checker and exits. No files written, no agent config touched. If it comes
back clean, your repo is already coherent — and you do not need to install anything.
