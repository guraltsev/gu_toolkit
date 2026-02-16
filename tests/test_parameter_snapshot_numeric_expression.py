from __future__ import annotations

import numpy as np
import sympy as sp

from gu_toolkit import Figure

def test_snapshot_order_and_values() -> None:
    a, b, c = sp.symbols("a b c")
    fig = Figure()
    fig.parameter([a, b, c], value=1)

    snap = fig.parameters.snapshot()
    assert list(snap.keys()) == [a, b, c]

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

def test_numeric_expression_can_be_frozen_manually() -> None:
    x, a, b = sp.symbols("x a b")
    fig = Figure()
    fig.parameter((a, b))
    plot = fig.plot(a * x + b, x, id="line")

    frozen = plot.numeric_expression.freeze({a: 2.0, b: 3.0})
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
