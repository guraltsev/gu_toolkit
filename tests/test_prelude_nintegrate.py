from __future__ import annotations

import math

import numpy as np
import sympy as sp

from gu_toolkit import SmartFigure
from prelude import NIntegrate, NReal_Fourier_Series


def test_nintegrate_finite_interval() -> None:
    x = sp.Symbol("x")
    result = NIntegrate(x**2, (x, 0, 1))
    assert math.isclose(result, 1.0 / 3.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_infinite_interval() -> None:
    x = sp.Symbol("x")
    result = NIntegrate(sp.exp(-x), (x, 0, sp.oo))
    assert math.isclose(result, 1.0, rel_tol=1e-9, abs_tol=1e-11)


def test_nintegrate_symbolic_expr_with_dict_binding() -> None:
    x, a, b = sp.symbols("x a b")
    result = NIntegrate(a * x + b, (x, 0, 1), binding={a: 2.0, b: 3.0})
    assert math.isclose(result, 4.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_symbolic_expr_binding_missing_raises() -> None:
    x, a, b = sp.symbols("x a b")
    try:
        NIntegrate(a * x + b, (x, 0, 1), binding={a: 2.0})
    except ValueError as exc:
        assert "binding is missing values" in str(exc)
        assert "b" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for missing binding")


def test_nintegrate_symbolic_expr_uses_current_figure_when_binding_absent() -> None:
    x, a, b = sp.symbols("x a b")
    fig = SmartFigure()
    fig.parameter([a, b], value=0)
    fig.parameters[a].value = 2.0
    fig.parameters[b].value = 3.0

    with fig:
        result = NIntegrate(a * x + b, (x, 0, 1))

    assert math.isclose(result, 4.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_symbolic_expr_with_smartfigure_binding() -> None:
    x, a, b = sp.symbols("x a b")
    fig = SmartFigure()
    fig.parameter([a, b], value=0)
    fig.parameters[a].value = 2.0
    fig.parameters[b].value = 3.0

    result = NIntegrate(a * x + b, (x, 0, 1), binding=fig)
    assert math.isclose(result, 4.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_plain_callable_ignores_symbol() -> None:
    result = NIntegrate(lambda t: t**2, ("ignored", 0, 1))
    assert math.isclose(result, 1.0 / 3.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_numpified_bound_and_unbound_functions() -> None:
    x, a, b = sp.symbols("x a b")
    expr = a * x + b

    try:
        from gu_toolkit.numpify import numpify_cached
    except ImportError:
        from numpify import numpify_cached

    unbound = numpify_cached(expr, args=[x, a, b])
    unbound_result = NIntegrate(unbound, (x, 0, 1), binding={a: 2.0, b: 3.0})
    assert math.isclose(unbound_result, 4.0, rel_tol=1e-10, abs_tol=1e-12)

    bound = unbound.bind({a: 2.0, b: 3.0})
    bound_result = NIntegrate(bound, (x, 0, 1))
    assert math.isclose(bound_result, 4.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_unbound_callable_with_dict_binding() -> None:
    def linear(x, a, b):
        return a * x + b

    result = NIntegrate(linear, ("ignored", 0, 1), binding={"a": 2.0, "b": 3.0})
    assert math.isclose(result, 4.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_unbound_callable_with_smartfigure_binding() -> None:
    def linear(x, a, b):
        return a * x + b

    a, b = sp.symbols("a b")
    fig = SmartFigure()
    fig.parameter([a, b], value=0)
    fig.parameters[a].value = 2.0
    fig.parameters[b].value = 3.0

    result = NIntegrate(linear, ("ignored", 0, 1), binding=fig)
    assert math.isclose(result, 4.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_unbound_callable_missing_binding_raises() -> None:
    def linear(x, a, b):
        return a * x + b

    try:
        NIntegrate(linear, ("ignored", 0, 1), binding={"a": 2.0})
    except ValueError as exc:
        assert "missing values" in str(exc) or "missing callable parameters" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for missing callable binding")


def test_nreal_fourier_series_symbolic_expr() -> None:
    x = sp.Symbol("x")
    cos_coeffs, sin_coeffs = NReal_Fourier_Series(sp.sin(x) + 2 * sp.cos(2 * x), (x, 0, 2 * sp.pi), samples=4096)

    assert abs(cos_coeffs[0]) < 2e-2
    assert abs(sin_coeffs[0]) < 1e-12
    assert np.isclose(sin_coeffs[1], np.sqrt(np.pi), rtol=2e-2, atol=2e-2)
    assert np.isclose(cos_coeffs[2], 2.0 * np.sqrt(np.pi), rtol=2e-2, atol=2e-2)
    assert abs(cos_coeffs[1]) < 3e-2
    assert abs(sin_coeffs[2]) < 3e-2


def test_nreal_fourier_series_symbolic_expr_with_binding() -> None:
    x, a = sp.symbols("x a")
    cos_coeffs, sin_coeffs = NReal_Fourier_Series(a * sp.sin(x), (x, 0, 2 * sp.pi), samples=4096, binding={a: 3.0})
    assert np.isclose(sin_coeffs[1], 3.0 * np.sqrt(np.pi), rtol=2e-2, atol=2e-2)


def test_nreal_fourier_series_callable_unbound_and_binding() -> None:
    def linear_combo(t, a, b):
        return a * np.sin(t) + b * np.cos(2 * t)

    cos_coeffs, sin_coeffs = NReal_Fourier_Series(
        linear_combo,
        ("ignored", 0, 2 * np.pi),
        samples=4096,
        binding={"a": 2.0, "b": 4.0},
    )
    assert np.isclose(sin_coeffs[1], 2.0 * np.sqrt(np.pi), rtol=2e-2, atol=2e-2)
    assert np.isclose(cos_coeffs[2], 4.0 * np.sqrt(np.pi), rtol=2e-2, atol=2e-2)
