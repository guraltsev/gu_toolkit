from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from gu_toolkit import Figure  # noqa: E402


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
    plot = fig.plot(x, a * x, parameters=[a], id="ax")

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
    plot = fig.plot(x, a * x + b, parameters=[a, b], id="line")

    frozen = plot.numeric_expression.freeze({a: 2.0, b: 3.0})
    y = np.asarray(frozen(np.array([1.0, 2.0])))
    assert np.allclose(y, np.array([5.0, 7.0]))


def test_symbolic_expression_returns_sympy_expr() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    plot = fig.plot(x, a * x, parameters=[a], id="sx")
    assert plot.symbolic_expression == a * x


def main() -> None:
    tests = [
        test_snapshot_order_and_values,
        test_snapshot_entry_immutability,
        test_numeric_expression_live_provider_binding,
        test_numeric_expression_can_be_frozen_manually,
        test_symbolic_expression_returns_sympy_expr,
    ]
    for test in tests:
        test()
    print(f"OK: {len(tests)} tests passed")


if __name__ == "__main__":
    main()
