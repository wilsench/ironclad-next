#!/usr/bin/env node
// Entry point for `npx github:wilsench/ironclad-next`.
//
// Node is only a delivery mechanism here — npm runs this file, which locates the
// bash installer that already sits next to it in the package and hands over. All
// the real logic stays in install.sh so `curl | bash` and `npx` run identical code.
// Two installers that drift apart is the exact class of bug this tool exists to
// prevent.

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
// index.mjs lives in cli/, install.sh in the package root.
const installer = join(here, "..", "install.sh");

if (!existsSync(installer)) {
  console.error("ironclad: install.sh is missing from this package.");
  console.error("This usually means npm pack ignored it — check the files list in package.json.");
  process.exit(1);
}

const hasBash = spawnSync("bash", ["-c", "true"], { stdio: "ignore" });
if (hasBash.error || hasBash.status !== 0) {
  console.error("ironclad: bash is required. On Windows use WSL or Git Bash.");
  process.exit(3);
}

const argv = process.argv.slice(2);

// Read-only subcommands. This is the front door for someone who does not want to
// install anything yet: `npx github:wilsench/ironclad-next check .` answers "does this repo
// already store status two ways" and exits, without touching a single agent config.
// Without it, the only way to try the tool was to install it first — backwards.
if (argv[0] === "check" || argv[0] === "scan") {
  const checker = join(here, "..", "skills", "ironclad", "scripts", "check_schema.py");
  if (!existsSync(checker)) {
    console.error("ironclad: check_schema.py is missing from this package.");
    process.exit(1);
  }
  const target = argv.slice(1).filter((a) => !a.startsWith("-"));
  const flags = argv.slice(1).filter((a) => a.startsWith("-"));
  const py = spawnSync("python3", ["--version"], { stdio: "ignore" });
  if (py.error || py.status !== 0) {
    console.error("ironclad: `check` needs python3. Install it, or skip this step and");
    console.error("use the installer instead — the agent instruction does not need Python.");
    process.exit(3);
  }
  const check = spawnSync("python3", [checker, ...target.length ? target : ["."], ...flags], {
    stdio: "inherit",
    env: process.env,
  });
  process.exit(check.status ?? 1);
}

// Everything else is passed straight through, so `--uninstall`, `--mode house` and
// `--dry-run` work unchanged.
const result = spawnSync("bash", [installer, ...argv], {
  stdio: "inherit",
  env: process.env,
});

if (result.error) {
  console.error(`ironclad: could not run the installer: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
