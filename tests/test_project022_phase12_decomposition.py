"""Regression coverage for Project 022 phase 1+2 decomposition."""

from __future__ import annotations

import sympy as sp

from gu_toolkit import Figure, parameter, plot, plot_style_options
from gu_toolkit.figure_plot_normalization import normalize_plot_inputs
from gu_toolkit.numpify import NumericFunction


def test_phase1_module_api_helpers_still_work_from_package_namespace() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()

    with fig:
        parameter(a, min=-1, max=1, value=0.5)
        wave = plot(a * sp.sin(x), x, id="wave")

    assert wave.id == "wave"
    assert wave.parameters == (a,)
    assert "opacity" in plot_style_options()


def test_phase2_normalizer_expression_path_infers_parameters() -> None:
    x, a, b = sp.symbols("x a b")
    plot_var, expr, numeric_fn, params = normalize_plot_inputs(a * x + b, x)

    assert plot_var == x
    assert expr == a * x + b
    assert numeric_fn is None
    assert params == (a, b)


def test_phase2_normalizer_callable_with_vars_mapping() -> None:
    x, a = sp.symbols("x a")

    def f(t, amp):
        return amp * t

    plot_var, expr, numeric_fn, params = normalize_plot_inputs(
        f,
        x,
        vars=(x, {"amp": a}),
        id_hint="wave",
    )

    assert plot_var == x
    assert expr == sp.Symbol("wave")
    assert params == (a,)
    assert isinstance(numeric_fn, NumericFunction)


def test_phase2_normalizer_rejects_ambiguous_callable_variable_without_vars() -> None:
    x = sp.symbols("x")

    def f(a, b):
        return a + b

    try:
        normalize_plot_inputs(f, x)
    except ValueError as exc:
        assert "not present in callable variables" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing vars specification")
