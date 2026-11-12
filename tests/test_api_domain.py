"""Tests for the API domain, run against text — no repository required.

Half of these are negative on purpose. The first draft of this domain passed 20
cases while producing 95 findings on a healthy Express repo, so "does it fire"
is the easy half; "does it stay quiet" is the one that decides whether anyone
keeps the tool installed.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "ironclad"))

from ironclad_core.domains.api import (  # noqa: E402
    extract_routes, is_route_file, norm_path, segment_style)
from ironclad_core.domains import load_all  # noqa: E402
from ironclad_core.engine import FileContext  # noqa: E402
from ironclad_core.report import Result  # noqa: E402

PASS, FAIL, NOTES = [], [], []


def check(label: str, got, want) -> None:
    if got == want:
        PASS.append(label)
    else:
        FAIL.append(f"{label}: got {got!r}, want {want!r}")


def ctx(name: str, text: str) -> FileContext:
    return FileContext(path=Path(name), text=text, language="test")


def run_api(*contexts) -> list:
    """Run only the API rules over these contexts."""
    reg = load_all(only=("api",))
    out = []
    for i, c in enumerate(contexts):
        for rule in reg.file_rules:
            if rule.applies(c):
                out.extend(rule.check(c, {}))
    for rule in reg.project_rules:
        out.extend(rule.check(list(contexts), {}))
    return out


# ---------------------------------------------------------------- detection
def test_route_extraction():
    laravel = ctx("routes/web.php", """<?php
Route::get('/users', [UserController::class, 'index']);
Route::post('/users', [UserController::class, 'store']);
// Route::get('/commented', [X::class, 'y']);
Route::match(['put', 'patch'], '/users/{id}', [UserController::class, 'update']);
""")
    routes = extract_routes(laravel)
    check("laravel: reads get and post", [r.method for r in routes],
          ["GET", "POST", "PUT", "PATCH"])
    check("laravel: ignores commented route",
          any(r.path == "/commented" for r in routes), False)

    express = ctx("server/routes/auth.routes.ts", """import { Router } from 'express';
const router = Router();
router.post('/auth/login', login);
router.get('/auth/me', me);
""")
    check("express: route file recognised", is_route_file(express), True)
    check("express: extracts two routes", len(extract_routes(express)), 2)


def test_client_is_not_a_server():
    """A React page calling an API is not declaring one.

    This was the first draft's worst bug: `api.post('/auth/login')` matched the
    same pattern as `router.post('/auth/login')`, so every call site became a
    duplicate declaration and a clean repo produced 95 findings.
    """
    client = ctx("client/src/pages/LoginPage.tsx", """import axios from 'axios';
const api = axios.create({ baseURL: '/api' });
export const login = () => api.post('/auth/login', body);
""")
    check("client: not a route file", is_route_file(client), False)
    check("client: no routes extracted", extract_routes(client), [])

    hook = ctx("client/src/hooks/useAdminMaster.ts", """import axios from 'axios';
export function useAdminMaster() { return api.get('/admin/kelompok'); }
""")
    check("client hook: not a route file", is_route_file(hook), False)


def test_mount_context_and_duplicates():
    """Same path string twice is only a duplicate under the same prefix."""
    grouped = ctx("routes/web.php", """<?php
Route::domain('{subdomain}.example.com')->group(function () {
    Route::get('/', [PublicPageController::class, 'show']);
});
Route::get('/', [LandingController::class, 'index']);
""")
    check("laravel: domain-grouped '/' is not a duplicate", run_api(grouped), [])

    naive = ctx("routes/web.php", """<?php
Route::get('/health', [HealthController::class, 'index']);
Route::get('/health', [HealthController::class, 'index']);
""")
    found = run_api(naive)
    check("laravel: real duplicate reported",
          [f.rule for f in found], ["API-07"])

    # Two separate Express routers mounted at unknown bases: a duplicate here
    # cannot be proven, so it must not be reported.
    a = ctx("server/routes/user.routes.ts",
            "import { Router } from 'express';\nconst router = Router();\nrouter.get('/me', h);\n")
    b = ctx("server/routes/profile.routes.ts",
            "import { Router } from 'express';\nconst router = Router();\nrouter.get('/me', h);\n")
    check("express: same path in two routers is not a duplicate", run_api(a, b), [])

    same = ctx("server/routes/dupe.routes.ts",
               "import { Router } from 'express';\nconst router = Router();\n"
               "router.get('/me', a);\nrouter.get('/me', b);\n")
    check("express: duplicate within one router reported",
          [f.rule for f in run_api(same)], ["API-07"])


def test_error_with_success_status():
    bad = ctx("server/controllers/user.controller.ts",
              "export const x = (req, res) => {\n  if (!ok) return res.status(200).json({ error: 'no' });\n};\n")
    check("api-02: 200 with error field reported",
          [f.rule for f in run_api(bad)], ["API-02"])

    fine_null = ctx("server/controllers/a.controller.ts",
                    "export const x = (req, res) => res.status(200).json({ error: null });\n")
    check("api-02: `error: null` is not a failure", run_api(fine_null), [])

    fine_msg = ctx("server/controllers/b.controller.ts",
                   "export const x = (req, res) => res.status(200).json({ message: 'error occurred' });\n")
    check("api-02: the word error in a message is not a payload", run_api(fine_msg), [])

    laravel = ctx("app/Http/Controllers/Api/Foo.php", """<?php
return response()->json(['error' => 'nope'], 200);
""")
    check("api-02: laravel json error with 200 reported",
          [f.rule for f in run_api(laravel)], ["API-02"])

    proper = ctx("app/Http/Controllers/Api/Bar.php", """<?php
return response()->json(['error' => 'nope'], 422);
""")
    check("api-02: the same payload with 422 is correct", run_api(proper), [])


def test_style_consistency():
    check("style: kebab", segment_style("reset-password"), "kebab-case")
    check("style: snake", segment_style("reset_password"), "snake_case")
    check("style: camel", segment_style("resetPassword"), "camelCase")
    check("style: single word carries no signal", segment_style("users"), None)
    check("style: parameter carries no signal", segment_style("{id}"), None)

    mixed = ctx("routes/web.php", """<?php
Route::get('/reset-password', [A::class, 'a']);
Route::get('/reset_password', [A::class, 'b']);
""")
    check("api-01: two styles reported",
          [f.rule for f in run_api(mixed)], ["API-01"])

    consistent = ctx("routes/web.php", """<?php
Route::get('/reset-password', [A::class, 'a']);
Route::get('/change-password', [A::class, 'b']);
Route::get('/users', [A::class, 'c']);
""")
    check("api-01: one style is silent", run_api(consistent), [])


def test_path_normalisation():
    check("norm: laravel param", norm_path('/users/{id}'), '/users/{}')
    check("norm: express param", norm_path('/users/:id'), '/users/{}')
    check("norm: fastapi typed param", norm_path('/users/<int:id>'), '/users/{}')
    check("norm: trailing slash", norm_path('/users/'), '/users')
    check("norm: root stays root", norm_path('/'), '/')


def test_disabled_rule_stays_disabled():
    """`off` in config must silence a domain rule like any other."""
    import tempfile
    from ironclad_core.config import load_config
    from ironclad_core.engine import run

    with tempfile.TemporaryDirectory() as d:
        Path(d, "web.php").write_text(
            "<?php\nRoute::get('/a', [A::class, 'a']);\nRoute::get('/a', [A::class, 'b']);\n")
        cfg, src = load_config(None, None, [d],
                               preset_dir=ROOT / "skills" / "ironclad" / "assets" / "presets")
        cfg["rules"]["API-07"] = "off"
        result = run(load_all(), cfg, [d], source=src)
        check("config: API-07 off silences it",
              [f.rule for f in result.findings], [])

        cfg["rules"]["API-07"] = "warn"
        result = run(load_all(), cfg, [d], source=src)
        check("config: API-07 warn reports as warn not error",
              [(f.rule, f.severity) for f in result.findings], [("API-07", "warn")])
        check("config: a demoted rule does not fail the build",
              result.exit_code, 0)


def main() -> int:
    print("API domain tests\n")
    for fn in (test_route_extraction, test_client_is_not_a_server,
               test_mount_context_and_duplicates, test_error_with_success_status,
               test_style_consistency, test_path_normalisation,
               test_disabled_rule_stays_disabled):
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
