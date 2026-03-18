from __future__ import annotations

import ipywidgets as widgets

from gu_toolkit.PlotlyPane import PlotlyPane, PlotlyPaneStyle, _apply_default_fill_hints
from gu_toolkit.figure_layout import FigureLayout


def test_plotlypane_reflow_delegates_to_driver() -> None:
    pane = PlotlyPane(widgets.Label("x"))
    called: list[dict[str, object]] = []
    pane.driver.reflow = lambda **kwargs: called.append(dict(kwargs))  # type: ignore[method-assign]

    pane.reflow(reason="manual_check", request_id="req-demo", force=True)

    assert called == [
        {
            "reason": "manual_check",
            "request_id": "req-demo",
            "view_id": None,
            "figure_id": None,
            "pane_id": pane.debug_pane_id,
            "force": True,
        }
    ]




def test_plotlypane_sets_default_fill_hints_on_inner_widget() -> None:
    label = widgets.Label("x")

    PlotlyPane(label)

    assert label.layout.width == "100%"
    assert label.layout.height == "100%"
    assert label.layout.min_width == "0"
    assert label.layout.min_height == "0"


def test_apply_default_fill_hints_ignores_non_widget_layout_objects() -> None:
    class FakeGraphLayout:
        def __init__(self) -> None:
            self.width = None
            self.height = None
            self.min_width = None
            self.min_height = None

    class FakePlotlyLikeWidget:
        def __init__(self) -> None:
            self.layout = FakeGraphLayout()

    widget = FakePlotlyLikeWidget()

    _apply_default_fill_hints(widget)

    assert widget.layout.width is None
    assert widget.layout.height is None
    assert widget.layout.min_width is None
    assert widget.layout.min_height is None


def test_plotlypane_layout_snapshot_alias_matches_debug_snapshot() -> None:
    pane = PlotlyPane(widgets.Label("x"))

    assert pane.layout_snapshot() == pane.debug_snapshot()

def test_plotlypane_applies_style_to_wrapper() -> None:
    pane = PlotlyPane(
        widgets.Label("x"), style=PlotlyPaneStyle(padding_px=7, border="1px solid red")
    )
    assert pane.widget.layout.padding == "7px"
    assert pane.widget.layout.border == "1px solid red"


def test_plotlypane_geometry_snapshot_defaults_are_visible_from_python() -> None:
    pane = PlotlyPane(widgets.Label("x"))

    geometry = pane.geometry_snapshot()

    assert geometry.state == "created"
    assert geometry.frontend_ready is False
    assert geometry.measured_width == 0
    assert geometry.measured_height == 0

    debug = pane.debug_snapshot()
    assert debug["geometry_state"] == "created"
    assert debug["geometry_frontend_ready"] is False


def test_figure_layout_trigger_reflow_for_view_uses_bound_callback() -> None:
    layout = FigureLayout()
    calls: list[tuple[str, str]] = []

    layout.bind_view_reflow(lambda view_id, reason: calls.append((view_id, reason)))
    layout.trigger_reflow_for_view("detail")

    assert calls == [("detail", "compatibility_reflow")]
