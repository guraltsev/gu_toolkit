from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from gu_toolkit import SmartFigure  # noqa: E402
from gu_toolkit.NumericExpression import PlotView  # noqa: E402


def _assert_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type as exc:
        return exc
    except Exception as exc:  # pragma: no cover
        raise AssertionError(f"Expected {exc_type}, got {type(exc)}") from exc
    raise AssertionError(f"Expected {exc_type} to be raised.")


def test_snapshot_order_and_values() -> None:
    a, b, c = sp.symbols("a b c")
    fig = SmartFigure()
    fig.parameter([a, b, c], value=1)

    snap = fig.params.snapshot()
    assert list(snap.keys()) == [a, b, c]
    assert list(snap.values().keys()) == [a, b, c]


def test_snapshot_entry_immutability() -> None:
    a = sp.symbols("a")
    fig = SmartFigure()
    fig.parameter(a, min=-2, max=2, step=0.5, value=0)

    snap = fig.params.snapshot()
    entry = dict(snap[a])
    entry["value"] = 99
    assert snap[a]["value"] != 99

    capabilities = snap[a]["capabilities"]
    capabilities.append("mutated")
    assert "mutated" not in snap[a]["capabilities"]


def test_bind_partial_and_key_validation() -> None:
    x, a, b, extra = sp.symbols("x a b extra")
    fig = SmartFigure()
    plot = fig.plot(x, a * x + b, parameters=[a, b], id="line")
    assert isinstance(plot.numeric_expression, PlotView)

    bound_partial = plot.numeric_expression.bind({a: 2.0})
    y_partial = np.asarray(bound_partial(np.array([1.0, 2.0]), 3.0))
    assert np.allclose(y_partial, np.array([5.0, 7.0]))

    bound = plot.numeric_expression.bind({a: 2.0, b: 3.0, extra: 5.0})
    assert bound.unbind() is plot.numpified

    err = _assert_raises(TypeError, plot.numeric_expression.bind, {"a": 2.0})
    assert "Symbol keys" in str(err)


def test_unbind_requires_bind_before_call() -> None:
    x, a = sp.symbols("x a")
    fig = SmartFigure()
    plot = fig.plot(x, a * x, parameters=[a], id="ax")

    unbound = plot.numeric_expression.unbind()
    y = np.asarray(unbound(np.array([0.0, 1.0]), 2.0))
    assert np.allclose(y, np.array([0.0, 2.0]))


def test_live_vs_snapshot_bound() -> None:
    x, a = sp.symbols("x a")
    fig = SmartFigure()
    plot = fig.plot(x, a * x, parameters=[a], id="ax")

    fig.params[a].value = 2.0
    x_values = np.array([1.0, 2.0, 3.0])
    y_live = np.asarray(plot.numeric_expression(x_values))
    assert np.allclose(y_live, np.array([2.0, 4.0, 6.0]))

    snap = fig.params.snapshot()
    bound = plot.numeric_expression.bind(snap.values())
    fig.params[a].value = 4.0

    y_bound = np.asarray(bound(x_values))
    y_live_2 = np.asarray(plot.numeric_expression(x_values))
    assert np.allclose(y_bound, np.array([2.0, 4.0, 6.0]))
    assert np.allclose(y_live_2, np.array([4.0, 8.0, 12.0]))


def main() -> None:
    tests = [
        test_snapshot_order_and_values,
        test_snapshot_entry_immutability,
        test_bind_partial_and_key_validation,
        test_unbind_requires_bind_before_call,
        test_live_vs_snapshot_bound,
    ]
    for test in tests:
        test()
    print(f"OK: {len(tests)} tests passed")


if __name__ == "__main__":
    main()
