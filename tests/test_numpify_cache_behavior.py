from __future__ import annotations

import sympy as sp
from importlib import import_module

numpify_module = import_module("gu_toolkit.numpify")


def test_numpify_uses_cache_by_default() -> None:
    x = sp.Symbol("x")
    numpify_module.numpify_cached.cache_clear()

    f1 = numpify_module.numpify(x + 1, vars=x)
    f2 = numpify_module.numpify(x + 1, vars=x)

    assert f1 is f2


def test_numpify_cache_false_forces_recompile() -> None:
    x = sp.Symbol("x")
    numpify_module.numpify_cached.cache_clear()

    f1 = numpify_module.numpify(x + 1, vars=x, cache=False)
    f2 = numpify_module.numpify(x + 1, vars=x, cache=False)

    assert f1 is not f2
