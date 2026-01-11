from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

from gu_toolkit.autoload import (
    discover_plugins,
    get_exports,
    get_setup_hooks,
    reset_plugins,
)


def _get_ipython_shell() -> Optional[Any]:
    try:
        from IPython import get_ipython
        return get_ipython()
    except Exception:
        return None


def _default_target_namespace() -> Optional[Dict[str, Any]]:
    """
    Prefer Jupyter/IPython user namespace, which is *the* notebook global namespace.
    Fallback: caller globals via stack inspection.
    """
    ip = _get_ipython_shell()
    if ip is not None and hasattr(ip, "user_ns") and isinstance(ip.user_ns, dict):
        return ip.user_ns

    # Fallback: caller globals (works in many contexts, but not all)
    try:
        frame = inspect.currentframe()
        if frame and frame.f_back:
            return frame.f_back.f_globals
    except Exception:
        pass

    return None


def enable_matplotlib_widget(*, verbose: bool = True) -> bool:
    """
    Try to enable matplotlib's 'widget' backend (ipympl).
    Safe to call even if IPython/ipympl isn't available.
    """
    ip = _get_ipython_shell()
    if not ip:
        return False

    try:
        ip.run_line_magic("matplotlib", "widget")
        if verbose:
            print("✓ Matplotlib backend set to 'widget'")
        return True
    except Exception:
        try:
            ip.enable_matplotlib("widget")
            if verbose:
                print("✓ Matplotlib backend set to 'widget'")
            return True
        except Exception as e:
            if verbose:
                print(f"⚠ Could not enable Matplotlib widget backend: {e}")
            return False


def _merge_into_namespace(
    target: Dict[str, Any],
    exports: Dict[str, Any],
    *,
    overwrite: bool,
    verbose: bool,
) -> None:
    if overwrite:
        target.update(exports)
        return

    added = 0
    skipped = 0
    for k, v in exports.items():
        if k in target:
            skipped += 1
            continue
        target[k] = v
        added += 1

    if verbose:
        print(f"[gu_toolkit] Injected {added} names; skipped {skipped} existing names (overwrite=False).")


def setup(
    *,
    verbose: bool = True,
    enable_widgets: bool = True,
    export: bool = True,
    overwrite: bool = True,
    namespace: Optional[Dict[str, Any]] = None,
    reload_plugins: bool = False,
) -> None:
    """
    Main entry point.

    - Configures environment (widgets) explicitly.
    - Auto-discovers plugin modules and runs their setup hooks.
    - Optionally injects (SymPy prelude + plugin exports) into the notebook namespace.

    Parameters
    ----------
    export:
        If True, inject exports into `namespace` (or notebook globals by default).
    overwrite:
        If True, exported names overwrite existing variables in the target namespace.
    namespace:
        If provided, inject exports into this dict (most explicit and robust).
        In notebooks, `namespace=globals()` is always acceptable.
    reload_plugins:
        If True, clear the plugin registry and re-discover plugins. Useful if you
        add/edit plugin files and want to reload without restarting the kernel.
    """
    if verbose:
        print("🔧 Initializing GU Toolkit...")

    # 1) Explicit environment configuration (side effects go here, not at import time)
    if enable_widgets:
        enable_matplotlib_widget(verbose=verbose)

    # 2) Discover plugins (optionally reload)
    if reload_plugins:
        reset_plugins()
    discover_plugins(verbose=verbose)

    # 3) Run plugin setup hooks
    ctx = {"verbose": verbose}
    for hook in get_setup_hooks(discover=False):
        try:
            hook(ctx)
        except Exception as e:
            if verbose:
                name = getattr(hook, "__name__", repr(hook))
                print(f"[gu_toolkit] setup hook failed ({name}): {e}")

    # 4) Export into notebook namespace (optional)
    if export:
        target = namespace if namespace is not None else _default_target_namespace()
        if target is None:
            raise RuntimeError(
                "gu_toolkit.setup(export=True) could not determine a target namespace.\n"
                "Fix: call gu_toolkit.setup(namespace=globals()) in the notebook."
            )

        # Prelude exports (SymPy-heavy) + plugin exports
        from gu_toolkit import prelude as _prelude  # imported only when exporting

        prelude_all = list(getattr(_prelude, "__all__", []))
        prelude_exports = {name: getattr(_prelude, name) for name in prelude_all if hasattr(_prelude, name)}

        plugin_exports = get_exports(discover=False)

        # Plugin exports override prelude if collisions occur (lets you replace wrappers)
        combined: Dict[str, Any] = {}
        combined.update(prelude_exports)
        combined.update(plugin_exports)

        _merge_into_namespace(target, combined, overwrite=overwrite, verbose=verbose)

        if verbose:
            print(f"[gu_toolkit] Exported {len(combined)} names into the notebook namespace.")

    if verbose:
        print("🎓 GU Toolkit Ready.")