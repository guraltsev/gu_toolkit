import numpy as np
import sympy as sp

from gu_toolkit.numpify import numpify_cached

__all__ = []


__all__ += ["SupNormCard", "MaxDistanceCard"]


def _metric_card(description, var, expr, reducer):
    """Return a Figure.info-compatible mixed static/dynamic card spec."""
    interval = (-0.5, 0.5)
    xs = np.linspace(interval[0], interval[1], 2000)
    expr = sp.Abs(sp.sympify(expr))
    params = tuple(
        sorted((s for s in expr.free_symbols if s != var), key=lambda s: s.sort_key())
    )
    expr_np = numpify_cached(expr, vars=(var, *params))

    def _value(fig, _ctx):
        missing = [p for p in params if p not in fig.parameters]
        if missing:
            fig.parameter(missing)
        par_vals = [fig.parameters[p].value for p in params]
        values = np.asarray(expr_np(xs, *par_vals), dtype=float)
        metric_value = float(reducer(values))
        return f"<code>{metric_value:g}</code>"

    return [description, _value]


def MaxDistanceCard(var, F, G):
    return SupNormCard(var, F - G)


def SupNormCard(var, F):
    return _metric_card(
        (
            r"The largest distance between the two functions on "
            r"$\left[-\tfrac12,\tfrac12\right]$ is:"
        ),
        var,
        F,
        np.max,
    )


__all__ += ["L1AvgNormCard", "AvgDistanceCard"]


def AvgDistanceCard(var, F, G):
    return L1AvgNormCard(var, F - G)


def L1AvgNormCard(var, F):
    return _metric_card(
        (
            r"The average distance between the two functions on "
            r"$\left[-\tfrac12,\tfrac12\right]$ is:"
        ),
        var,
        F,
        np.mean,
    )
