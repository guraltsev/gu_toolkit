"""Regression coverage for Project 022 phase 3+4 decomposition."""

from __future__ import annotations

from types import SimpleNamespace

import sympy as sp

from gu_toolkit import Figure
from gu_toolkit.figure_view_manager import ViewManager


class _ManagedView(SimpleNamespace):
    id: str
    title: str
    x_range: tuple[float, float] | None
    y_range: tuple[float, float] | None
    x_label: str
    y_label: str
    viewport_x_range: tuple[float, float] | None
    viewport_y_range: tuple[float, float] | None
    is_active: bool
    is_stale: bool


def _view(
    view_id: str,
    *,
    title: str | None = None,
    x_range: tuple[float, float] | None = None,
    y_range: tuple[float, float] | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
) -> _ManagedView:
    return _ManagedView(
        id=view_id,
        title=(view_id if title is None else title),
        x_range=x_range,
        y_range=y_range,
        x_label=(x_label or ""),
        y_label=(y_label or ""),
        viewport_x_range=None,
        viewport_y_range=None,
        is_active=False,
        is_stale=False,
    )


def test_phase3_view_manager_register_switch_remove_and_stale_policy() -> None:
    manager = ViewManager(default_view_id="main")
    manager.register_view(_view("main"))
    manager.register_view(
        _view("alt", title="Alt", x_range=(-2, 2), y_range=(-1, 1), x_label="x", y_label="y")
    )

    transition = manager.set_active_view(
        "alt",
        current_viewport_x=(-4.0, 4.0),
        current_viewport_y=(-3.0, 3.0),
    )

    assert transition is not None
    current, nxt = transition
    assert current.id == "main"
    assert current.viewport_x_range == (-4.0, 4.0)
    assert current.viewport_y_range == (-3.0, 3.0)
    assert nxt.id == "alt"
    assert manager.active_view_id == "alt"

    manager.mark_stale(view_id=None, except_views=("alt",))
    assert manager.views["main"].is_stale is True
    assert manager.views["alt"].is_stale is False

    manager.clear_stale("main")
    assert manager.views["main"].is_stale is False

    manager.set_active_view(
        "main",
        current_viewport_x=(-2.0, 2.0),
        current_viewport_y=(-1.0, 1.0),
    )
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
    fig.flush_render_queue()

    assert fig.views["alt"].is_stale is True
