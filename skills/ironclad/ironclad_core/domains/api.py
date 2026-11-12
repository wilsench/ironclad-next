"""The API domain: does this project answer the same way in every place?

The database domain asks "is status stored one way". This asks the same question
about the HTTP surface, which is where a codebase usually disagrees with itself
long before anyone writes it down.

Three rules ship. Four were dropped on purpose — see the note at the bottom,
because a rule that guesses is worse than a rule that is absent.

Extraction is regex, not AST, and that is a deliberate trade: the shapes we look
for (`Route::get('/x'`, `router.post('/x'`, `@app.get("/x")`) are declarations,
not expressions. A router built from a variable (`router[verb](path)`) is
invisible to us, and the rules stay silent rather than pretending it passed.

Two things this file learned by running on real repositories (Laravel 180 files,
Express/TS 471 files) and being wrong:

1. A client is not a server. `api.post('/auth/login')` in a React page matched
   the same pattern as `router.post('/auth/login')`, so every call site looked
   like a duplicate declaration. Files are now classified before extraction.
2. `Route::domain('{sub}.x')->group(...)` and `Route::prefix('dasbor')` mean
   the same path string is two different endpoints. Comparing raw strings
   reported correct Laravel code as broken. Group context is tracked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .. import Finding, Position, RuleMeta
from ..engine import FileContext, ProjectRule, Registry, Rule

DOMAIN = "api"

# Extensions a route declaration can plausibly live in. `.tsx`/`.jsx` are absent
# on purpose: React components call APIs, they do not declare them.
API_EXTS = (".php", ".js", ".mjs", ".cjs", ".ts", ".py")

# Directories whose files never declare server routes.
_CLIENT_DIRS = {"client", "public", "assets", "static", "frontend", "web",
                "components", "pages", "hooks", "services", "store", "views"}

_I_AM_CLIENT = re.compile(
    r"""^\s*import\s+.*\bfrom\s+['"]axios['"]|"""
    r"""\brequire\(\s*['"]axios['"]\s*\)|"""
    r"""\baxios\s*\.\s*create\s*\(|"""
    r"""^\s*import\s+.*\bfrom\s+['"]@tanstack/react-query['"]""",
    re.M)

_I_AM_ROUTER = re.compile(
    r"""\bexpress\s*\.\s*Router\s*\(|"""
    r"""\bRouter\s*\(\s*\)|"""
    r"""\bnew\s+Router\s*\(|"""
    r"""\bfastify\s*\.\s*register\s*\(|"""
    r"""\bcreateRouter\s*\(|"""
    r"""^\s*from\s+fastapi\s+import|"""
    r"""^\s*import\s+.*\bflask\b""",
    re.M)

_NOT_ROUTES = re.compile(
    r"(?:^|/)(?:test|tests|spec|specs|__tests__|__mocks__|fixtures|examples?|"
    r"node_modules|vendor|dist[^/]*|build|coverage)/", re.I)
_NOT_ROUTES_NAME = re.compile(r"\.(?:test|spec|stories|d)\.[jt]sx?$", re.I)


def is_route_file(ctx: FileContext) -> bool:
    """Does this file declare server routes, or merely talk to them?

    Cheap to be wrong in the safe direction here: a file we skip costs us a
    finding, a file we wrongly include costs the user a hundred.
    """
    if ctx.path.suffix not in API_EXTS:
        return False
    where = str(ctx.path)
    if _NOT_ROUTES.search(where) or _NOT_ROUTES_NAME.search(ctx.path.name):
        return False
    if _CLIENT_DIRS & set(p.lower() for p in ctx.path.parts[:-1]):
        return False

    if ctx.path.suffix == ".php":
        return "Route::" in ctx.text
    if ctx.path.suffix == ".py":
        return bool(re.search(r"@\w+\.(?:get|post|put|patch|delete)\s*\(", ctx.text))

    # JavaScript/TypeScript. A routes/ directory is a strong hint, the router
    # construction is proof; an axios import is proof of the opposite.
    if _I_AM_CLIENT.search(ctx.text):
        return False
    if _I_AM_ROUTER.search(ctx.text):
        return True
    return bool(re.search(r"(?:^|/)(?:routes?|routers?)/", where.lower())) and \
        bool(re.search(r"\b(?:router|app)\s*\.\s*(?:get|post|put|patch|delete)\s*\(", ctx.text))


# A file that shapes a response, without declaring a route: a Laravel controller,
# a FastAPI endpoint module, an Express handler. Still server-side code.
_PY_RESPONSE = re.compile(
    r"\bJSONResponse\b|\bHTTPException\b|\bstatus_code\s*=|\bJsonResponse\b|"
    r"\bResponse\s*\(|\bHTTPStatus\b")
_JS_RESPONSE = re.compile(
    r"\bres\s*\.\s*(?:status|json|send|end)\s*\(|"
    r"\bresponse\s*\.\s*(?:status|json|send)\s*\(")
_PHP_RESPONSE = re.compile(
    r"response\s*\(\s*\)\s*->\s*json|->json\s*\(|\bRedirectResponse\b|"
    r"->jsonResponse\s*\(", re.I)


def handles_responses(ctx: FileContext) -> bool:
    """Server-side file that returns HTTP responses, route declaration or not.

    API-02 needs controllers, which never contain `Route::`. It does not need
    React pages or Django models, and the first draft scanned those too: a
    `.status(200)` in an axios interceptor is a call, not a reply.
    """
    if ctx.path.suffix not in API_EXTS:
        return False
    where = str(ctx.path)
    if _NOT_ROUTES.search(where) or _NOT_ROUTES_NAME.search(ctx.path.name):
        return False
    if _CLIENT_DIRS & set(p.lower() for p in ctx.path.parts[:-1]):
        return False
    if _I_AM_CLIENT.search(ctx.text):
        return False

    pattern = {".php": _PHP_RESPONSE, ".py": _PY_RESPONSE}.get(
        ctx.path.suffix, _JS_RESPONSE)
    return bool(pattern.search(ctx.text)) or is_route_file(ctx)


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    file: str
    line: int
    framework: str
    context: str = ""       # mount context: Laravel prefix/domain, empty elsewhere

    @property
    def normalized(self) -> str:
        """Same path, whatever parameter syntax the framework uses.

        `{id}`, `:id`, `<int:id>` and `<id>` are one route. Comparing raw strings
        would report every FastAPI/Express/Laravel pair as different.
        """
        return norm_path(self.path)

    @property
    def identity(self) -> tuple[str, str, str, str]:
        """What must match for two declarations to collide.

        PHP routers are registered globally at boot, so a duplicate anywhere in
        the project is real. A JS `router` object is mounted by its importer,
        which we cannot see, so we only compare within one file — a rule that
        shouts about `/health` in two routers mounted at different bases is a
        rule people switch off.
        """
        scope = "global" if self.framework == "laravel" else self.file
        return (self.method, self.context, scope, self.normalized)


_PARAM = re.compile(r"\{[^}]*\}|<[^>]*>|:[A-Za-z_][A-Za-z0-9_]*")


def norm_path(path: str) -> str:
    p = _PARAM.sub("{}", path.split("?")[0].split("#")[0])
    if len(p) > 1:
        p = p.rstrip("/")
    return p or "/"


# --------------------------------------------------------------- extraction
_LARAVEL = re.compile(
    r"\bRoute::(get|post|put|patch|delete|options|any)\s*\(\s*['\"]([^'\"]+)['\"]", re.I)
_LARAVEL_MATCH = re.compile(
    r"\bRoute::match\s*\(\s*\[([^\]]*)\]\s*,\s*['\"]([^'\"]+)['\"]", re.I)

# Express / Fastify / Koa / FastAPI. `app`/`router` must be a bare receiver:
# `axios.get` and `$http.get` are calls TO an API, not declarations OF one.
_JS = re.compile(
    r"(?<![\w$.])(?:app|router|server|route|apiRouter)\s*\.\s*"
    r"(get|post|put|patch|delete|options|all)\s*\(\s*['\"`]([^'\"`]+)['\"`]", re.I)


def _comment_start(line: str) -> bool:
    return line.lstrip().startswith(("//", "#", "*", "/*"))


def laravel_contexts(lines: list[str]) -> list[str]:
    """Mount context in force on each line, from `Route::prefix()`/`domain()`.

    Laravel registers every route into one global table, so the same string can
    legitimately appear twice under different prefixes. Without this, correct
    code (`Route::get('/')` on two domains) reads as a duplicate.
    """
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    pending = None
    depth = 0
    for line in lines:
        out.append("|".join(label for _, label in stack))
        if not _comment_start(line):
            m = re.search(r"Route::prefix\s*\(\s*['\"]([^'\"]*)", line)
            if m:
                pending = (pending or "") + "/" + m.group(1).strip("/")
            m = re.search(r"Route::domain\s*\(\s*(?:['\"]([^'\"]*)['\"]|([^)]*))", line)
            if m:
                pending = (pending or "") + "@" + (m.group(1) or m.group(2) or "").strip()
            if "->group(" in line and pending:
                stack.append((depth + 1, pending))
                pending = None
        depth += line.count("{") - line.count("}")
        while stack and depth < stack[-1][0]:
            stack.pop()
    return out


def extract_routes(ctx: FileContext) -> list[Route]:
    """Every route declared in this file. Never raises; unknown shapes are missed."""
    if not is_route_file(ctx):
        return []

    where = str(ctx.path)
    lines = ctx.lines
    contexts = laravel_contexts(lines) if ctx.path.suffix == ".php" else [""] * len(lines)

    out: list[Route] = []
    for i, line in enumerate(lines):
        lineno = i + 1
        if _comment_start(line):
            continue
        ctx_label = contexts[i]

        for m in _LARAVEL.finditer(line):
            out.append(Route(m.group(1).upper(), m.group(2), where, lineno,
                             "laravel", ctx_label))
        for m in _LARAVEL_MATCH.finditer(line):
            for verb in re.findall(r"['\"](\w+)['\"]", m.group(1)) or ["GET"]:
                out.append(Route(verb.upper(), m.group(2), where, lineno,
                                 "laravel", ctx_label))

        if ctx.path.suffix == ".php":
            continue
        for m in _JS.finditer(line):
            verb = m.group(1).upper()
            out.append(Route("ANY" if verb == "ALL" else verb, m.group(2),
                             where, lineno, "js", ctx_label))
    return out


def _routes_of(contexts) -> list[Route]:
    out: list[Route] = []
    for ctx in contexts:
        out.extend(extract_routes(ctx))
    return out


# ------------------------------------------------------------------- styles
_KEBAB = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
_SNAKE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")
_CAMEL = re.compile(r"^[a-z][a-z0-9]*[A-Z][A-Za-z0-9]*$")
_PASCAL = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def segment_style(segment: str) -> str | None:
    """Name the convention one path segment follows, or None if it follows none.

    A bare lowercase word (`users`, `order`) carries no signal — kebab, snake and
    camel all produce it — so returning None there is what keeps this from
    flagging every repo that names a resource with a single word.
    """
    if not segment or segment.startswith(("{", ":", "<", "$", "*")):
        return None
    if _SNAKE.match(segment):
        return "snake_case"
    if _KEBAB.match(segment):
        return "kebab-case"
    if _PASCAL.match(segment):
        return "PascalCase"
    if _CAMEL.match(segment):
        return "camelCase"
    return None


def project_styles(routes) -> dict[str, list[Route]]:
    found: dict[str, list[Route]] = {}
    for r in routes:
        for seg in r.path.split("/"):
            style = segment_style(seg)
            if style:
                found.setdefault(style, []).append(r)
    return found


class Api01RouteNaming(ProjectRule):
    """The project names its endpoint paths two different ways.

    Same shape as DB-08: one finding for the project, because the problem is that
    nobody chose, not that eleven files each chose something. It does not say
    which style is right — a house that writes `/getUser` consistently is not
    this rule's business.
    """
    extensions = API_EXTS
    meta = RuleMeta("API-01", DOMAIN, "endpoint paths named in more than one style",
                    "warn", scope="project")

    def applies_to(self, ctx) -> bool:
        return is_route_file(ctx)

    def check(self, contexts, cfg):
        routes = _routes_of(contexts)
        styles = project_styles(routes)
        if len(styles) < 2:
            return []

        total = sum(len(v) for v in styles.values())
        ordered = sorted(styles.items(), key=lambda kv: -len(kv[1]))
        (main_style, main_hits) = ordered[0]
        (other_style, other_hits) = ordered[1]
        examples = sorted({r.path for r in other_hits})[:3]
        return [Finding(
            rule="API-01", severity="warn", file=other_hits[0].file,
            position=Position(other_hits[0].line), domain=DOMAIN,
            message=(f"endpoint paths use {len(styles)} naming styles: "
                     f"{main_style} ({len(main_hits)} segments) and "
                     f"{other_style} ({len(other_hits)} of {total}) — e.g. "
                     + ", ".join(examples)
                     + " — pick one for the whole project"))]


class Api02ErrorWithSuccessStatus(Rule):
    """A 2xx status returned together with an error payload.

    Not a guess about business meaning: the code says both things at once, and a
    client cannot tell success from failure. Covers `res.status(200).json({error})`
    and Laravel's `response()->json(['error' => ...], 200)`.
    """
    extensions = API_EXTS
    meta = RuleMeta("API-02", DOMAIN, "error payload returned with a success status",
                    "warn")

    def applies(self, ctx) -> bool:
        return handles_responses(ctx)

    # An "error" FIELD, not the word error anywhere: `{ error: null }` and
    # `{ message: 'error occurred' }` are both fine and both fired on the first
    # draft. Laravel's `json(['error' => ...])` is the PHP shape.
    _STATUS = re.compile(r"\.status\(\s*(2\d\d)\s*\)")
    # Match the key, then look at what follows it. A lookahead inside the same
    # pattern was tried first and failed on `{ error: null }` because the regex
    # engine happily started the match one character later, at `rror`.
    _ERROR_KEY = re.compile(r"(?<![\w$])(?:error|errors|err)\s*['\"]?\s*:")
    _EMPTY_VALUE = re.compile(r"^\s*(?:null|false|undefined|''|\"\"|\[\s*\])")
    _LARAVEL = re.compile(r"json\(\s*\[[^\]]*?['\"](?:error|errors|err)['\"]\s*=>",
                          re.I | re.S)
    # Laravel turns the whole array into JSON too, so the status is the argument
    # after the closing bracket — and it may be on a later line.
    _LARAVEL_CODE = re.compile(r"\]\s*,\s*(\d{3})\s*\)")

    def check(self, ctx, cfg):
        out = []
        lines = ctx.lines
        offsets, pos = [], 0
        for line in lines:
            offsets.append(pos)
            pos += len(line) + 1

        for i, line in enumerate(lines, 1):
            if not _comment_start(line):
                m = self._STATUS.search(line)
                if m and self._error_payload(ctx.text[offsets[i - 1]:offsets[i - 1] + 400]):
                    out.append(self._finding(ctx, i, f"HTTP {m.group(1)}"))
                    continue
            if self._LARAVEL.search(line):
                # Look past this line: `json([...], 422)` wraps in real code.
                window = ctx.text[offsets[i - 1]:offsets[i - 1] + 400]
                code = self._LARAVEL_CODE.search(window)
                status = code.group(1) if code else None
                if status is None or status.startswith("2"):
                    out.append(self._finding(
                        ctx, i, f"HTTP {status}" if status else "A 2xx status"))
        return out

    def _error_payload(self, window: str) -> bool:
        """An error key whose value is not empty."""
        for m in self._ERROR_KEY.finditer(window):
            if not self._EMPTY_VALUE.match(window[m.end():m.end() + 24]):
                return True
        return False

    def _finding(self, ctx, line, label):
        return Finding(rule="API-02", severity="warn", file=str(ctx.path),
                       position=Position(line), domain=DOMAIN,
                       message=(f"{label} returned with an error payload; a client "
                                f"cannot tell this from success — use 4xx/5xx"))


class Api07DuplicateRoute(ProjectRule):
    """The same verb and path declared twice in the same mount context.

    Whichever declaration wins is a framework detail; that one of them is dead
    code is not. This is the only API rule whose evidence is two identical
    strings, which is why it is the only one allowed to be an error.
    """
    extensions = API_EXTS
    meta = RuleMeta("API-07", DOMAIN, "the same route is declared twice", "error",
                    scope="project")

    def applies_to(self, ctx) -> bool:
        return is_route_file(ctx)

    def check(self, contexts, cfg):
        seen: dict[tuple, list[Route]] = {}
        for r in _routes_of(contexts):
            if r.method == "ANY":
                continue
            seen.setdefault(r.identity, []).append(r)

        out = []
        for _key, hits in sorted(seen.items(), key=lambda kv: (kv[0][0], kv[0][-1])):
            if len(hits) < 2:
                continue
            files = sorted({f"{h.file}:{h.line}" for h in hits})
            out.append(Finding(
                rule="API-07", severity="error", file=hits[0].file,
                position=Position(hits[0].line), domain=DOMAIN,
                message=(f"{hits[0].method} {hits[0].normalized} is declared "
                         f"{len(hits)} times"
                         + (f" under prefix `{hits[0].context}`" if hits[0].context else "")
                         + f" ({', '.join(files[:3])}); "
                         f"only one of them can ever run")))
        return out


def register(reg: Registry) -> None:
    for rule in (Api01RouteNaming(), Api02ErrorWithSuccessStatus(),
                 Api07DuplicateRoute()):
        reg.add(rule)


# ------------------------------------------------------------------- dropped
# API-03 (uniform response shape) — needs to know what a handler *returns*, which
#   means following expressions across statements. A regex for `res.json({data`
#   would flag every endpoint that returns a bare array and miss every wrapper
#   built by a helper.
# API-04 (versioned API) — a breaking change is a property of git history, not of
#   the working tree. Without history the rule can only demand `/v1`, which is a
#   preference, not a defect.
# API-05 (unvalidated input) — validation often lives in a FormRequest class, a
#   middleware, or a schema file the rule never opens. Laravel repos would light
#   up for code that is correct. Needs handler-level flow analysis.
# API-06 (OpenAPI drift) — comparing spec paths to routes requires resolving
#   mount prefixes across files (`app.use('/api/x', router)`). Built, measured on
#   a real Express repo, and withdrawn: it reported drift that was only a prefix
#   the rule could not see. It returns when discovery can follow the mounts.
