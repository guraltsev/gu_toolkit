from __future__ import annotations

from dataclasses import dataclass

import ipywidgets as widgets

from gu_toolkit.figure_legend import LegendPanelManager, _LegendInteractionBridge


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
    _sound_autonormalization: bool = False

    def autonormalization(self, enabled: bool | None = None) -> bool:
        if enabled is None:
            return self._sound_autonormalization
        self._sound_autonormalization = bool(enabled)
        return self._sound_autonormalization


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


def test_context_bridge_decodes_encoded_plot_id_from_dom_class_payload() -> None:
    legend_box = widgets.VBox()
    root = widgets.VBox()
    manager = LegendPanelManager(legend_box, modal_host=root, root_widget=root)
    manager.set_active_view("main")

    plot = _FakePlot(id="plot 1 / alt", label="Plot 1", visible=True, views=("main",))
    manager.on_plot_added(plot)
    encoded_plot_id = manager._rows[plot.id].css_plot_id

    manager._handle_context_bridge_message(
        None,
        {
            "type": "legend_context_request",
            "action": "open_style_dialog",
            "plot_id": encoded_plot_id,
        },
        None,
    )

    assert manager._settings_open is True
    assert manager._settings_plot_id == plot.id


def test_dialog_changes_apply_only_after_ok_and_refresh_row_color() -> None:
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
    manager._dialog_autonormalization.value = True

    row = manager._rows["plot-1"]
    assert plot.color is None
    assert plot.thickness == 2.0
    assert plot.opacity == 1.0
    assert plot.dash == "solid"

    manager._apply_style_dialog(None)

    assert plot.color == "#123456"
    assert plot.thickness == 4.5
    assert plot.opacity == 0.4
    assert plot.dash == "dashdot"
    assert plot.autonormalization() is True
    assert row.toggle.style.text_color == "#123456"


def test_dialog_escape_request_closes_without_applying_pending_changes() -> None:
    legend_box = widgets.VBox()
    root = widgets.VBox()
    manager = LegendPanelManager(legend_box, modal_host=root, root_widget=root)
    manager.set_active_view("main")

    plot = _FakePlot(id="plot-1", label="Plot 1", visible=True, views=("main",))
    manager.on_plot_added(plot)
    manager._open_style_dialog("plot-1")

    manager._dialog_color.value = "#123456"
    manager._dialog_width.value = 4.5

    manager._context_bridge._emit_msg(
        {"type": "legend_context_request", "action": "close_style_dialog", "reason": "escape"}
    )

    assert manager._settings_open is False
    assert manager._dialog_modal.layout.display == "none"
    assert plot.color is None
    assert plot.thickness == 2.0


def test_dialog_exposes_graphical_color_picker_and_apply_button() -> None:
    manager = LegendPanelManager(widgets.VBox(), modal_host=widgets.VBox(), root_widget=widgets.VBox())

    assert type(manager._dialog_color).__name__ == "ColorPicker"
    assert manager._dialog_color.concise is True
    assert manager._dialog_ok_button.description == "Apply"


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


def test_context_menu_bridge_no_longer_exposes_line_style_entry() -> None:
    assert "open_style_dialog" not in _LegendInteractionBridge._esm
