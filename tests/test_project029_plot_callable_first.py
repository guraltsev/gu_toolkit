from __future__ import annotations

import numpy as np
import sympy as sp

from gu_toolkit import Figure, SymbolFamily, numpify


def test_plot_supports_sympy_expression_callable_first() -> None:
    x = sp.Symbol("x")
    fig = Figure()

    plot = fig.plot(sp.sin(x), x, id="sin")

    assert plot.symbolic_expression == sp.sin(x)
    assert plot.parameters == ()


def test_plot_rejects_var_expr_argument_order() -> None:
    x = sp.Symbol("x")
    fig = Figure()

    try:
        fig.plot(x, sp.sin(x), id="bad_order")
    except TypeError as exc:
        assert "plot variable" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected argument-order rejection")


def test_plot_supports_callable_first_python_callable() -> None:
    x = sp.Symbol("x")
    fig = Figure()

    plot = fig.plot(lambda x: x**2, x, id="sq")

    xs = plot.x_data
    ys = plot.y_data
    assert xs is not None and ys is not None
    assert np.allclose(ys, xs**2)


def test_plot_supports_callable_first_with_range_tuple() -> None:
    x = sp.Symbol("x")
    fig = Figure()

    plot = fig.plot(lambda x: x, (x, -2, 2), id="line")

    assert plot.x_domain == (-2.0, 2.0)


def test_plot_supports_callable_first_multivariable_with_explicit_vars() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()

    plot = fig.plot(lambda x, a: a * x, x, vars=(x, a), id="ax")
    fig.parameters[a].value = 3.0
    plot.render()

    xs = plot.x_data
    ys = plot.y_data
    assert xs is not None and ys is not None
    assert np.allclose(ys, 3.0 * xs)


def test_plot_callable_first_explicit_vars_rebinds_callable_order_to_plot_variable() -> None:
    """Regression test for issue-023 notebook callable/x context mismatch.

    When a callable argument name (e.g. ``t``) differs from the symbol used as
    plot variable (e.g. ``x``), ``plot(..., vars=(x, ...))`` should treat
    ``x`` as the positional sample variable and only mark the remaining symbols
    as dynamic figure parameters.
    """
    x, a = sp.symbols("x a")
    fig = Figure()

    plot = fig.plot(lambda t, a: a * t, x, vars=(x, a), id="ax_rebound")
    fig.parameters[a].value = 4.0
    plot.render()

    xs = plot.x_data
    ys = plot.y_data
    assert xs is not None and ys is not None
    assert np.allclose(ys, 4.0 * xs)


def test_plot_callable_first_multivariable_requires_var_or_vars() -> None:
    fig = Figure()

    try:
        fig.plot(lambda x, y: x + y, None, id="bad")
    except ValueError as exc:
        assert "could not infer plotting variable" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ambiguity error")


def test_plot_supports_numeric_function_first_argument() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    nf = numpify(a * x, vars=(x, a), cache=False)

    plot = fig.plot(nf, x, id="nf")
    fig.parameters[a].value = 2.5
    plot.render()

    xs = plot.x_data
    ys = plot.y_data
    assert xs is not None and ys is not None
    assert np.allclose(ys, 2.5 * xs)


def test_plot_callable_first_single_variable_rebinds_arg_name_without_explicit_vars() -> None:
    """Single-argument callables should rebind to the explicit plotting symbol.

    Regression coverage for issue-023 notebook path where callable arg-name
    differs from the plotting symbol (e.g. ``lambda t: ...`` with ``plot(..., x)``).
    """
    x = sp.Symbol("x")
    fig = Figure()

    plot = fig.plot(lambda t: t**2 + 1, x, id="rebind_single")
    xs = plot.x_data
    ys = plot.y_data

    assert xs is not None and ys is not None
    assert np.allclose(ys, xs**2 + 1)


def test_plot_callable_first_supports_symbolfamily_plot_variable() -> None:
    """Callable-first plotting should work when using ``SymbolFamily`` symbols."""
    x = SymbolFamily("x")
    fig = Figure()

    plot = fig.plot(lambda t: np.exp(-0.15 * t**2) * np.cos(3 * t), x, id="damped")
    xs = plot.x_data
    ys = plot.y_data

    assert xs is not None and ys is not None
    assert np.allclose(ys, np.exp(-0.15 * xs**2) * np.cos(3 * xs))
