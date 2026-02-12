from __future__ import annotations

import importlib.util
from pathlib import Path

import sympy as sp


def _import_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_numpify_uses_cache_by_default() -> None:
    mod = _import_module_from_path("numpify", Path("numpify.py"))

    x = sp.Symbol("x")
    mod.numpify_cached.cache_clear()

    f1 = mod.numpify(x + 1, args=x)
    f2 = mod.numpify(x + 1, args=x)

    assert f1 is f2


def test_numpify_cache_false_forces_recompile() -> None:
    mod = _import_module_from_path("numpify", Path("numpify.py"))

    x = sp.Symbol("x")
    mod.numpify_cached.cache_clear()

    f1 = mod.numpify(x + 1, args=x, cache=False)
    f2 = mod.numpify(x + 1, args=x, cache=False)

    assert f1 is not f2
