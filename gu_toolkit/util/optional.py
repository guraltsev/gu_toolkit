from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Optional


def optional_import(module_name: str, *, purpose: str = "", warn: bool = True) -> Optional[ModuleType]:
    """
    Import an optional dependency. If missing, return None and optionally print a helpful message.

    Use this to avoid hard importing heavy/optional modules (e.g., scipy, plotly, ipympl).
    """
    try:
        return import_module(module_name)
    except Exception as e:
        if warn:
            msg = f"[gu_toolkit] Optional dependency '{module_name}' not available"
            if purpose:
                msg += f" (needed for {purpose})"
            msg += f": {e}"
            print(msg)
        return None
