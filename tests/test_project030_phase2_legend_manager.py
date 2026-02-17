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

    manager.on_plot_added(_FakePlot(id="main_only", label="Main", visible=True, views=("main",)))
    manager.on_plot_added(_FakePlot(id="alt_only", label="Alt", visible=True, views=("alt",)))

    manager.set_active_view("main")
    assert [row.children[1].value for row in box.children] == ["Main"]
    assert manager.has_legend is True

    manager.set_active_view("alt")
    assert [row.children[1].value for row in box.children] == ["Alt"]


def test_toggle_updates_plot_visibility_with_boolean_semantics() -> None:
    box = widgets.VBox()
    manager = LegendPanelManager(box)
    manager.set_active_view("main")

    plot = _FakePlot(id="p1", label="P1", visible="legendonly", views=("main",))
    manager.on_plot_added(plot)
    row = manager._rows["p1"]

    assert row.toggle.value is False

    row.toggle.value = True
    assert plot.visible is True
