from __future__ import annotations

from gu_toolkit.PlotlyPane import PlotlyPane, PlotlyPaneStyle
import ipywidgets as widgets


def test_plotlypane_reflow_delegates_to_driver() -> None:
    pane = PlotlyPane(widgets.Label("x"))
    called = []
    pane.driver.reflow = lambda: called.append(True)

    pane.reflow()

    assert called == [True]


def test_plotlypane_applies_style_to_wrapper() -> None:
    pane = PlotlyPane(widgets.Label("x"), style=PlotlyPaneStyle(padding_px=7, border="1px solid red"))
    assert pane.widget.layout.padding == "7px"
    assert pane.widget.layout.border == "1px solid red"
