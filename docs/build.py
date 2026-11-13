#!/usr/bin/env python3
"""Build the Ironclad docs site (static, bilingual, no runtime deps).

    python3 docs/build.py

Reads docs/pages/<lang>/*.md (frontmatter + markdown), writes site/:

    site/            Indonesian  → /ironclad-next/
    site/en/         English     → /ironclad-next/en/

Each language gets its own sidebar, TOC, search index and pager, so a reader
never falls into the other language by accident. A switcher in the sidebar and
topbar toggles between the two, remembering the choice.

Dependency: python3-markdown (build time only).
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("build-time dependency missing: pip install markdown (or apt install python3-markdown)")

ROOT = Path(__file__).resolve().parent
PAGES = ROOT / "pages"
ASSETS = ROOT / "assets"
OUT = ROOT.parent / "site"
AVER = ""  # set in main(): version + content hash for cache-busting

def _read_version() -> str:
    """One source of truth: skills/ironclad/SKILL.md.

    This was a hardcoded string that said 0.5.0 while the shipped skill was 0.8.2,
    so the docs confidently advertised a version nobody could install. Reading it
    from the skill means the number cannot drift again — and if it breaks, the build
    should fail loudly rather than print a stale number.
    """
    skill = ROOT.parent / "skills" / "ironclad" / "SKILL.md"
    for line in skill.read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit(f"no version: line in {skill}")


VERSION = _read_version()
DEFAULT_LANG = "id"
# This site is served under /ironclad-next/, not /ironclad/. The latter belongs
# to the published 0.10.2 docs of the original repository and must not be
# overwritten: a release candidate's documentation taking over the stable URL is
# not a deploy, it is a quiet downgrade for everyone reading it.
BASE = "/ironclad-next"
LANGS = ["id", "en"]

# every string the layout needs, per language
STRINGS = {
    "id": {
        "html_lang": "id",
        "tagline": "Aturan engineering tim, ditegakkan mesin.",
        "skip": "Lompat ke isi",
        "search": "Cari dokumentasi",
        "search_aria": "Dokumentasi",
        "search_placeholder": "Cari: install, preset, DB-04, CI…",
        "nav_aria": "Dokumentasi",
        "on_this_page": "Di halaman ini",
        "burger": "Buka menu",
        "search_mini": "Cari",
        "prev": "Sebelumnya",
        "next": "Berikutnya",
        "pager_aria": "Halaman berikutnya",
        "copy": "SALIN",
        "copy_aria": "Salin perintah",
        "hint": "↑ ↓ pilih · ↵ buka · ESC tutup",
        "toc_empty": "Ringkas",
        "lang_label": "Bahasa",
        "other_lang": "English",
    },
    "en": {
        "html_lang": "en",
        "tagline": "Your team's engineering rules, enforced by a machine.",
        "skip": "Skip to content",
        "search": "Search the docs",
        "search_aria": "Documentation",
        "search_placeholder": "Search: install, preset, DB-04, CI…",
        "nav_aria": "Documentation",
        "on_this_page": "On this page",
        "burger": "Open menu",
        "search_mini": "Search",
        "prev": "Previous",
        "next": "Next",
        "pager_aria": "Next page",
        "copy": "COPY",
        "copy_aria": "Copy command",
        "hint": "↑ ↓ select · ↵ open · ESC close",
        "toc_empty": "In short",
        "lang_label": "Language",
        "other_lang": "Indonesia",
    },
}


def lang_prefix(lang: str) -> str:
    return BASE if lang == DEFAULT_LANG else f"{BASE}/{lang}"


def asset_ver() -> str:
    """Cache-bust on content, not on release: a file edited without a version
    bump must still reach the browser, otherwise a deployed fix looks broken."""
    import hashlib
    h = hashlib.sha1()
    for name in ("docs.css", "docs.js"):
        h.update((ASSETS / name).read_bytes())
    return f"{VERSION}-{h.hexdigest()[:8]}"


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5:]
    meta = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta, body


def substitute_version(text: str) -> str:
    """Replace {{VERSION}} with the version read from SKILL.md.

    The pages hardcoded `#v0.10.2` in 71 places. That is a number nobody updates
    until someone notices the install command 404s, and by then it is in a search
    result. Reading it at build time means the docs cannot disagree with the
    package — and `check_version_agreement()` already fails the build when
    SKILL.md and package.json drift.
    """
    return text.replace("{{VERSION}}", VERSION)


def collect(lang):
    pages = []
    folder = PAGES / lang
    if not folder.is_dir():
        return pages
    for path in sorted(folder.glob("*.md")):
        meta, body = split_frontmatter(substitute_version(path.read_text()))
        slug = meta.get("slug") or path.stem
        pages.append({
            "slug": slug,
            "title": meta.get("title", slug),
            "group": meta.get("group", "Docs"),
            "summary": meta.get("summary", ""),
            "order": int(meta.get("order", 99)),
            "body": body,
            "src": path.name,
            "lang": lang,
        })
    pages.sort(key=lambda p: (p["order"], p["title"]))
    return pages


def render_md(text):
    md = markdown.Markdown(extensions=["tables", "fenced_code", "attr_list", "sane_lists", "toc"],
                           extension_configs={"toc": {"permalink": False}})
    html = md.convert(text)
    return html, md.toc_tokens


def add_copy_buttons(html, t):
    """Every <pre> gets a copy button. Assets are static, so this is a plain string insert."""
    label = t["copy"]
    aria = t["copy_aria"]

    def repl(m):
        return ('<div class="codewrap"><button class="copy" type="button" '
                f'aria-label="{aria}">{label}</button>' + m.group(0) + "</div>")
    return re.sub(r"<pre>.*?</pre>", repl, html, flags=re.S)


SEV_RE = re.compile(r"<td>(<strong>)?(error|warn|off)(</strong>)?</td>")


def decorate_tables(html):
    """Wrap tables so they scroll inside themselves, and make severity cells
    readable at a glance instead of relying on the word alone."""
    def sev(m):
        word = m.group(2)
        return f'<td><span class="sev sev-{word}">{word}</span></td>'
    html = SEV_RE.sub(sev, html)
    return html.replace("<table>", '<div class="tablewrap"><table>').replace("</table>", "</table></div>")


LINK_RE = re.compile(r'href="/(?!/|#|http)([^"]*)"')


def fix_links(html, lang):
    """Absolute /slug/ links get the site prefix, plus the language prefix,
    so the build is portable and a link never jumps languages."""
    prefix = lang_prefix(lang)
    return LINK_RE.sub(lambda m: f'href="{prefix}/{m.group(1).lstrip("/")}"', html)


def build_toc(tokens):
    """Flatten the nested token tree: markdown.py nests h2/h3 under h1."""
    out = []

    def walk(nodes):
        for t in nodes:
            if t["level"] in (2, 3):
                out.append((t["level"], t["name"], t["id"]))
            walk(t.get("children") or [])

    walk(tokens)
    return out


def sidebar_html(pages, current, lang, t):
    groups = {}
    for p in pages:
        groups.setdefault(p["group"], []).append(p)
    prefix = lang_prefix(lang)
    parts = []
    for gi, (group, items) in enumerate(groups.items(), 1):
        parts.append(f'<div class="navgroup"><div class="navlabel">'
                     f'<span>{gi:02d}</span>{group}</div><ul>')
        for p in items:
            active = ' class="active" aria-current="page"' if p["slug"] == current else ""
            parts.append(f'<li><a href="{prefix}/{p["slug"]}/"{active}>{p["title"]}</a></li>')
        parts.append("</ul></div>")
    return "\n".join(parts)


LAYOUT = """<!doctype html>
<html lang="{html_lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Ironclad</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="https://wilsench.my.id{path}/">
<link rel="alternate" hreflang="{html_lang}" href="https://wilsench.my.id{path}/">
<link rel="alternate" hreflang="{alt_lang}" href="https://wilsench.my.id{alt_path}/">
<meta name="color-scheme" content="light">
<link rel="stylesheet" href="{BASE}/assets/docs.css?v={ver}">
<script>document.documentElement.classList.add('js')</script>
</head>
<body>

<a class="skip" href="#main">{skip}</a>

<div class="shell">

  <aside class="side" id="side">
    <a class="brand" href="{prefix}/">
      <span class="mark" aria-hidden="true">IC</span>
      <span>
        <b>Ironclad</b>
        <i>v{ver} · MIT</i>
      </span>
    </a>

    <div class="langsw" role="group" aria-label="{lang_label}">
      <a href="{sw_id}/"{on_id}>ID</a>
      <a href="{sw_en}/"{on_en}>EN</a>
    </div>

    <button class="searchbtn" type="button" id="searchbtn">
      <span>{search}</span><kbd>/</kbd>
    </button>

    <nav class="nav" aria-label="{nav_aria}">
      {nav}
    </nav>

    <div class="sidefoot">
      <a href="https://github.com/wilsench/ironclad-next">GitHub</a>
      <a href="https://wilsench.my.id/">wilsench.my.id</a>
    </div>
  </aside>

  <div class="scrim" id="scrim" hidden></div>

  <main id="main">
    <header class="topbar">
      <button class="burger" type="button" id="burger" aria-label="{burger}" aria-expanded="false">
        <span></span><span></span>
      </button>
      <span class="crumb">{group} / <b>{title}</b></span>
      <a class="langsw-mini" href="{alt_path}/" aria-label="{lang_label}">{alt_label}</a>
      <button class="searchmini" type="button" id="searchmini" aria-label="{search_mini}">/<span>{search_mini}</span></button>
    </header>

    <div class="pagegrid">
      <article class="prose">
        {body}
        <nav class="pager" aria-label="{pager_aria}">
          {pager}
        </nav>
        <footer class="docfoot">
          <span>Ironclad v{ver}</span>
          <span>MIT</span>
          <span>Chia Wilsen</span>
        </footer>
      </article>

      <aside class="{tocclass}" aria-label="{on_this_page}">
        <div class="navlabel"><span>§</span>{on_this_page}</div>
        <ul>{toc}</ul>
      </aside>
    </div>
  </main>
</div>

<div class="search" id="search" hidden>
  <div class="searchbox">
    <input id="q" type="search" placeholder="{search_placeholder}" autocomplete="off" spellcheck="false">
    <button id="closeSearch" type="button">ESC</button>
  </div>
  <ul id="results"></ul>
  <p class="hint">{hint}</p>
</div>

<script src="{BASE}/assets/docs.js?v={ver}" defer></script>
<script src="{BASE}/assets/{index_file}?v={ver}" defer></script>
</body>
</html>
"""


def build_lang(lang, pages_all):
    t = STRINGS[lang]
    pages = pages_all[lang]
    if not pages:
        return []

    index = []
    for i, p in enumerate(pages):
        html, tokens = render_md(p["body"])
        html = add_copy_buttons(html, t)
        html = decorate_tables(html)
        html = fix_links(html, lang)

        toc = build_toc(tokens)
        toc_html = "\n".join(
            f'<li class="lvl{lvl}"><a href="#{tid}">{name}</a></li>' for lvl, name, tid in toc
        ) or f'<li class="lvl2"><a href="#main">{t["toc_empty"]}</a></li>'
        toc_class = "toc thin" if len(toc) < 3 else "toc"

        prev_p = pages[i - 1] if i > 0 else None
        next_p = pages[i + 1] if i + 1 < len(pages) else None
        pager = []
        prefix = lang_prefix(lang)
        if prev_p:
            pager.append(f'<a class="prev" href="{prefix}/{prev_p["slug"]}/">'
                         f'<span>{t["prev"]}</span><b>{prev_p["title"]}</b></a>')
        if next_p:
            pager.append(f'<a class="next" href="{prefix}/{next_p["slug"]}/">'
                         f'<span>{t["next"]}</span><b>{next_p["title"]}</b></a>')

        # language switch keeps the reader on the same page when a translation exists
        alt_lang = "en" if lang == "id" else "id"
        alt_slugs = {q["slug"] for q in pages_all[alt_lang]}
        alt_slug = p["slug"] if p["slug"] in alt_slugs else (pages_all[alt_lang][0]["slug"] if pages_all[alt_lang] else "")
        alt_path = f"{lang_prefix(alt_lang)}/{alt_slug}" if alt_slug else lang_prefix(alt_lang)

        path = f"{prefix}/{p['slug']}"
        page_html = LAYOUT.format(
            title=p["title"], desc=p["summary"] or t["tagline"], path=path,
            ver=AVER, nav=sidebar_html(pages, p["slug"], lang, t), group=p["group"], body=html,
            toc=toc_html, pager="\n".join(pager), tocclass=toc_class,
            html_lang=t["html_lang"], alt_lang=STRINGS[alt_lang]["html_lang"], alt_path=alt_path,
            skip=t["skip"], search=t["search"], nav_aria=t["nav_aria"], lang_label=t["lang_label"],
            on_this_page=t["on_this_page"], burger=t["burger"], search_mini=t["search_mini"],
            pager_aria=t["pager_aria"], search_placeholder=t["search_placeholder"], hint=t["hint"],
            prefix=prefix, home_id=BASE, home_en=f"{BASE}/en", BASE=BASE,
            on_id=' class="on" aria-current="true"' if lang == "id" else "",
            on_en=' class="on" aria-current="true"' if lang == "en" else "",
            alt_label="EN" if lang == "id" else "ID",
            # the switch stays on the same page when a translation exists
            sw_id=path if lang == "id" else alt_path,
            sw_en=alt_path if lang == "id" else path,
            index_file="search-index.js" if lang == DEFAULT_LANG else f"search-index.{lang}.js",
        )
        dest = OUT / p["slug"] if lang == DEFAULT_LANG else OUT / lang / p["slug"]
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text(page_html)

        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        index.append({"t": p["title"], "g": p["group"], "u": f"{prefix}/{p['slug']}/",
                      "s": p["summary"], "x": text[:1400]})

    # one search index per language: mixing them gives the reader results they cannot read
    if lang == DEFAULT_LANG:
        out_js = OUT / "assets" / "search-index.js"
        var = "IRONCLAD_INDEX"
    else:
        out_js = OUT / "assets" / f"search-index.{lang}.js"
        var = "IRONCLAD_INDEX"
    out_js.write_text(f"window.{var}=" + json.dumps(index, ensure_ascii=False) + ";\n")

    return pages


def check_version_agreement() -> None:
    """Fail the build when the three places that name a version disagree.

    The docs once said 0.5.0 while the skill was 0.8.2, and nothing complained —
    a bad number is worse than a broken build, because people install it.
    """
    ver = VERSION
    pkg = ROOT.parent / "package.json"
    if pkg.exists():
        import json
        n = json.loads(pkg.read_text(encoding="utf-8")).get("version")
        if n != ver:
            raise SystemExit(
                f"version drift: package.json says {n}, skills/ironclad/SKILL.md says {ver}")
    # Deliberately NOT checking the tag on HEAD here. A release is built before the tag
    # is moved onto the commit, so that check would block every legitimate release.
    # Whether the tag matches what shipped is release-check.sh's job, run after tagging.


def main():
    global AVER
    check_version_agreement()
    AVER = asset_ver()
    pages_all = {lang: collect(lang) for lang in LANGS}
    if not any(pages_all.values()):
        sys.exit("no pages found in docs/pages/<lang>/")

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    shutil.copy(ASSETS / "docs.css", OUT / "assets" / "docs.css")
    shutil.copy(ASSETS / "docs.js", OUT / "assets" / "docs.js")

    for lang in LANGS:
        built = build_lang(lang, pages_all)
        if not built:
            print(f"  ({lang}: no pages, skipped)")
            continue
        print(f"built {len(built)} {lang} pages")
        for p in built:
            print(f"  {lang_prefix(lang)}/{p['slug']}/  {p['title']}")

    # BASE (default language) serves its first page directly; no redirect,
    # because the first page IS the landing. Canonical points at the stable URL.
    first = OUT / pages_all[DEFAULT_LANG][0]["slug"] / "index.html"
    (OUT / "index.html").write_text(first.read_text())

    # BASE/en/ needs the same treatment
    if pages_all["en"]:
        first_en = OUT / "en" / pages_all["en"][0]["slug"] / "index.html"
        (OUT / "en" / "index.html").write_text(first_en.read_text())

    print(f"\nsite → {OUT}")


if __name__ == "__main__":
    main()
