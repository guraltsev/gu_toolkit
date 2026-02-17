"""Legend side-panel manager for per-view plot visibility controls.

Purpose
-------
This module defines :class:`LegendPanelManager`, a widget-oriented controller
that renders toolkit-managed legend rows into ``FigureLayout.legend_box``.
Each row is stably bound to a plot id and exposes two v1 controls:

- a boolean visibility toggle,
- an ``HTMLMath`` label.

Concepts and structure
----------------------
The manager stores a lightweight row model per plot id, plus deterministic
insertion ordering. ``refresh()`` applies active-view filtering and incremental
widget updates without recreating the full tree on every call.

Architecture notes
------------------
- The manager is intentionally figure-agnostic in Phase 2. It tracks plots via
  lifecycle events (``on_plot_added/updated/removed``) and a local registry.
- Visibility writes use boolean semantics (``True``/``False``) while still
  tolerating legacy plot visibility values such as ``"legendonly"`` during
  migration.

Examples
--------
>>> import ipywidgets as widgets
>>> from gu_toolkit.figure_legend import LegendPanelManager
>>> class _P:  # doctest: +SKIP
...     def __init__(self):
...         self.id, self.label, self.visible, self.views = "p", "sin(x)", True, ("main",)
>>> box = widgets.VBox()  # doctest: +SKIP
>>> mgr = LegendPanelManager(box)  # doctest: +SKIP
>>> p = _P()  # doctest: +SKIP
>>> mgr.on_plot_added(p)  # doctest: +SKIP
>>> mgr.set_active_view("main")  # doctest: +SKIP

Discoverability
---------------
See next:

- ``docs/projects/project-030-dedicated-legend-side-panel/plan.md`` for rollout
  phases and acceptance criteria.
- ``figure_layout.py`` for sidebar composition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import ipywidgets as widgets


@dataclass
class LegendRowModel:
    """Widget and state bundle for one legend row bound to a plot id."""

    plot_id: str
    container: widgets.HBox
    toggle: widgets.Checkbox
    label_widget: widgets.HTMLMath
    is_visible_for_active_view: bool = False


class LegendPanelManager:
    """Manage legend sidebar rows and synchronize them with plot lifecycle events."""

    def __init__(self, layout_box: widgets.Box) -> None:
        """Initialize a legend manager bound to the provided layout box."""
        self._layout_box = layout_box
        self._rows: Dict[str, LegendRowModel] = {}
        self._plots: Dict[str, Any] = {}
        self._ordered_plot_ids: list[str] = []
        self._active_view_id: Optional[str] = None
        self._suspended_plot_ids: set[str] = set()

    @property
    def has_legend(self) -> bool:
        """Return ``True`` when at least one row is visible for the active view."""
        return any(row.is_visible_for_active_view for row in self._rows.values())

    def on_plot_added(self, plot: Any) -> None:
        """Register a plot and create a row if needed."""
        plot_id = str(plot.id)
        self._plots[plot_id] = plot
        if plot_id not in self._ordered_plot_ids:
            self._ordered_plot_ids.append(plot_id)
        if plot_id not in self._rows:
            self._rows[plot_id] = self._create_row(plot_id)
        self.refresh(reason="plot_added")

    def on_plot_updated(self, plot: Any) -> None:
        """Refresh row contents for an existing plot or lazily add it."""
        plot_id = str(plot.id)
        if plot_id not in self._rows:
            self.on_plot_added(plot)
            return
        self._plots[plot_id] = plot
        self.refresh(reason="plot_updated")

    def on_plot_removed(self, plot_id: str) -> None:
        """Unregister a plot and remove its row from the layout."""
        key = str(plot_id)
        self._plots.pop(key, None)
        self._ordered_plot_ids = [pid for pid in self._ordered_plot_ids if pid != key]
        removed = self._rows.pop(key, None)
        if removed is not None:
            removed.toggle.unobserve_all()
        self.refresh(reason="plot_removed")

    def set_active_view(self, view_id: str) -> None:
        """Set the active view used for row filtering."""
        self._active_view_id = str(view_id)
        self.refresh(reason="active_view_changed")

    def refresh(self, reason: str = "") -> None:
        """Synchronize row widgets with latest plot state and active-view filtering."""
        visible_rows: list[widgets.Widget] = []
        for plot_id in self._ordered_plot_ids:
            plot = self._plots.get(plot_id)
            row = self._rows.get(plot_id)
            if plot is None or row is None:
                continue
            visible = self._plot_in_active_view(plot)
            row.is_visible_for_active_view = visible
            self._sync_row_widgets(row=row, plot=plot)
            if visible:
                visible_rows.append(row.container)
        desired_children = tuple(visible_rows)
        if self._layout_box.children != desired_children:
            self._layout_box.children = desired_children

    def _plot_in_active_view(self, plot: Any) -> bool:
        """Return whether ``plot`` belongs to the current active view."""
        if self._active_view_id is None:
            return True
        plot_views = getattr(plot, "views", ())
        return self._active_view_id in tuple(str(view_id) for view_id in plot_views)

    def _create_row(self, plot_id: str) -> LegendRowModel:
        """Create a legend row widget bundle with toggle and label controls."""
        toggle = widgets.Checkbox(
            value=False,
            description="",
            indent=False,
            layout=widgets.Layout(width="28px", min_width="28px", margin="0"),
        )
        label_widget = widgets.HTMLMath(value="", layout=widgets.Layout(margin="0", width="100%"))
        container = widgets.HBox(
            [toggle, label_widget],
            layout=widgets.Layout(width="100%", align_items="center", margin="0", gap="6px"),
        )
        toggle.observe(lambda change, pid=plot_id: self._on_toggle_changed(pid, change), names="value")
        return LegendRowModel(plot_id=plot_id, container=container, toggle=toggle, label_widget=label_widget)

    def _sync_row_widgets(self, *, row: LegendRowModel, plot: Any) -> None:
        """Incrementally update label/toggle to mirror current plot state."""
        label = str(getattr(plot, "label", "") or getattr(plot, "id", row.plot_id))
        if row.label_widget.value != label:
            row.label_widget.value = label

        target_value = self._coerce_visible_to_bool(getattr(plot, "visible", True))
        if row.toggle.value != target_value:
            self._suspended_plot_ids.add(row.plot_id)
            try:
                row.toggle.value = target_value
            finally:
                self._suspended_plot_ids.discard(row.plot_id)

    def _on_toggle_changed(self, plot_id: str, change: Dict[str, Any]) -> None:
        """Propagate user checkbox toggles to bound plot visibility."""
        if change.get("name") != "value":
            return
        if plot_id in self._suspended_plot_ids:
            return
        plot = self._plots.get(plot_id)
        if plot is None:
            return
        plot.visible = bool(change.get("new"))

    @staticmethod
    def _coerce_visible_to_bool(value: Any) -> bool:
        """Map mixed visibility states to v1 legend checkbox semantics."""
        return value is True
