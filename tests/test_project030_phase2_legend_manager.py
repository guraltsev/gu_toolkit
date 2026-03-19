from __future__ import annotations

from dataclasses import dataclass

import ipywidgets as widgets

from gu_toolkit.figure_legend import LegendPanelManager


@dataclass
class _FakePlot:
    id: str
    label: str
    visible: object
    views: tuple[str, ...]
    color: str | None = None


def test_lifecycle_add_update_remove_and_has_legend() -> None:
    box = widgets.VBox()
    manager = LegendPanelManager(box)
    manager.set_active_view("main")

    plot = _FakePlot(id="p1", label="sin(x)", visible=True, views=("main",))
    manager.on_plot_added(plot)

    assert manager.has_legend is True
    assert len(box.children) == 1

    plot.label = "updated"
    plot.visible = False
    manager.on_plot_updated(plot)

    row = manager._rows["p1"]
    assert row.label_widget.value == "updated"
    assert row.toggle.value is False

    manager.on_plot_removed("p1")

    assert manager.has_legend is False
    assert box.children == ()


def test_manager_preserves_deterministic_insertion_order() -> None:
    box = widgets.VBox()
    manager = LegendPanelManager(box)
    manager.set_active_view("main")

    manager.on_plot_added(_FakePlot(id="a", label="A", visible=True, views=("main",)))
    manager.on_plot_added(_FakePlot(id="b", label="B", visible=True, views=("main",)))
    manager.on_plot_added(_FakePlot(id="c", label="C", visible=True, views=("main",)))

    labels = [row.children[1].value for row in box.children]
    assert labels == ["A", "B", "C"]


def test_refresh_is_idempotent_for_widget_children() -> None:
    box = widgets.VBox()
    manager = LegendPanelManager(box)
    manager.set_active_view("main")

    manager.on_plot_added(_FakePlot(id="a", label="A", visible=True, views=("main",)))

    first_children = box.children
    manager.refresh(reason="repeat")
    second_children = box.children

    assert first_children is second_children


def test_active_view_filtering_hides_non_member_plots() -> None:
    box = widgets.VBox()
    manager = LegendPanelManager(box)

    manager.on_plot_added(
        _FakePlot(id="main_only", label="Main", visible=True, views=("main",))
    )
    manager.on_plot_added(
        _FakePlot(id="alt_only", label="Alt", visible=True, views=("alt",))
    )

    manager.set_active_view("main")
    assert [row.children[1].value for row in box.children] == ["Main"]
    assert manager.has_legend is True

    manager.set_active_view("alt")
    assert [row.children[1].value for row in box.children] == ["Alt"]


def test_toggle_updates_plot_visibility_with_boolean_semantics() -> None:
    box = widgets.VBox()
    manager = LegendPanelManager(box)
    manager.set_active_view("main")

    plot = _FakePlot(id="p1", label="P1", visible=False, views=("main",))
    manager.on_plot_added(plot)
    row = manager._rows["p1"]

    assert row.toggle.value is False

    row.toggle.value = True
    assert plot.visible is True


def test_toggle_marker_reflects_plot_color_and_visibility_state() -> None:
    box = widgets.VBox()
    manager = LegendPanelManager(box)
    manager.set_active_view("main")

    plot = _FakePlot(
        id="p1",
        label="P1",
        visible=True,
        views=("main",),
        color="#123456",
    )
    manager.on_plot_added(plot)
    row = manager._rows["p1"]

    assert row.toggle.icon == "circle"
    assert row.toggle.style.text_color == "#123456"
    assert row.toggle.style.button_color == "transparent"
    assert "gu-legend-toggle" in row.toggle._dom_classes
    assert row.toggle.layout.width == "30px"
    assert row.toggle.layout.height == "30px"
    assert row.toggle.layout.opacity == "1"

    row.toggle.value = False

    assert row.toggle.icon == "times-circle"
    assert row.toggle.style.text_color == "#123456"
    assert row.toggle.style.button_color == "transparent"
    assert row.toggle.layout.opacity == "0.6"


def test_toggle_marker_uses_plotly_default_color_when_color_unspecified() -> None:
    import plotly.graph_objects as go

    class _FakePlotWithTrace:
        def __init__(self, plot_id: str, trace: go.Scatter) -> None:
            self.id = plot_id
            self.label = "Default"
            self.visible = True
            self.views = ("main",)
            self.color = None
            self._trace = trace

        def _reference_trace_handle(self) -> go.Scatter:
            return self._trace

    fig = go.Figure()
    fig.update_layout(template=None)
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="first")
    fig.add_scatter(x=[0, 1], y=[1, 2], mode="lines", name="second")

    box = widgets.VBox()
    manager = LegendPanelManager(box)
    manager.set_active_view("main")

    first = _FakePlotWithTrace("p-default-1", fig.data[0])
    second = _FakePlotWithTrace("p-default-2", fig.data[1])

    manager.on_plot_added(first)
    manager.on_plot_added(second)

    assert manager._rows[first.id].toggle.style.text_color == "rgb(31, 119, 180)"
    assert manager._rows[second.id].toggle.style.text_color == "rgb(255, 127, 14)"
