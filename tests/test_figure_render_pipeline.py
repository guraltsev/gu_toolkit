from __future__ import annotations

import sympy as sp

from gu_toolkit import Figure


def test_figure_render_pipeline_updates_trace_data() -> None:
    x, a = sp.symbols("x a")
    fig = Figure(sampling_points=30)
    pref = fig.parameter(a, value=2.0)
    plot = fig.plot(a * x, x, parameters=[a], id="line")

    before = plot.y_data.copy()
    pref.value = 3.0
    fig.render(reason="param_change")
    after = plot.y_data

    assert len(after) == 30
    assert (after != before).any()
