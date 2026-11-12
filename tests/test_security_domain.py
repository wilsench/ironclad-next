"""Tests for the security domain.

The important assertions here are the silences. A secret scanner is judged by what
it does not say: on three real repositories, plain entropy produced 1.647 + 408 +
536 findings, and the difference between a tool people keep and a tool they
disable is entirely in the negative cases below.

No test prints a secret. Fixtures use obviously fake values, and the assertions
check that findings do not contain the value either.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "ironclad"))

from ironclad_core.domains import load_all  # noqa: E402
from ironclad_core.domains.security import looks_like_secret  # noqa: E402
from ironclad_core.engine import FileContext, run  # noqa: E402

PASS, FAIL = [], []

# Fake but high-entropy, in the shape each vendor uses. Never a real credential.
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.KeepThisOutOfTheReport1234567890"
FAKE_STRIPE = "sk_test_51H8xQ2eZvKYlo2C9mNpQrStUvWxYzAbCdEfGh"
FAKE_APP_KEY = "base64:8fJ2kL9pQrT4vWxY7zA1bC3dE5fG6hI8jK0lM2nO4pQ="


def check(label, got, want) -> None:
    if got == want:
        PASS.append(label)
    else:
        FAIL.append(f"{label}: got {got!r}, want {want!r}")


def _git(d: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(d), *args], check=True,
                   capture_output=True, text=True)


def _scan(d: Path) -> list:
    cfg = {"name": "balanced", "rules": {}, "exceptions": [], "sources": []}
    return run(load_all(), cfg, [str(d)], source="test").findings


def api_rules(findings) -> list[str]:
    return sorted({f.rule for f in findings if f.rule.startswith("SEC")})


def test_evidence_function():
    """The value classifier, in isolation."""
    check("secret: jwt shape", looks_like_secret(FAKE_JWT), True)
    check("secret: stripe shape", looks_like_secret(FAKE_STRIPE), True)
    check("secret: laravel app key", looks_like_secret(FAKE_APP_KEY), True)

    check("not: placeholder", looks_like_secret("change-me"), False)
    check("not: xxxxxxxx", looks_like_secret("xxxxxxxxxxxxxxxxxxxx"), False)
    check("not: env reference", looks_like_secret("${APP_KEY}"), False)
    check("not: getenv call", looks_like_secret("getenv('APP_KEY')"), False)
    check("not: php class", looks_like_secret("Illuminate\\Auth\\Passwords\\PasswordBrokerManager"),
          False)
    check("not: url", looks_like_secret("https://example.com/some/long/path"), False)
    check("not: date", looks_like_secret("2026-11-13T01:22:33+07:00"), False)
    check("not: short", looks_like_secret("hunter2"), False)
    check("not: dotted map key", looks_like_secret("auth.password"), False)


def test_hardcoded_secret():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "config.php").write_text(
            "<?php\nreturn [\n"
            f"    'stripe_secret' => '{FAKE_STRIPE}',\n"
            "    'db_password' => 'change-me',\n"
            "    'api_key' => getenv('API_KEY'),\n"
            "];\n")
        found = _scan(d)
        check("hardcoded: one finding", api_rules(found), ["SEC-02"])

        # The finding must not quote the value: a report is not a second leak.
        body = " ".join(f.message for f in found)
        check("hardcoded: value never appears in the message",
              FAKE_STRIPE in body, False)
        check("hardcoded: key name is named",
              "stripe_secret" in body, True)


def test_laravel_cache_is_not_a_leak():
    """`'auth.password' => 'Illuminate\\...'` is wiring, not a credential.

    This exact shape produced the only two false positives on real repos, and it
    is the single most common false positive in a Laravel project.
    """
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "services.php").write_text(
            "<?php\nreturn [\n"
            "    'auth.password' => 'Illuminate\\Auth\\Passwords\\PasswordBrokerManager',\n"
            "    'auth.password.broker' => 'Illuminate\\Auth\\Passwords\\PasswordBroker',\n"
            "];\n")
        check("cache: framework wiring is silent", api_rules(_scan(d)), [])


def test_env_states():
    """Tracked, untracked, ignored, and no repository at all are four answers."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _git(d, "init", "-q")
        _git(d, "config", "user.email", "t@example.com")
        _git(d, "config", "user.name", "t")
        (d / ".env").write_text(f"JWT_ACCESS_SECRET={FAKE_JWT}\nAPP_ENV=local\n")

        # 1. untracked, not ignored → warn (one `git add .` from being shipped)
        found = _scan(d)
        check("env untracked and unignored: warns", api_rules(found), ["SEC-01"])
        check("env untracked and unignored: warn severity",
              [f.severity for f in found if f.rule == "SEC-01"], ["warn"])

        # 2. ignored → silent, which is what correct looks like
        (d / ".gitignore").write_text(".env\n")
        check("env ignored: silent", api_rules(_scan(d)), [])

        # 3. tracked → error, it is already in the history
        _git(d, "add", "-f", ".env")
        _git(d, "add", ".gitignore")
        _git(d, "-c", "user.email=t@e.com", "-c", "user.name=t",
             "commit", "-qm", "oops")
        found = _scan(d)
        check("env tracked: error", api_rules(found), ["SEC-01"])
        check("env tracked: error severity",
              [f.severity for f in found if f.rule == "SEC-01"], ["error"])
        check("env tracked: says it is in history",
              "history" in " ".join(f.message for f in found), True)


def test_env_without_repository_is_silent():
    """A production `.env` with no git around it cannot leak through git.

    On this very server the live `.env` files sit in exactly that state. Flagging
    them was the false positive that would have made the whole domain useless.
    """
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / ".env").write_text(f"JWT_ACCESS_SECRET={FAKE_JWT}\n")
        check("no repository: silent", api_rules(_scan(d)), [])


def test_env_example_is_not_a_leak():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _git(d, "init", "-q")
        (d / ".env.example").write_text(f"JWT_ACCESS_SECRET={FAKE_JWT}\n")
        _git(d, "add", "-A")
        check("example: never reported", api_rules(_scan(d)), [])


def test_env_example_diverges():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / ".env").write_text(
            f"JWT_ACCESS_SECRET={FAKE_JWT}\nDB_HOST=127.0.0.1\nMAIL_FROM=a@b.c\n")
        (d / ".env.example").write_text("DB_HOST=\n")
        found = _scan(d)
        check("example diverges: SEC-03", api_rules(found), ["SEC-03"])
        check("example diverges: names the missing key",
              "MAIL_FROM" in " ".join(f.message for f in found), True)


def test_generated_bundles_are_skipped():
    """A minified bundle is one huge line; nothing on it is hand-written."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        filler = "var a" + "x" * 400 + ";"
        (d / "app.min.js").write_text(
            filler + f"var api_key='{FAKE_STRIPE}';" + filler + "\n")
        check("bundle: skipped by name", api_rules(_scan(d)), [])

        (d / "vendor_like.js").write_text(
            "\n".join(["var padding = '" + "y" * 300 + "';"] * 40) +
            f"\nvar api_key = '{FAKE_STRIPE}';\n")
        check("bundle: skipped by line length", api_rules(_scan(d)), [])


def test_disabled_domain_rule():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "a.php").write_text(f"<?php\n$config = ['stripe_secret' => '{FAKE_STRIPE}'];\n")
        cfg = {"name": "balanced", "rules": {"SEC-02": "off"}, "exceptions": [],
               "sources": []}
        check("config: SEC-02 off is silent",
              api_rules(run(load_all(), cfg, [str(d)], source="t").findings), [])


def main() -> int:
    print("Security domain tests\n")
    for fn in (test_evidence_function, test_hardcoded_secret,
               test_laravel_cache_is_not_a_leak, test_env_states,
               test_env_without_repository_is_silent,
               test_env_example_is_not_a_leak, test_env_example_diverges,
               test_generated_bundles_are_skipped, test_disabled_domain_rule):
        print(f"{fn.__name__}:")
        before = len(PASS)
        fn()
        print(f"  {len(PASS) - before} checks passed")
    for label in PASS:
        print(f"  PASS  {label}")
    for line in FAIL:
        print(f"  FAIL  {line}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
