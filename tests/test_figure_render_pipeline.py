from __future__ import annotations

import numpy as np
import sympy as sp

from gu_toolkit import Figure


def test_queued_param_change_render_updates_trace_data_on_flush() -> None:
    x, a = sp.symbols("x a")
    fig = Figure(sampling_points=30)
    pref = fig.parameter(a, value=2.0)
    plot = fig.plot(a * x, x, id="line")

    before = plot.y_data.copy()
    pref.value = 3.0

    # Default param-triggered renders are queued and coalesced until flushed.
    assert np.array_equal(plot.y_data, before)

    fig.flush_render_queue()
    after = plot.y_data

    assert len(after) == 30
    assert (after != before).any()


def test_force_render_flushes_pending_param_change_immediately() -> None:
    x, a = sp.symbols("x a")
    fig = Figure(sampling_points=16)
    pref = fig.parameter(a, value=1.0)
    plot = fig.plot(a * x, x, id="line")

    pref.value = 4.0
    fig.render(reason="manual", force=True)

    assert np.allclose(plot.y_data, plot.x_data * 4.0)
