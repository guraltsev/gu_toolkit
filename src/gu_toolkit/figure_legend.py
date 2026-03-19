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
- Visibility writes use strict boolean semantics (``True``/``False``).

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

import html
from dataclasses import dataclass
from typing import Any

import ipywidgets as widgets
from .figure_color import color_for_trace_index


@dataclass
class LegendRowModel:
    """Widget and state bundle for one legend row bound to a plot id."""

    plot_id: str
    container: widgets.HBox
    toggle: widgets.ToggleButton
    label_widget: widgets.HTMLMath
    style_widget: widgets.HTML
    is_visible_for_active_view: bool = False


class LegendPanelManager:
    """Manage legend sidebar rows and synchronize them with plot lifecycle events."""

    def __init__(self, layout_box: widgets.Box) -> None:
        """Initialize a legend manager bound to the provided layout box."""
        self._layout_box = layout_box
        self._rows: dict[str, LegendRowModel] = {}
        self._plots: dict[str, Any] = {}
        self._ordered_plot_ids: list[str] = []
        self._active_view_id: str | None = None
        self._suspended_plot_ids: set[str] = set()

    @property
    def has_legend(self) -> bool:
        """Return ``True`` when at least one row is visible for the active view."""
        return any(row.is_visible_for_active_view for row in self._rows.values())

    def on_plot_added(self, plot: Any) -> None:
        """Register a plot and create a row if needed."""
        plot_id = self._normalize_plot_id(
            getattr(plot, "id", None), fallback_prefix="plot"
        )
        self._plots[plot_id] = plot
        if plot_id not in self._ordered_plot_ids:
            self._ordered_plot_ids.append(plot_id)
        if plot_id not in self._rows:
            self._rows[plot_id] = self._create_row(plot_id)
        self.refresh(reason="plot_added")

    def on_plot_updated(self, plot: Any) -> None:
        """Refresh row contents for an existing plot or lazily add it."""
        plot_id = self._normalize_plot_id(
            getattr(plot, "id", None), fallback_prefix="plot"
        )
        if plot_id not in self._rows:
            self.on_plot_added(plot)
            return
        self._plots[plot_id] = plot
        self.refresh(reason="plot_updated")

    def on_plot_removed(self, plot_id: str) -> None:
        """Unregister a plot and remove its row from the layout."""
        key = self._normalize_plot_id(plot_id, fallback_prefix="plot")
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
        toggle = widgets.ToggleButton(
            value=False,
            description="",
            tooltip="Toggle plot visibility",
            layout=widgets.Layout(
                width="30px",
                min_width="30px",
                height="30px",
                margin="0",
                padding="0",
            )
        )
        toggle.add_class("gu-legend-toggle")
        label_widget = widgets.HTMLMath(
            value="", layout=widgets.Layout(margin="0", width="100%")
        )
        style_widget = widgets.HTML(
            value=(
                "<style>"
                ".gu-legend-toggle,"
                ".gu-legend-toggle:hover,"
                ".gu-legend-toggle:focus,"
                ".gu-legend-toggle.mod-active,"
                ".gu-legend-toggle.mod-active:hover,"
                ".gu-legend-toggle.mod-active:focus {"
                "background: transparent !important;"
                "background-color: transparent !important;"
                "background-image: none !important;"
                "box-shadow: none !important;"
                "}"
                "</style>"
            ),
            layout=widgets.Layout(display="none", width="0", height="0"),
        )
        container = widgets.HBox(
            [toggle, label_widget, style_widget],
            layout=widgets.Layout(
                width="100%", align_items="center", margin="0", gap="6px"
            ),
        )
        toggle.observe(
            lambda change, pid=plot_id: self._on_toggle_changed(pid, change),
            names="value",
        )
        return LegendRowModel(
            plot_id=plot_id,
            container=container,
            toggle=toggle,
            label_widget=label_widget,
            style_widget=style_widget,
        )

    def _sync_row_widgets(self, *, row: LegendRowModel, plot: Any) -> None:
        """Incrementally update label/toggle to mirror current plot state."""
        label = self._format_label_value(plot=plot, default_plot_id=row.plot_id)
        if row.label_widget.value != label:
            row.label_widget.value = label

        target_value = self._coerce_visible_to_bool(getattr(plot, "visible", True))
        marker_color = self._resolve_plot_color(plot)
        self._style_toggle_marker(
            toggle=row.toggle, is_visible=target_value, marker_color=marker_color
        )
        if row.toggle.value != target_value:
            self._suspended_plot_ids.add(row.plot_id)
            try:
                row.toggle.value = target_value
            finally:
                self._suspended_plot_ids.discard(row.plot_id)

    def _on_toggle_changed(self, plot_id: str, change: dict[str, Any]) -> None:
        """Propagate user checkbox toggles to bound plot visibility."""
        if change.get("name") != "value":
            return
        if plot_id in self._suspended_plot_ids:
            return
        plot = self._plots.get(plot_id)
        if plot is None:
            return
        plot.visible = bool(change.get("new"))
        row = self._rows.get(plot_id)
        if row is None:
            return
        self._style_toggle_marker(
            toggle=row.toggle,
            is_visible=plot.visible is True,
            marker_color=self._resolve_plot_color(plot),
        )

    @staticmethod
    def _style_toggle_marker(
        *, toggle: widgets.ToggleButton, is_visible: bool, marker_color: str
    ) -> None:
        """Render the toggle marker as a color-coded circular legend control."""
        toggle.icon = "circle" if is_visible else "times-circle"
        toggle.button_style = ""
        toggle.style.text_color = marker_color
        toggle.style.button_color = "transparent"
        toggle.layout.border = "none"
        toggle.layout.opacity = "1" if is_visible else "0.6"

    @classmethod
    def _resolve_plot_color(cls, plot: Any) -> str:
        """Return a legend marker color derived from explicit or implicit trace styles.

        Plotly often leaves ``trace.line.color`` unset in Python when color is not
        specified by user code. In that case, the browser assigns a default color
        from the active colorway during rendering. For legend rows we approximate
        that same default using the trace index and colorway so markers do not
        degrade to gray before explicit style is set.
        """
        raw_color = cls._safe_attr_str(plot, "color").strip()
        if raw_color:
            return raw_color

        trace_handle = cls._resolve_reference_trace_handle(plot)
        if trace_handle is not None:
            trace_color = cls._resolve_trace_handle_color(trace_handle)
            if trace_color:
                return trace_color

            inferred = cls._resolve_default_color_from_parent_figure(trace_handle)
            if inferred:
                return inferred
        return "#6c757d"

    @staticmethod
    def _resolve_reference_trace_handle(plot: Any) -> Any:
        """Return a best-effort representative trace handle for ``plot``."""
        getter = getattr(plot, "_reference_trace_handle", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        return None

    @classmethod
    def _resolve_trace_handle_color(cls, trace_handle: Any) -> str:
        """Read explicit color directly from a trace handle when available."""
        line_obj = getattr(trace_handle, "line", None)
        line_color = cls._safe_attr_str(line_obj, "color").strip()
        if line_color:
            return line_color

        marker_obj = getattr(trace_handle, "marker", None)
        marker_color = cls._safe_attr_str(marker_obj, "color").strip()
        if marker_color:
            return marker_color

        return ""

    @classmethod
    def _resolve_default_color_from_parent_figure(cls, trace_handle: Any) -> str:
        """Infer Plotly's default trace color from parent figure order and colorway."""
        parent = getattr(trace_handle, "_parent", None)
        traces = tuple(getattr(parent, "data", ())) if parent is not None else ()
        if not traces:
            return ""

        try:
            trace_index = traces.index(trace_handle)
        except ValueError:
            return ""

        return color_for_trace_index(parent, trace_index, fallback="")

    @staticmethod
    def _coerce_visible_to_bool(value: Any) -> bool:
        """Map mixed visibility states to v1 legend checkbox semantics."""
        return value is True

    @staticmethod
    def _normalize_plot_id(raw_plot_id: Any, *, fallback_prefix: str) -> str:
        """Return a stable plot-id string, even for malformed inputs."""
        try:
            value = "" if raw_plot_id is None else str(raw_plot_id)
        except Exception:
            value = ""
        value = value.strip()
        if value:
            return value
        return f"{fallback_prefix}-{id(raw_plot_id)}"

    @classmethod
    def _format_label_value(cls, *, plot: Any, default_plot_id: str) -> str:
        """Return a safe label string suitable for ``widgets.HTMLMath``.

        Label selection policy for Phase 5:

        1. Use explicit ``plot.label`` when provided and non-empty.
        2. Fall back to ``plot.id``.
        3. Fall back to ``default_plot_id`` if plot attributes are unavailable.

        The selected text is HTML-escaped so plain text and mixed text/math labels
        render safely, while MathJax delimiters (for example ``$...$``) are
        preserved as literal characters.
        """
        raw_label = cls._safe_attr_str(plot, "label")
        if raw_label.strip() != "":
            return html.escape(raw_label)

        raw_plot_id = cls._safe_attr_str(plot, "id")
        if raw_plot_id.strip() != "":
            return html.escape(raw_plot_id)

        return html.escape(default_plot_id)

    @staticmethod
    def _safe_attr_str(plot: Any, attr_name: str) -> str:
        """Best-effort string conversion for plot attributes.

        If attribute access or ``str()`` conversion fails, returns an empty string
        so callers can apply fallback behavior without raising widget refresh
        errors.
        """
        try:
            value = getattr(plot, attr_name, "")
        except Exception:
            return ""

        try:
            return "" if value is None else str(value)
        except Exception:
            return ""
