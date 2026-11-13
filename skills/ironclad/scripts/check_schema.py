#!/usr/bin/env python3
"""Schema convention checker for Ironclad.

This file is the entry point, not the implementation. In Phase 1 the engine
moved to `ironclad_core/` so domains could be registered instead of appended to
one long loop. Everything observable — flags, exit codes, stdout, JSON keys — is
unchanged, and `tests/capture_behaviour.py` proves it against a recorded
baseline of 108 cases.

There is exactly one implementation. An earlier draft kept a frozen copy of the
old code here for repos that had the checker copied in on its own; that is the
same shape as the hand-written install manifest that drifted out of sync with
the payload, so instead the package is what gets copied.

Layouts supported, in order:

  1. `<skill>/ironclad_core/`      — the installed payload
  2. `<repo>/scripts/ironclad_core/` — what `ironclad init` writes for a repo

Rules:
  DB-01 native enum in schema
  DB-02 magic number compared to / assigned on a status-like field
  DB-03 status integer with no FK/CHECK
  DB-04 status stored as text
  DB-05 boolean named for a non-binary concept
  DB-06 money stored as float
  DB-07 timestamp without timezone
  DB-08 status stored more than one way (project-wide)
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_UP = _HERE.parent


def _preset_dir() -> Path:
    """Assets live in one of two places.

    `<skill>/assets/presets` for the installed payload, `<scripts>/presets` for a
    repo that had the checker copied in with `--with-checker`.
    """
    for d in (_HERE / "presets", _UP / "assets" / "presets"):
        if d.is_dir():
            return d
    return _HERE / "presets"


def _load_package():
    """Import ironclad_core from whichever layout is present."""
    for base in (_HERE, _UP):
        if (base / "ironclad_core").is_dir():
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
    try:
        from ironclad_core.cli import main as engine_main
    except ImportError as exc:
        print(f"ironclad: the checker engine is missing ({exc}).", file=sys.stderr)
        print("The install is incomplete — re-run the installer:", file=sys.stderr)
        print("  curl -fsSL https://wilsench.my.id/ironclad/install.sh | bash",
              file=sys.stderr)
        return None
    return engine_main


def _load_module(name: str):
    """Import any callable from ironclad_core with the same layout search."""
    for base in (_HERE, _UP):
        if (base / "ironclad_core").is_dir():
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
    import importlib
    return getattr(importlib.import_module(f"ironclad_core.{name}"), f"{name}_main")


def main(argv=None) -> int:
    engine_main = _load_package()
    if engine_main is None:
        # Exit 3, the documented "the tool itself could not run" code. Not 0:
        # a broken install must never look like a clean repo.
        return 3
    # `--rules` / `--presets` are subcommands of the *checker*, not of the bash
    # wrapper, so a repo that copied the checker in with `--with-checker` can read
    # its rules without the skill installed. Dispatch before argparse, which
    # would otherwise treat the word as a path.
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("rules", "presets", "doctor"):
        verb, rest = argv[0], argv[1:]
        try:
            if verb == "rules":
                return _load_module("rules")(rest, preset_dir=_preset_dir())
            if verb == "doctor":
                return _load_module("doctor")(rest, preset_dir=_preset_dir())
            return engine_main(["--list-presets", *rest], preset_dir=_preset_dir())
        except ImportError as exc:
            print(f"ironclad: {verb} needs a complete install ({exc}).", file=sys.stderr)
            return 3
    return engine_main(argv, preset_dir=_preset_dir())


if __name__ == "__main__":
    sys.exit(main())
