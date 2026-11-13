#!/usr/bin/env python3
"""Is there a newer Ironclad? Ask once, in plain words, then get out of the way.

Why this is a separate script and not part of the installer: the installer runs once.
The question "am I behind?" only becomes interesting a month later, when nobody is
running the installer. So the check lives where people already type: `ironclad`.

Design constraints, learned from tools that get muted:

  * Never block. Every network call has a short timeout; failure is silent.
  * Never change an exit code. `check` must mean the same thing whether or not the
    network is up, or CI results start depending on GitHub uptime.
  * Never ask twice a day. One check per 24h, cached in ~/.ironclad/.
  * Never ask in a pipe. No TTY means no human; print the facts and leave.
  * Never nag for long. Option 4 turns it off permanently on that machine.

No dependencies: stdlib only, same as the checker. Python 3.8+.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = "wilsench/ironclad-next"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/skills/ironclad/SKILL.md"
API = f"https://api.github.com/repos/{REPO}"
TTL = 24 * 3600
TIMEOUT = 6.0

STATE_DIR = Path(os.environ.get("IRONCLAD_STATE_DIR") or (Path.home() / ".ironclad"))
STATE = STATE_DIR / "update-check.json"

SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


# ----------------------------------------------------------------------------- text
# The tool is English-first, but "what changed?" is the one message a person reads
# when they are not in the mood to parse English. Two short sets beat one confusing
# one, and `LANG=id_ID.UTF-8` is a cheap, honest signal.
TEXT = {
    "en": {
        "installed": "installed",
        "latest": "latest",
        "up_to_date": "You are on the latest version.",
        "behind": "A newer version is available.",
        "kinds": {
            "fix": "fixes",
            "feat": "new",
            "docs": "docs",
            "test": "tests",
            "ci": "tests",
            "perf": "speed",
            "refactor": "cleanup",
            "chore": "cleanup",
        },
        "kind_note": {
            "fix": "something that was broken now works",
            "feat": "something that did not exist before",
            "docs": "the explanation was wrong or missing",
            "test": "internal checks, nothing you see",
            "speed": "same result, less waiting",
            "cleanup": "internal tidying, nothing you see",
        },
        "what": "What changed since {since}",
        "none": "  (no list could be fetched — the network may be limited)",
        "one": "1 change",
        "many": "{n} changes",
        "menu": "What do you want to do?",
        "opt1": "Install {v} now  (recommended)",
        "opt2": "Stay on {cur} for now  (nothing changes)",
        "opt3": "Show me what changed",
        "opt4": "Stop asking on this machine",
        "choose": "Choose 1-4 [{d}]:",
        "install_run": "Installing {v}…",
        "install_manual": "Run this to install:\n  {cmd}",
        "install_fail": "The installer exited with code {code}. Nothing was changed; you are still on {cur}.",
        "install_ok": "Done. You are on {v}.",
        "stay": "Staying on {cur}.",
        "muted": "Update checks turned off. Turn them back on with: ironclad update",
        "hint": "Ironclad {v} is available (you have {cur}). Run `ironclad update`.",
        "no_tty": "Not a terminal — nothing to ask. To install: {cmd}",
        "bad_state": "Could not read {p}; continuing as if no check had been done.",
        "net": "Could not reach GitHub. Check skipped for now.",
    },
    "id": {
        "installed": "terpasang",
        "latest": "terbaru",
        "up_to_date": "Kamu sudah memakai versi terbaru.",
        "behind": "Ada versi yang lebih baru.",
        "kinds": {
            "fix": "perbaikan",
            "feat": "kemampuan baru",
            "docs": "penjelasan",
            "test": "pemeriksaan",
            "ci": "pemeriksaan",
            "perf": "kecepatan",
            "refactor": "perapian",
            "chore": "perapian",
        },
        "kind_note": {
            "fix": "yang tadinya bermasalah sekarang jalan",
            "feat": "hal yang sebelumnya belum ada",
            "docs": "penjelasan yang salah atau kurang",
            "test": "pemeriksaan internal, tidak terlihat olehmu",
            "speed": "hasil sama, lebih cepat",
            "cleanup": "perapian internal, tidak terlihat olehmu",
        },
        "what": "Apa yang berubah sejak {since}",
        "none": "  (daftar tidak bisa diambil — jaringan mungkin dibatasi)",
        "one": "1 perubahan",
        "many": "{n} perubahan",
        "menu": "Mau bagaimana?",
        "opt1": "Pasang {v} sekarang  (disarankan)",
        "opt2": "Tetap pakai {cur} dulu  (tidak ada yang berubah)",
        "opt3": "Lihat apa saja yang berubah",
        "opt4": "Jangan tanya lagi di mesin ini",
        "choose": "Pilih 1-4 [{d}]:",
        "install_run": "Memasang {v}…",
        "install_manual": "Jalankan ini untuk memasang:\n  {cmd}",
        "install_fail": "Installer keluar dengan kode {code}. Tidak ada yang diubah; kamu masih di {cur}.",
        "install_ok": "Selesai. Sekarang kamu di {v}.",
        "stay": "Tetap di {cur}.",
        "muted": "Pemeriksaan pembaruan dimatikan. Nyalakan lagi dengan: ironclad update",
        "hint": "Ironclad {v} sudah tersedia (punyamu {cur}). Jalankan `ironclad update`.",
        "no_tty": "Bukan terminal — tidak ada yang bisa ditanya. Untuk memasang: {cmd}",
        "bad_state": "Tidak bisa membaca {p}; dianggap belum pernah memeriksa.",
        "net": "Tidak bisa menghubungi GitHub. Pemeriksaan dilewati.",
    },
}


def lang() -> str:
    # LC_ALL wins over LANG; IRONCLAD_LANG is the explicit override (useful when the
    # shell locale says en_US but the reader does not).
    raw = (os.environ.get("IRONCLAD_LANG")
           or os.environ.get("LC_ALL")
           or os.environ.get("LANG")
           or "en").lower()
    return "id" if raw.startswith("id") else "en"


def T(key: str) -> str:
    return TEXT[lang()][key]


def kind_label(kind: str) -> str:
    """Plain word for a conventional-commit prefix, in the reader's language."""
    table = TEXT[lang()]["kinds"]
    note_table = TEXT[lang()]["kind_note"]
    word = table.get(kind, "cleanup")
    return f"{word} — {note_table.get(word, '')}".rstrip(" —")


# -------------------------------------------------------------------------- version
def parse(v: str | None) -> tuple[int, int, int] | None:
    m = SEMVER.match((v or "").strip())
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def is_newer(latest: str | None, current: str | None) -> bool:
    """None-safe comparison: an unparseable version is never "newer"."""
    a, b = parse(latest), parse(current)
    return bool(a and b and a > b)


def installed_version() -> str:
    """Read from SKILL.md, the single source of truth — no second state file."""
    home = Path(os.environ.get("IRONCLAD_HOME") or (Path.home() / ".agents" / "skills" / "ironclad"))
    try:
        for line in (home / "SKILL.md").read_text(encoding="utf-8").splitlines():
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


# --------------------------------------------------------------------------- state
def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(data: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass  # A read-only home is not a reason to fail an update check.


def muted() -> bool:
    return bool(load_state().get("muted"))


# -------------------------------------------------------------------------- network
def get_json(url: str) -> object | None:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "ironclad-update-check",
        **({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
           if os.environ.get("GITHUB_TOKEN") else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        return None


def fetch_latest() -> tuple[str | None, str | None]:
    """Newest released tag. Tags, not `main`: an unreleased commit is not an update.

    Falls back to SKILL.md on main if the API is rate-limited — a rate limit is the
    common case behind a shared office IP, and failing there would make the feature
    look broken exactly for the people who need it.
    """
    data = get_json(f"{API}/tags?per_page=100")
    best: tuple[int, int, int] | None = None
    best_name: str | None = None
    if isinstance(data, list):
        for item in data:
            name = (item or {}).get("name", "")
            pv = parse(name)
            if pv and (best is None or pv > best):
                best, best_name = pv, name
    if best_name:
        return best_name.lstrip("v"), None

    try:
        req = urllib.request.Request(RAW, headers={"User-Agent": "ironclad-update-check"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            for line in r.read().decode("utf-8", "replace").splitlines():
                if line.startswith("version:"):
                    return line.split(":", 1)[1].strip(), None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        pass
    return None, T("net")


def fetch_notes(since: str, latest: str) -> list[dict]:
    """Commits between the installed tag and the newest one.

    `compare` needs both ends to be tags. When the installed version was built from a
    working tree there is no tag to compare against, so the newest tag's own history
    is used — a superset, but honest, and it still answers "what is in this release".
    """
    base = f"v{since}" if parse(since) else None
    data = None
    if base:
        data = get_json(f"{API}/compare/{base}...v{latest}")
    if not isinstance(data, dict) or "commits" not in data:
        data = get_json(f"{API}/commits?per_page=40&sha=v{latest}")
    commits = data.get("commits", []) if isinstance(data, dict) else []
    if not isinstance(commits, list):
        return []

    out = []
    for c in commits:
        msg = ((c.get("commit") or {}).get("message") or "").strip()
        if not msg:
            continue
        subject = msg.splitlines()[0]
        m = re.match(r"^(\w+)(?:\([^)]*\))?!?:\s*(.+)$", subject)
        kind = (m.group(1).lower() if m else "chore")
        text = (m.group(2).strip() if m else subject)
        if kind not in TEXT["en"]["kinds"]:
            kind = "chore"
        out.append({"kind": kind, "text": text})
    return out


# ------------------------------------------------------------------------- printing
def print_notes(notes: list[dict], since: str) -> None:
    print(f"\n{T('what').format(since=since)}:")
    if not notes:
        print(T("none"))
        return
    counts: dict[str, int] = {}
    for n in notes:
        counts[n["kind"]] = counts.get(n["kind"], 0) + 1
    order = ["feat", "fix", "docs", "perf", "test", "ci", "refactor", "chore"]
    parts = []
    for k in order:
        if counts.get(k):
            parts.append(f"{counts[k]} {kind_label(k).split(' — ')[0]}")
    head = T("one") if len(notes) == 1 else T("many").format(n=len(notes))
    print("  " + head + ": " + ", ".join(parts))
    print()
    for n in notes[:12]:
        print(f"  • {n['text']}")
    if len(notes) > 12:
        print(f"  … {len(notes) - 12} more")


def install_cmd(latest: str) -> str:
    override = os.environ.get("IRONCLAD_INSTALL_CMD")
    if override:
        return override
    return f"npx github:{REPO}#v{latest}"


def do_install(latest: str) -> int:
    cmd = install_cmd(latest)
    if os.environ.get("IRONCLAD_INSTALL_CMD"):
        print(T("install_run").format(v=latest))
        return subprocess.call(cmd, shell=True)
    if not shutil.which("npx"):
        print(T("install_manual").format(cmd=cmd))
        return 0
    print(T("install_run").format(v=latest))
    return subprocess.call(["npx", "--yes", f"github:{REPO}#v{latest}"])


# ----------------------------------------------------------------------------- main
def main(argv: list[str]) -> int:
    args = set(argv)
    quiet = "--quiet" in args or "-q" in args
    interactive = "--prompt" in args or (not args & {"--check", "--notes", "--hint", "--install", "--mute"})

    cur = installed_version()
    state = load_state()

    # `--hint` runs at the end of `check`: cached only, no network, stderr, silent
    # unless a newer version is already known. It must never change an exit code.
    if "--hint" in args:
        if muted() or not sys.stderr.isatty():
            return 0
        latest = state.get("latest")
        if is_newer(latest, cur):
            print(T("hint").format(v=latest, cur=cur), file=sys.stderr)
        return 0

    if "--mute" in args:
        state["muted"] = True
        save_state(state)
        print(T("muted"))
        return 0

    force = "--force" in args or not interactive
    fresh = force or (time.time() - float(state.get("checked_at") or 0)) > TTL

    if fresh:
        latest, err = fetch_latest()
        if err:
            if not quiet:
                print(err, file=sys.stderr)
            return 1
        notes = fetch_notes(cur, latest) if latest and is_newer(latest, cur) else []
        state = {"checked_at": time.time(), "latest": latest, "since": cur, "notes": notes,
                 "muted": state.get("muted", False)}
        save_state(state)
    latest = state.get("latest") or cur
    notes = state.get("notes") or []

    newer = is_newer(latest, cur)

    if "--notes" in args:
        print(f"{T('installed')}: {cur}\n{T('latest')}:    {latest}")
        if newer:
            print_notes(notes, cur)
        else:
            print(T("up_to_date"))
        return 0

    if "--install" in args:
        if not newer:
            print(T("up_to_date"))
            return 0
        return do_install(latest)

    if "--check" in args:
        if not quiet:
            print(f"{T('installed')}: {cur}")
            print(f"{T('latest')}:    {latest}")
            print(T("behind") if newer else T("up_to_date"))
        return 10 if newer else 0

    # Interactive: only when a human is actually there.
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(f"{T('installed')}: {cur}\n{T('latest')}:    {latest}")
        print(T("behind") if newer else T("up_to_date"))
        if newer:
            print(T("no_tty").format(cmd=install_cmd(latest)))
        return 0

    print(f"{T('installed')}: {cur}\n{T('latest')}:    {latest}")
    if not newer:
        print(T("up_to_date"))
        return 0
    print(T("behind"))
    print_notes(notes, cur)

    while True:
        print()
        print(T("menu"))
        print(f"  1) {T('opt1').format(v=latest)}")
        print(f"  2) {T('opt2').format(cur=cur)}")
        print(f"  3) {T('opt3')}")
        print(f"  4) {T('opt4')}")
        try:
            ans = input(T("choose").format(d=2)).strip() or "2"
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if ans == "1":
            code = do_install(latest)
            if code != 0:
                print(T("install_fail").format(code=code, cur=cur))
                return 1
            print(T("install_ok").format(v=latest))
            return 0
        if ans == "2":
            print(T("stay").format(cur=cur))
            return 0
        if ans == "3":
            print_notes(notes, cur)
            continue
        if ans == "4":
            state["muted"] = True
            save_state(state)
            print(T("muted"))
            return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
