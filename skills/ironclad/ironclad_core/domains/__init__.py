"""Domain registry — a domain is added by existing, not by being listed here.

`load_all` walks this package, imports each module, and calls its `register()`.
The core never names a domain, which is the property that makes adding API or
security a new file instead of an edit to the engine.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from ..engine import Registry


def load_all(only: tuple[str, ...] | None = None) -> Registry:
    reg = Registry()
    for mod in sorted(pkgutil.iter_modules([str(Path(__file__).parent)]), key=lambda m: m.name):
        if mod.name.startswith("_"):
            continue
        if only is not None and mod.name not in only:
            continue
        module = importlib.import_module(f"{__name__}.{mod.name}")
        register = getattr(module, "register", None)
        if callable(register):
            register(reg)
    return reg
