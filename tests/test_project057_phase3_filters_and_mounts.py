from __future__ import annotations

from dataclasses import dataclass

import ipywidgets as widgets
import sympy as sp

from gu_toolkit import Figure
from gu_toolkit.figure_info import InfoPanelManager
from gu_toolkit.figure_legend import LegendModel
from gu_toolkit.figure_parameters import ParameterManager


@dataclass
class _FakePlot:
    id: str
    label: str
    visible: object
    views: tuple[str, ...]


def test_parameter_manager_can_exist_without_layout_and_drive_filtered_panel() -> None:
    a, b = sp.symbols("a b")
    manager = ParameterManager(lambda *_: None)

    ref_a = manager.parameter(a)
    ref_b = manager.parameter(b)

    assert manager.list_parameters() == ("a", "b")
    assert manager.get_value("a") == ref_a.value

    seen: list[set[str]] = []
    unsubscribe = manager.subscribe(lambda changed: seen.append(set(changed)))
    manager.set_value("a", 2.0)
    panel = manager.create_panel(parameter_filter=("b",))

    assert panel.root_widget.children == (ref_b.widget,)
    assert seen and "a" in seen[-1]

    unsubscribe()


def test_legend_model_filters_global_plots_without_widget_surface() -> None:
    model = LegendModel(plot_filter=lambda plot: "main" in plot.views)
    main_plot = _FakePlot(id="main", label="Main", visible=True, views=("main",))
    alt_plot = _FakePlot(id="alt", label="Alt", visible=True, views=("alt",))

    model.on_plot_added(main_plot.id, main_plot)
    model.on_plot_added(alt_plot.id, alt_plot)

    visible_ids = [plot_id for plot_id, _plot in model.visible_plots()]
    assert visible_ids == ["main"]


def test_figure_exposes_plot_widget_queries_and_filtered_presentations() -> None:
    x, a, b = sp.symbols("x a b")
    fig = Figure()
    fig.add_view("alt")

    fig.plot(a * sp.sin(x), x, id="main_plot", label="Main", view="main")
    fig.plot(b * sp.cos(x), x, id="alt_plot", label="Alt", view="alt")

    main_widget = fig.views["main"].pane.widget
    alt_widget = fig.views["alt"].pane.widget

    assert [plot.id for plot in fig.plots_for_plot_widget(main_widget)] == ["main_plot"]
    assert [plot.id for plot in fig.plots_for_plot_widget(alt_widget)] == ["alt_plot"]
    assert fig.parameters_for_plot_widget(main_widget) == ("a",)
    assert fig.parameters_for_plot_widget(alt_widget) == ("b",)

    main_legend = fig.create_legend_panel(plot_widget=main_widget, register=True)
    alt_legend = fig.create_legend_panel(plot_widget=alt_widget, register=True)
    assert [row.children[1].value for row in main_legend._body_children()] == ["Main"]
    assert [row.children[1].value for row in alt_legend._body_children()] == ["Alt"]

    assert fig._layout.params_box.children == (fig.parameters["a"].widget,)
    fig.set_active_view("alt")
    assert fig._layout.params_box.children == (fig.parameters["b"].widget,)


def test_info_manager_supports_multiple_independent_roots() -> None:
    default_box = widgets.VBox()
    secondary_box = widgets.VBox()
    manager = InfoPanelManager(default_box)

    default_out = manager.get_output("default")
    secondary_out = manager.get_output("secondary", group="details", root_widget=secondary_box)

    assert default_out in default_box.children
    assert secondary_out in secondary_box.children
    assert secondary_out not in default_box.children
    assert manager.default_group_has_info is True
    assert manager.group_has_info("details") is True

    tertiary_box = widgets.VBox()
    manager.set_simple_card("hello", id="card", group="tertiary", root_widget=tertiary_box)
    assert manager.group_widget("tertiary") is tertiary_box
    assert manager._outputs["card"] in tertiary_box.children
