from __future__ import annotations

import math

import numpy as np
import sympy as sp

from gu_toolkit import Figure
from prelude import NIntegrate
from prelude import NReal_Fourier_Series
from prelude import play


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
    fig = Figure()
    fig.parameter([a, b], value=0)
    fig.parameters[a].value = 2.0
    fig.parameters[b].value = 3.0

    with fig:
        result = NIntegrate(a * x + b, (x, 0, 1))

    assert math.isclose(result, 4.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_symbolic_expr_with_smartfigure_binding() -> None:
    x, a, b = sp.symbols("x a b")
    fig = Figure()
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

    unbound = numpify_cached(expr, vars=[x, a, b])
    unbound_result = NIntegrate(unbound, (x, 0, 1), binding={a: 2.0, b: 3.0})
    assert math.isclose(unbound_result, 4.0, rel_tol=1e-10, abs_tol=1e-12)

    bound = unbound.freeze({a: 2.0, b: 3.0})
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
    fig = Figure()
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


def test_nintegrate_sympy_lambda_with_dict_binding() -> None:
    x, a, b = sp.symbols("x a b")
    lam = sp.Lambda((x, a, b), a * x + b)
    result = NIntegrate(lam, (x, 0, 1), binding={a: 2.0, b: 3.0})
    assert math.isclose(result, 4.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_sympy_lambda_uses_current_figure_when_binding_absent() -> None:
    x, a, b = sp.symbols("x a b")
    lam = sp.Lambda((x, a, b), a * x + b)
    fig = Figure()
    fig.parameter([a, b], value=0)
    fig.parameters[a].value = 2.0
    fig.parameters[b].value = 3.0

    with fig:
        result = NIntegrate(lam, (x, 0, 1))

    assert math.isclose(result, 4.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nreal_fourier_series_constant_l2_normalized() -> None:
    x = sp.Symbol("x")
    cos_coeffs, sin_coeffs = NReal_Fourier_Series(1, (x, 0, 2 * sp.pi), samples=4096)

    assert cos_coeffs.shape == sin_coeffs.shape
    assert math.isclose(cos_coeffs[0], math.sqrt(2.0 * math.pi), rel_tol=3e-3, abs_tol=3e-3)
    assert np.all(np.abs(cos_coeffs[1:25]) < 1e-2)
    assert np.all(np.abs(sin_coeffs[:25]) < 1e-2)


def test_nreal_fourier_series_single_mode_matches_expected_component() -> None:
    x = sp.Symbol("x")
    cos_coeffs, sin_coeffs = NReal_Fourier_Series(sp.sin(3 * x), (x, 0, 2 * sp.pi), samples=4096)

    assert math.isclose(sin_coeffs[3], math.sqrt(math.pi), rel_tol=3e-3, abs_tol=3e-3)
    assert np.all(np.abs(cos_coeffs[:10]) < 1e-2)
    near_zero = np.abs(sin_coeffs[:10])
    near_zero[3] = 0.0
    assert np.all(near_zero < 1e-2)


def test_play_returns_non_autoplay_audio_by_default() -> None:
    x = sp.Symbol("x")
    widget = play(sp.sin(2 * sp.pi * 220 * x), (x, 0, 0.01), loop=False)
    data = widget.data
    assert '<audio controls ' in data
    assert 'autoplay' not in data


def test_play_can_enable_autoplay_explicitly() -> None:
    x = sp.Symbol("x")
    widget = play(sp.sin(2 * sp.pi * 220 * x), (x, 0, 0.01), loop=False, autoplay=True)
    assert 'autoplay' in widget.data
