from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable

# Registry state
_DISCOVERED: bool = False
_SETUP_HOOKS: list[Callable[[Any], None]] = []
_EXPORTS: dict[str, Any] = {}


@dataclass(frozen=True)
class PluginInfo:
    name: str
    priority: int
    module: ModuleType


def reset_plugins() -> None:
    """
    Clear plugin registries so the next discover_plugins() re-imports/rescans plugins.
    Note: Python's module cache still exists; if you want a full reload, you can
    additionally delete entries from sys.modules, but that's usually not necessary.
    """
    global _DISCOVERED, _SETUP_HOOKS, _EXPORTS
    _DISCOVERED = False
    _SETUP_HOOKS = []
    _EXPORTS = {}


def _safe_has_module(modname: str) -> bool:
    try:
        importlib.import_module(modname)
        return True
    except Exception:
        return False


def _should_skip_without_import(fullname: str) -> bool:
    """
    True 'avoid import' gate based on module name only:
    - Skip if last component starts with '_' (e.g. _foo.py)
    - Skip if last component ends with '_disabled' (e.g. foo_disabled.py)
    """
    base = fullname.rsplit(".", 1)[-1]
    return base.startswith("_") or base.endswith("_disabled")


def _is_enabled_after_import(mod: ModuleType) -> bool:
    """
    Post-import enable switch:
    - user requested: `_gu__enabled = False`
    Also honor: `__gu_enabled__ = False` (alias).
    """
    if getattr(mod, "_gu__enabled", True) is False:
        return False
    if getattr(mod, "__gu_enabled__", True) is False:
        return False
    return True


def discover_plugins(
    pkg: str = "gu_toolkit.plugins",
    *,
    verbose: bool = False,
) -> None:
    """
    Import all plugin modules under `pkg` and collect exports + setup hooks.

    Conventions per plugin module:
      - Disable without import: filename starts with '_' OR ends with '_disabled.py'
      - Disable after import: _gu__enabled = False
      - Exports:
          __gu_exports__ = ["name1", "name2", ...]   (preferred)
          OR __all__ = [...]
          OR __gu_export_all__ = True (export all public names; escape hatch)
      - Setup hook:
          def _setup(ctx): ...
          OR __gu_setup__ = callable
      - Optional requirements:
          __gu_requires__ = ["plotly", "ipympl", ...]
      - Ordering:
          __gu_priority__ = int (lower runs earlier)
    """
    global _DISCOVERED
    if _DISCOVERED:
        return

    pkg_mod = importlib.import_module(pkg)

    candidates: list[str] = []
    for m in pkgutil.walk_packages(pkg_mod.__path__, pkg_mod.__name__ + "."):
        if m.ispkg:
            continue
        if _should_skip_without_import(m.name):
            if verbose:
                print(f"[gu_toolkit] Skip (no import) {m.name}")
            continue
        candidates.append(m.name)

    plugins: list[PluginInfo] = []

    for fullname in candidates:
        mod = importlib.import_module(fullname)

        if not _is_enabled_after_import(mod):
            if verbose:
                print(f"[gu_toolkit] Skip (disabled) {fullname}")
            continue

        requires = getattr(mod, "__gu_requires__", None)
        if requires:
            missing = [r for r in requires if not _safe_has_module(r)]
            if missing:
                if verbose:
                    print(f"[gu_toolkit] Skip {fullname} (missing: {missing})")
                continue

        prio = int(getattr(mod, "__gu_priority__", 100))
        plugins.append(PluginInfo(name=fullname, priority=prio, module=mod))

    plugins.sort(key=lambda p: (p.priority, p.name))

    for p in plugins:
        mod = p.module

        # Setup hook
        hook = getattr(mod, "__gu_setup__", None) or getattr(mod, "_setup", None)
        if callable(hook):
            _SETUP_HOOKS.append(hook)

        # Export policy
        exports = getattr(mod, "__gu_exports__", None)
        if exports is None:
            exports = getattr(mod, "__all__", None)

        export_all = bool(getattr(mod, "__gu_export_all__", False))

        if exports is not None:
            # Explicit export list
            for name in exports:
                if not isinstance(name, str):
                    raise TypeError(f"{p.name}: export entries must be str, got {type(name)}")
                if not hasattr(mod, name):
                    raise AttributeError(f"{p.name}: exported name '{name}' not found in module")
                _EXPORTS[name] = getattr(mod, name)
        elif export_all:
            # Export all public names (escape hatch)
            for name, val in vars(mod).items():
                if not name.startswith("_"):
                    _EXPORTS[name] = val

        if verbose:
            exp_count = 0
            if exports is not None:
                exp_count = len(exports)
            elif export_all:
                exp_count = len([n for n in vars(mod) if not n.startswith("_")])
            print(f"[gu_toolkit] Loaded {p.name} (exports={exp_count}, hook={callable(hook)})")

    _DISCOVERED = True


def get_exports(*, discover: bool = True) -> dict[str, Any]:
    if discover:
        discover_plugins()
    return dict(_EXPORTS)


def get_setup_hooks(*, discover: bool = True) -> list[Callable[[Any], None]]:
    if discover:
        discover_plugins()
    return list(_SETUP_HOOKS)
