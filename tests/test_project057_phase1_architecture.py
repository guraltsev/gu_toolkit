from __future__ import annotations

import sys
from dataclasses import dataclass
from unittest.mock import patch

import sympy as sp

from gu_toolkit import Figure
from gu_toolkit._widget_stubs import widgets
from gu_toolkit.figure_layout import FigureLayout
from gu_toolkit.figure_legend import LegendPanelManager
from gu_toolkit.figure_parameters import ParameterManager


class _RecordingParameterLayout:
    def __init__(self) -> None:
        self.controls: list[object] = []

    def _mount_parameter_control(self, control: object) -> None:
        self.controls.append(control)


class _RecordingLegendLayout:
    def __init__(self) -> None:
        self.root_classes: list[str] = []
        self.body_classes: list[str] = []
        self.overlays: list[widgets.Widget] = []
        self.toolbar_children: tuple[widgets.Widget, ...] = ()
        self._body_children_state: tuple[widgets.Widget, ...] = ()
        self._legend_has_toolbar_host = False

    @property
    def _legend_body_children(self) -> tuple[widgets.Widget, ...]:
        return self._body_children_state

    def _add_legend_body_class(self, class_name: str) -> None:
        self.body_classes.append(class_name)

    def _add_root_classes(self, *class_names: str) -> None:
        self.root_classes.extend(class_names)

    def _attach_overlay_children(self, *children: widgets.Widget) -> None:
        self.overlays.extend(children)

    def _set_legend_toolbar_children(self, children: tuple[widgets.Widget, ...]) -> None:
        self.toolbar_children = tuple(children)

    def _set_legend_body_children(self, children: tuple[widgets.Widget, ...]) -> None:
        self._body_children_state = tuple(children)


@dataclass
class _FakePlot:
    id: str
    label: str
    visible: object
    views: tuple[str, ...]
    color: str | None = None


def test_parameter_manager_can_bind_controls_through_layout_manager() -> None:
    a = sp.symbols("a")
    layout = _RecordingParameterLayout()
    manager = ParameterManager(lambda *_: None, layout_manager=layout)

    ref = manager.parameter(a, value=1.0, min=-2.0, max=2.0, step=0.5)

    assert layout.controls == [ref.widget]
    assert manager.widgets() == [ref.widget]


def test_legend_manager_can_refresh_through_layout_manager() -> None:
    layout = _RecordingLegendLayout()
    manager = LegendPanelManager(layout_manager=layout)
    manager.set_active_view("main")

    manager.on_plot_added(_FakePlot(id="p1", label="sin(x)", visible=True, views=("main",)))

    assert "gu-figure-legend-area" in layout.body_classes
    assert any(name.startswith("gu-figure-context-root-") for name in layout.root_classes)
    assert "gu-figure-context-governed" in layout.root_classes
    assert len(layout.overlays) == 3
    assert len(layout._legend_body_children) == 1


def test_figure_layout_keeps_view_selection_state_without_extra_navigation_classes() -> None:
    layout = FigureLayout()
    layout.ensure_view_page("main", "Main")
    layout.ensure_view_page("alt", "Alt")

    seen: list[str] = []
    layout.observe_view_selection(seen.append)

    assert tuple(layout.view_selector.options) == (("Main", "main"), ("Alt", "alt"))
    assert layout.view_selector.layout.display == "flex"
    assert layout._active_view_id == "main"

    layout.view_selector.value = "alt"

    assert layout._active_view_id == "alt"
    assert seen[-1] == "alt"
    assert layout._view_pages["main"].host_box.layout.display == "none"
    assert layout._view_pages["alt"].host_box.layout.display == "flex"


def test_figure_show_routes_display_through_layout_manager() -> None:
    fig = Figure()
    token = object()
    calls: list[widgets.Widget] = []
    module = sys.modules[Figure.__module__]

    def _materialize() -> object:
        calls.append(fig._layout.root_widget)
        return token

    with patch.object(fig._layout, "_materialize_display_output", side_effect=_materialize):
        with patch.object(module, "display") as mocked_display:
            fig.show()

    assert calls == [fig._layout.root_widget]
    mocked_display.assert_called_once_with(token)


def test_figure_layout_records_stable_section_widgets_for_future_mounting() -> None:
    layout = FigureLayout()
    widgets_by_name = layout._section_widgets

    assert widgets_by_name["shell"] is layout.root_widget
    assert widgets_by_name["title"] is layout._titlebar
    assert widgets_by_name["navigation"] is layout.view_selector
    assert widgets_by_name["stage"] is layout.view_stage
    assert widgets_by_name["legend"] is layout.legend_panel.panel
    assert widgets_by_name["parameters"] is layout.params_panel.panel
    assert widgets_by_name["info"] is layout.info_panel.panel
    assert widgets_by_name["output"] is layout.print_panel
