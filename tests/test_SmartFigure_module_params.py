"""
Minimal verification script for module-level params/parameter helpers.

Run (from the repo root):

    python tests/test_SmartFigure_module_params.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from gu_toolkit import SmartFigure, params, parameter  # noqa: E402


def _assert_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as exc:  # pragma: no cover - defensive
        raise AssertionError(f"Expected {exc_type}, got {type(exc)}") from exc
    raise AssertionError(f"Expected {exc_type} to be raised.")


def test_params_proxy_context_access() -> None:
    x, a = sp.symbols("x a")
    fig = SmartFigure()
    with fig:
        param_ref = fig.params.parameter(a)
        assert params[a] is param_ref


def test_params_strict_lookup() -> None:
    a = sp.symbols("a")
    fig = SmartFigure()
    with fig:
        assert a not in params
        _assert_raises(KeyError, lambda: params[a])


def test_parameter_creation_path() -> None:
    a = sp.symbols("a")
    fig = SmartFigure()
    with fig:
        param_ref = parameter(a)
        assert params[a] is param_ref


def test_no_context_behavior() -> None:
    a = sp.symbols("a")
    _assert_raises(RuntimeError, lambda: params[a])
    _assert_raises(RuntimeError, parameter, a)


def test_params_setitem_sugar() -> None:
    a = sp.symbols("a")
    fig = SmartFigure()
    with fig:
        fig.params.parameter(a, value=1)
        params[a] = 7
        assert params[a].value == 7


def main() -> None:
    tests = [
        test_params_proxy_context_access,
        test_params_strict_lookup,
        test_parameter_creation_path,
        test_no_context_behavior,
        test_params_setitem_sugar,
    ]
    for test in tests:
        test()
    print(f"OK: {len(tests)} tests passed")


if __name__ == "__main__":
    main()
