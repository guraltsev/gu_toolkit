from __future__ import annotations

import numpy as np
import pytest
import sympy as sp

from gu_toolkit import Figure


def test_snapshot_order_and_values_are_name_based() -> None:
    a, b, c = sp.symbols("a b c")
    fig = Figure()
    fig.parameter([a, b, c], value=1)

    snap = fig.parameters.snapshot()
    assert list(snap.keys()) == ["a", "b", "c"]
    assert snap[a] == 1
    assert snap["b"] == 1


def test_snapshot_entry_immutability() -> None:
    a = sp.symbols("a")
    fig = Figure()
    fig.parameter(a, min=-2, max=2, step=0.5, value=0)

    snap = fig.parameters.snapshot(full=True)
    entry = dict(snap[a])
    entry["value"] = 99
    assert snap[a]["value"] != 99

    capabilities = snap[a]["capabilities"]
    capabilities.append("mutated")
    assert "mutated" not in snap[a]["capabilities"]


def test_numeric_expression_live_provider_binding() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    fig.parameter(a)
    plot = fig.plot(a * x, x, id="ax")

    fig.parameters[a].value = 2.0
    x_values = np.array([1.0, 2.0, 3.0])
    y_live = np.asarray(plot.numeric_expression(x_values))
    assert np.allclose(y_live, np.array([2.0, 4.0, 6.0]))

    fig.parameters[a].value = 4.0
    y_live_2 = np.asarray(plot.numeric_expression(x_values))
    assert np.allclose(y_live_2, np.array([4.0, 8.0, 12.0]))

    assert fig.parameters.parameter_context["a"] == pytest.approx(4.0)
    assert fig.parameters.parameter_context[a] == pytest.approx(4.0)


def test_numeric_expression_can_be_frozen_manually() -> None:
    x, a, b = sp.symbols("x a b")
    fig = Figure()
    fig.parameter((a, b))
    plot = fig.plot(a * x + b, x, id="line")

    frozen = plot.numeric_expression.freeze({a: 2.0, "b": 3.0})
    y = np.asarray(frozen(np.array([1.0, 2.0])))
    assert np.allclose(y, np.array([5.0, 7.0]))


def test_numeric_expression_unfreeze_without_keys_accepts_full_positional_input() -> None:
    x, a, b = sp.symbols("x a b")
    fig = Figure()
    fig.parameter((a, b))
    plot = fig.plot(a * x + b, x, id="line-live")

    unfrozen = plot.numeric_expression.unfreeze()
    y = np.asarray(unfrozen(np.array([1.0, 2.0]), 4.0, 5.0))
    assert np.allclose(y, np.array([9.0, 13.0]))


def test_symbolic_expression_returns_sympy_expr() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    fig.parameter(a)
    plot = fig.plot(a * x, x, id="sx")
    assert plot.symbolic_expression == a * x


def test_snapshot_value_map_allows_string_and_symbol_lookup() -> None:
    a, b = sp.symbols("a b")
    fig = Figure()
    fig.parameter((a, b), value=1.0)

    values = fig.parameters.snapshot()
    assert values[a] == 1.0
    assert values["b"] == 1.0


def test_snapshot_full_allows_string_and_symbol_lookup() -> None:
    a = sp.symbols("a")
    fig = Figure()
    fig.parameter(a, min=-2, max=2, step=0.5, value=0.75)

    snap = fig.parameters.snapshot(full=True)
    assert snap[a]["value"] == 0.75
    assert snap["a"]["value"] == 0.75


def test_snapshot_string_lookup_unknown_name_has_actionable_error() -> None:
    a = sp.symbols("a")
    fig = Figure()
    fig.parameter(a, value=1.0)

    snap = fig.parameters.snapshot(full=True)
    with pytest.raises(KeyError, match="Unknown parameter name"):
        _ = snap["missing"]


def test_snapshot_same_name_symbols_share_one_name_key() -> None:
    q_real = sp.Symbol("q", real=True)
    q_integer = sp.Symbol("q", integer=True)
    fig = Figure()
    fig.parameter((q_real, q_integer), value=1.0)

    values = fig.parameters.snapshot()
    assert list(values.keys()) == ["q"]
    assert values["q"] == 1.0
    assert values[q_real] == 1.0
    assert values[q_integer] == 1.0

    full = fig.parameters.snapshot(full=True)
    assert full.symbol_for_name("q") == q_real
    assert fig.parameters[q_real] is fig.parameters[q_integer]


def test_snapshot_keys_and_iteration_are_name_based() -> None:
    a, b = sp.symbols("a b")
    fig = Figure()
    fig.parameter((a, b), value=1.0)

    values = fig.parameters.snapshot()
    assert list(values.keys()) == ["a", "b"]
    assert list(values) == ["a", "b"]
    assert values.symbols == (a, b)


def test_same_name_plot_parameters_bind_through_one_logical_name() -> None:
    x = sp.Symbol("x")
    q_real = sp.Symbol("q", real=True)
    q_integer = sp.Symbol("q", integer=True)
    fig = Figure()
    plot = fig.plot(q_real * x + q_integer, x, id="qq")

    assert list(fig.parameters) == ["q"]
    fig.parameters["q"].value = 2.0

    y = np.asarray(plot.numeric_expression(np.array([1.0, 2.0])))
    assert np.allclose(y, np.array([4.0, 6.0]))
