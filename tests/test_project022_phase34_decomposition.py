"""Regression coverage for Project 022 phase 3+4 decomposition."""

from __future__ import annotations

import sympy as sp

from gu_toolkit import Figure
from gu_toolkit.figure_view_manager import ViewManager


def test_phase3_view_manager_add_switch_remove_and_stale_policy() -> None:
    manager = ViewManager(default_view_id="main")
    manager.add_view("main", title=None, x_range=None, y_range=None, x_label=None, y_label=None)
    manager.add_view("alt", title="Alt", x_range=(-2, 2), y_range=(-1, 1), x_label="x", y_label="y")

    transition = manager.set_active_view(
        "alt",
        current_viewport_x=(-4.0, 4.0),
        current_viewport_y=(-3.0, 3.0),
    )

    assert transition is not None
    current, nxt = transition
    assert current.id == "main"
    assert current.viewport_x_range == (-4.0, 4.0)
    assert nxt.id == "alt"
    assert manager.active_view_id == "alt"

    manager.mark_stale(view_id=None, except_views=("alt",))
    assert manager.views["main"].is_stale is True
    assert manager.views["alt"].is_stale is False

    manager.clear_stale("main")
    assert manager.views["main"].is_stale is False

    manager.set_active_view("main", current_viewport_x=(-2.0, 2.0), current_viewport_y=(-1.0, 1.0))
    manager.remove_view("alt")
    assert "alt" not in manager.views


def test_phase4_figure_uses_explicit_runtime_accessors_and_removes_private_aliases() -> None:
    fig = Figure()

    main_widget = fig.figure_widget_for("main")
    main_pane = fig.pane_for("main")
    assert fig.figure_widget is main_widget
    assert fig.pane is main_pane
    assert not hasattr(fig, "_figure")
    assert not hasattr(fig, "_pane")


def test_phase4_param_change_marks_inactive_view_stale_via_manager() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    fig.add_view("alt")
    fig.plot(a * x, x, id="wave", view=("main", "alt"))
    ref = fig.parameter(a, min=-2, max=2, value=0.0)

    assert fig.views["alt"].is_stale is False
    ref.value = 1.0

    assert fig.views["alt"].is_stale is True
