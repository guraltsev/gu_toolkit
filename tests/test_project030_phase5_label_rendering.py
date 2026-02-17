from __future__ import annotations

from dataclasses import dataclass

import ipywidgets as widgets

from gu_toolkit.figure_legend import LegendPanelManager


@dataclass
class _FakePlot:
    id: object
    label: object
    visible: object
    views: tuple[str, ...]


class _BadStr:
    def __str__(self) -> str:
        raise RuntimeError("cannot stringify")


def test_phase5_label_prefers_explicit_label_and_escapes_html() -> None:
    box = widgets.VBox()
    manager = LegendPanelManager(box)
    manager.set_active_view("main")

    plot = _FakePlot(
        id="plot_id", label="f(x) <b>unsafe</b>", visible=True, views=("main",)
    )
    manager.on_plot_added(plot)

    row = manager._rows["plot_id"]
    assert row.label_widget.value == "f(x) &lt;b&gt;unsafe&lt;/b&gt;"


def test_phase5_label_falls_back_to_id_when_label_missing() -> None:
    box = widgets.VBox()
    manager = LegendPanelManager(box)
    manager.set_active_view("main")

    plot = _FakePlot(id="fallback-id", label="", visible=True, views=("main",))
    manager.on_plot_added(plot)

    row = manager._rows["fallback-id"]
    assert row.label_widget.value == "fallback-id"


def test_phase5_label_handles_bad_values_without_refresh_errors() -> None:
    box = widgets.VBox()
    manager = LegendPanelManager(box)
    manager.set_active_view("main")

    plot = _FakePlot(id=_BadStr(), label=_BadStr(), visible=True, views=("main",))
    manager.on_plot_added(plot)

    key = next(iter(manager._rows))
    row = manager._rows[key]
    assert row.label_widget.value == key
