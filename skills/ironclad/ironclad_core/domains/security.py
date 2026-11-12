"""The security domain: what leaked, and what is about to leak.

This is the domain that gets a tool uninstalled. A secret scanner that cries wolf
at 1.647 places in one repo teaches people to ignore the whole tool, so every rule
here answers one question — *is there evidence?* — and stays silent otherwise.

Measured, not assumed. On three real repositories:

  entropy alone (any high-entropy assignment)        1647 + 408 + 536 findings
  credential-named key + entropy + placeholder skip       2 findings, both wrong
  the same, plus "a PHP class name is not a secret"       0 findings
  planted control (sk_live_..., base64 app key)           1 finding, correct

The two wrong ones were `'auth.password' => 'Illuminate\\Auth\\...'` in a Laravel
cache file. The value is a class name. That is the most useful negative case this
domain has, and it is why the class-name and framework-wiring guards exist.

Secrets are **never** printed. A finding says which file, which line, which name,
and what to do — never the value. Printing it would turn the report into a second
copy of the leak, in a log and in a CI artefact.

The `.env` rule learned the hard way that "a file exists" is not evidence of a
leak: on this server the production `.env` is exactly where it belongs, and there
is no git repository at all. The rule now checks for a *repository* before it
talks about *committing*, and reports the weaker, universally true problem
otherwise: a credential store with no ignore rule guarding it.
"""

from __future__ import annotations

import re
import subprocess
from math import log2
from pathlib import Path

from .. import Finding, Position, RuleMeta
from ..discovery import matches
from ..engine import FileContext, ProjectRule, Registry, Rule

DOMAIN = "security"

# `.env` is claimed by NAME, not extension: `Path(".env").suffix` is empty, so an
# extension set can never match a dotfile. That bug made SEC-01 blind in the one
# place it matters most — found because a repo with a real `.env` reported none.
SCAN_EXTS = (".php", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".py", ".rb", ".go",
             ".java", ".kt", ".cs", ".rs", ".yml", ".yaml", ".json", ".ini",
             ".env", ".sh", ".tf", "env")

_SKIP_PARTS = {"node_modules", "vendor", ".git", "dist", "build", "coverage",
               ".next", "storage", "__pycache__", ".venv", "venv"}

# The tool's own policy file is configuration about the tool, not application
# source. Scanning it means a repo's standards file is judged by the rules it
# configures — and `exceptions:` there is a path list, not a secret.
_TOOL_POLICY = re.compile(r"(?:^|/)\.agent/standards\.(?:yml|yaml|md)$")
_SKIP_NAMES = re.compile(r"\.(?:min|bundle|chunk)\.[cm]?js$|\.map$|\.lock$", re.I)
_TESTISH = re.compile(r"(?:^|/)(?:tests?|specs?|__tests__|fixtures)/|"
                      r"\.(?:test|spec)\.[cm]?[jt]sx?$", re.I)

# A name that promises a credential. Narrow on purpose: `key` alone is a map key,
# `token` alone is a lexer token. Only shapes that unambiguously mean auth.
CRED_NAME = re.compile(
    r"(?i)(?:secret|passw(?:or)?d|pwd|api[_-]?key|apikey|access[_-]?key|"
    r"private[_-]?key|client[_-]?secret|auth[_-]?key|credential|"
    r"bearer|access[_-]?token|refresh[_-]?token|auth[_-]?token|session[_-]?secret)")

ASSIGN = re.compile(
    r"""(?:"|')?(?P<key>[A-Za-z0-9_.\-]{3,40})(?:"|')?\s*"""
    r"""(?::=|=>|=|:)\s*(?:"|')(?P<val>[^'"\n]{8,300})(?:"|')""")

PLACEHOLDER = re.compile(
    r"^(?:x+|\*+|\.+|-+|change[-_]?me|your[-_].*|example.*|placeholder.*|dummy.*|"
    r"sample.*|todo|fixme|<.*>|\$\{.*\}|\{\{.*\}\}|%\(.*\)s|null|none|nil|"
    r"true|false|0|1|.*_here|.*_key_here|redacted)$", re.I)

_CLASS_REF = re.compile(r"^[A-Z][A-Za-z0-9_]*(?:\\\\?[A-Za-z0-9_]+){2,}$")
_CONFIG_MAP_KEY = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9]+){1,}$")


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * log2(c / n) for c in counts.values())


def looks_like_secret(value: str) -> bool:
    """Evidence, in order: not a placeholder, long enough, varied enough, not code."""
    v = value.strip()
    if not v or PLACEHOLDER.match(v):
        return False
    if _CLASS_REF.match(v):
        return False
    if len(v) < 16 or len(set(v)) < 8:
        return False
    # A call, not a literal: `getenv('API_KEY')`, `process.env.X`, `os.environ[...]`,
    # `System.getenv(...)`. Each is already read from the environment.
    if re.search(r"getenv\s*\(|process\.env|os\.environ|ENV\[|\$ENV", v):
        return False
    if re.search(r"[\s@]|https?://|localhost|127\.0\.0\.1|\$\{|\{\{|%\(|::", v):
        return False
    if re.fullmatch(r"[\d.\-/:_]+", v):          # dates, versions, timestamps
        return False
    if re.search(r"[A-Za-z]\\[A-Za-z]", v):      # Foo\Bar namespace
        return False
    return _entropy(v) >= 3.3


def _scannable(ctx: FileContext) -> bool:
    if not matches(ctx.path, SCAN_EXTS):
        return False
    if _TOOL_POLICY.search(str(ctx.path)):
        return False
    if set(ctx.path.parts) & _SKIP_PARTS or _SKIP_NAMES.search(ctx.path.name):
        return False
    if _TESTISH.search(str(ctx.path)):
        return False
    lines = ctx.lines or [""]
    # A bundler writes one enormous line; nothing on it is a hand-written secret,
    # and scanning it produces the 1.647 false positives measured above.
    return sum(len(ln) for ln in lines) / len(lines) <= 250


def _is_dotenv(ctx: FileContext) -> bool:
    return ctx.path.name == ".env" or ".env." in ctx.path.name


def _is_example(ctx: FileContext) -> bool:
    return ctx.path.name.endswith((".example", ".sample", ".template", ".dist"))


def dotenv_assignments(text: str):
    """`KEY=value` lines of a dotenv file, comments and blanks skipped."""
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        yield i, key.strip(), val.strip().strip("'\"")


def _repo_root(start: Path) -> Path | None:
    """The nearest enclosing git work tree, or None. Never runs outside it."""
    here = start.resolve()
    for d in [here, *here.parents]:
        if (d / ".git").exists():
            return d
    return None


def _tracked(repo: Path, target: Path) -> bool | None:
    """True if git tracks this file, False if it does not, None if we cannot say."""
    try:
        rel = target.resolve().relative_to(repo.resolve())
    except ValueError:
        return None
    try:
        r = subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch",
                            str(rel)],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode == 0:
        return True
    if "did not match" in r.stderr or r.returncode == 1:
        return False
    return None


def _ignored(repo: Path, target: Path) -> bool | None:
    try:
        r = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", str(target)],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    return None


class Sec01EnvExposure(Rule):
    """A credential store that git can ship, and no rule saying don't.

    Three states, deliberately separated because they are different problems:

    - tracked by git              → severity error: it is already shipped
    - untracked but not ignored   → warn: one `git add .` from being shipped
    - untracked and ignored       → silent: this is what correct looks like
    - no repository at all        → silent: the file cannot leak through git, and
                                    a server's production `.env` is supposed to be
                                    there. Accusing it would be the false positive
                                    that discredits the whole domain.
    """
    extensions = SCAN_EXTS
    meta = RuleMeta("SEC-01", DOMAIN, "credentials in a file git could ship", "warn")

    def applies(self, ctx: FileContext) -> bool:
        return _is_dotenv(ctx) and not _is_example(ctx)

    def check(self, ctx: FileContext, cfg):
        if not _scannable(ctx):
            return []
        secrets = [(i, k) for i, k, v in dotenv_assignments(ctx.text)
                   if CRED_NAME.search(k) and looks_like_secret(v)]
        if not secrets:
            return []

        repo = _repo_root(ctx.path)
        if repo is None:
            return []                        # cannot be committed; not our business

        names = sorted({k for _, k in secrets})[:3]
        tracked = _tracked(repo, ctx.path)
        if tracked:
            return [Finding(
                rule="SEC-01", severity="error", file=str(ctx.path),
                position=Position(secrets[0][0]), domain=DOMAIN,
                message=(f"`.env` is tracked by git and holds {len(secrets)} real "
                         f"credential(s) ({', '.join(names)}); it is already in the "
                         f"history — untrack it, rotate the values, ship "
                         f"`.env.example`"))]

        if _ignored(repo, ctx.path):
            return []                        # untracked and ignored: correct

        return [Finding(
            rule="SEC-01", severity="warn", file=str(ctx.path),
            position=Position(secrets[0][0]), domain=DOMAIN,
            message=(f"`.env` holds {len(secrets)} real credential(s) "
                     f"({', '.join(names)}) and no ignore rule covers it; one "
                     f"`git add .` puts them in the history. Add it to .gitignore"))]


class Sec02HardcodedSecret(Rule):
    """A credential-looking value written into source instead of configuration.

    Reports the name and the place, never the value: a report that quotes the
    secret is a second copy of the secret, in a log and a CI artefact.
    """
    extensions = SCAN_EXTS
    meta = RuleMeta("SEC-02", DOMAIN, "credential hardcoded in source", "error")

    def applies(self, ctx: FileContext) -> bool:
        # Dotenv is SEC-01's job: it sees the whole file at once, and calling a
        # config file "hardcoded" is technically true and practically wrong.
        return _scannable(ctx) and not _is_dotenv(ctx)

    def check(self, ctx, cfg):
        out = []
        for i, line in enumerate(ctx.lines, 1):
            m = ASSIGN.search(line)
            if not m:
                continue
            key, val = m.group("key"), m.group("val")
            if not CRED_NAME.search(key) or not looks_like_secret(val):
                continue
            if _CONFIG_MAP_KEY.match(key) and "\\" in val:
                continue          # framework wiring: 'auth.password' => Some\Class
            out.append(Finding(
                rule="SEC-02", severity="error", file=str(ctx.path),
                position=Position(i), domain=DOMAIN,
                # Deliberately no value, and not even a prefix of it.
                message=(f"`{key}` is assigned a literal credential; read it from the "
                         f"environment. The value is not printed here on purpose")))
        return out


class Sec03EnvExampleDiverges(ProjectRule):
    """`.env.example` stopped documenting a variable the real `.env` requires.

    Only fires when both exist, because the example is spec and the real file is
    the truth. Naming drift is how a teammate clones a repo and hits a runtime
    error nobody can explain.
    """
    extensions = SCAN_EXTS
    meta = RuleMeta("SEC-03", DOMAIN, "`.env.example` and `.env` disagree", "warn",
                    scope="project")

    def applies_to(self, ctx: FileContext) -> bool:
        return _is_dotenv(ctx)

    def check(self, contexts, cfg):
        envs = [c for c in contexts if _is_dotenv(c)]
        reals = [c for c in envs if not _is_example(c)]
        examples = [c for c in envs if _is_example(c)]
        if not reals or not examples:
            return []

        key_re = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
        real_keys = {k for c in reals for _, k, _ in dotenv_assignments(c.text)
                     if key_re.match(k)}
        ex_keys = {k for c in examples for _, k, _ in dotenv_assignments(c.text)
                   if key_re.match(k)}

        missing = real_keys - ex_keys
        if not missing:
            return []
        ex = examples[0]
        return [Finding(
            rule="SEC-03", severity="warn", file=str(ex.path), position=Position(1),
            domain=DOMAIN,
            message=(f"{len(missing)} variable(s) exist in `.env` but not in "
                     f"`{ex.path.name}`: {', '.join(sorted(missing)[:4])} — a new "
                     f"clone will fail on the ones nobody documented"))]


def register(reg: Registry) -> None:
    for rule in (Sec01EnvExposure(), Sec02HardcodedSecret(),
                 Sec03EnvExampleDiverges()):
        reg.add(rule)


# ------------------------------------------------------------------- dropped
# SEC-04 "no secrets in git history" — needs `git log -S`, which means rescanning
#   history on every run. Belongs in `ironclad doctor`, not a file checker.
# SEC-05 "dependencies with known CVEs" — a network call and a vulnerability
#   database. This tool must stay useful offline; a stale bundled list is worse
#   than none.
# SEC-06 "authz on every route" — middleware can be applied by a group, a service
#   provider, or the kernel, and a regex cannot see inheritance. Laravel repos
#   would light up for code that is protected.
# SEC-07 "SQL injection via concatenation" — the honest test is whether a query
#   builder is used, which is AST work over several call shapes. Regex on
#   `query(` + `+` produced mostly false positives on log strings.
