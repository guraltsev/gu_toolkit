from __future__ import annotations

import sympy as sp

from gu_toolkit import Figure


def test_phase4_default_mode_disables_plotly_legend() -> None:
    fig = Figure()

    assert fig.figure_widget.layout.showlegend is False


def test_phase4_compatibility_mode_keeps_plotly_legend_enabled() -> None:
    fig = Figure(plotly_legend_mode="plotly")

    assert fig.figure_widget.layout.showlegend is True


def test_phase4_legend_toggle_migrates_legendonly_to_boolean_visibility() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.plot(sp.sin(x), x, id="legacy", visible="legendonly", label="legacy")

    row = fig._legend._rows["legacy"]
    assert row.toggle.value is False
    assert fig.plots["legacy"].visible == "legendonly"

    row.toggle.value = True
    assert fig.plots["legacy"].visible is True
