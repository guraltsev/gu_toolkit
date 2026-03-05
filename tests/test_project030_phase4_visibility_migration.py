from __future__ import annotations

import sympy as sp

from gu_toolkit import Figure


def test_phase4_default_mode_disables_plotly_legend() -> None:
    fig = Figure()

    assert fig.figure_widget.layout.showlegend is False


def test_phase4_legend_toggle_uses_boolean_visibility() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.plot(sp.sin(x), x, id="legacy", visible=False, label="legacy")

    row = fig._legend._rows["legacy"]
    assert row.toggle.value is False
    assert fig.plots["legacy"].visible is False

    row.toggle.value = True
    assert fig.plots["legacy"].visible is True
