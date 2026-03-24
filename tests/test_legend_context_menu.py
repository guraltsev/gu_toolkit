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
    thickness: float | None = 2.0
    opacity: float | None = 1.0
    dash: str | None = "solid"


def test_context_bridge_opens_style_dialog_for_existing_plot() -> None:
    legend_box = widgets.VBox()
    root = widgets.VBox()
    manager = LegendPanelManager(legend_box, modal_host=root, root_widget=root)
    manager.set_active_view("main")

    plot = _FakePlot(id="plot 1", label="Plot 1", visible=True, views=("main",))
    manager.on_plot_added(plot)

    manager._handle_context_bridge_message(
        None,
        {
            "type": "legend_context_request",
            "action": "open_style_dialog",
            "plot_id": "plot 1",
        },
        None,
    )

    assert manager._settings_open is True
    assert manager._settings_plot_id == "plot 1"
    assert manager._dialog_modal.layout.display == "flex"
    assert manager._dialog_subject.value == "Plot 1"


def test_dialog_value_changes_update_plot_style_and_row_color() -> None:
    legend_box = widgets.VBox()
    root = widgets.VBox()
    manager = LegendPanelManager(legend_box, modal_host=root, root_widget=root)
    manager.set_active_view("main")

    plot = _FakePlot(id="plot-1", label="Plot 1", visible=True, views=("main",))
    manager.on_plot_added(plot)
    manager._open_style_dialog("plot-1")

    manager._dialog_color.value = "#123456"
    manager._dialog_width.value = 4.5
    manager._dialog_opacity.value = 0.4
    manager._dialog_dash.value = "dashdot"

    row = manager._rows["plot-1"]
    assert plot.color == "#123456"
    assert plot.thickness == 4.5
    assert plot.opacity == 0.4
    assert plot.dash == "dashdot"
    assert row.toggle.style.text_color == "#123456"


def test_legend_row_and_root_are_marked_as_figure_context_governed() -> None:
    legend_box = widgets.VBox()
    root = widgets.VBox()
    manager = LegendPanelManager(legend_box, modal_host=root, root_widget=root)
    manager.set_active_view("main")
    manager.on_plot_added(_FakePlot(id="plot-1", label="Plot 1", visible=True, views=("main",)))

    row = manager._rows["plot-1"]
    assert "gu-figure-context-governed" in row.container._dom_classes
    assert "gu-figure-context-governed" in root._dom_classes
    assert any(cls.startswith("gu-legend-plot-id-") for cls in row.toggle._dom_classes)
