from __future__ import annotations

import html
import re
import uuid
from dataclasses import dataclass
from typing import Any

import traitlets

from ._widget_stubs import anywidget, widgets
from .figure_color import color_for_trace_index


_DASH_STYLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Solid", "solid"),
    ("Dot", "dot"),
    ("Dash", "dash"),
    ("Dash-dot", "dashdot"),
    ("Long dash", "longdash"),
    ("Long dash-dot", "longdashdot"),
)


class _LegendContextMenuBridge(anywidget.AnyWidget):
    """Frontend bridge for figure-owned right-click handling.

    The bridge listens for ``contextmenu`` events inside the figure root and
    suppresses Jupyter's default browser menu for figure-governed regions. When
    the right-click lands on a legend marker it sends a Python-side message so
    the legend style dialog can open for the matching plot.
    """

    root_class = traitlets.Unicode("").tag(sync=True)

    _esm = r"""
    function sameClassSet(node, value) {
      const current = node.__guLegendRootClass || "";
      if (current === value) return true;
      node.__guLegendRootClass = value || "";
      return false;
    }

    function parsePlotIdFromClasses(node) {
      if (!(node instanceof HTMLElement)) return "";
      for (const cls of Array.from(node.classList || [])) {
        if (cls.startsWith("gu-legend-plot-id-")) {
          return cls.slice("gu-legend-plot-id-".length);
        }
      }
      return "";
    }

    export default {
      render({ model, el }) {
        el.style.display = "none";

        function rootEl() {
          const rootClass = model.get("root_class") || "";
          return rootClass ? document.querySelector(`.${rootClass}`) : null;
        }

        function detach() {
          const oldRoot = el.__guLegendRoot;
          const oldHandler = el.__guLegendContextHandler;
          if (oldRoot && oldHandler) {
            oldRoot.removeEventListener("contextmenu", oldHandler, true);
          }
          el.__guLegendRoot = null;
          el.__guLegendContextHandler = null;
        }

        function attach() {
          const root = rootEl();
          if (!(root instanceof HTMLElement)) {
            detach();
            return;
          }
          if (el.__guLegendRoot === root) return;
          detach();
          const handler = (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const governed = target.closest(".gu-figure-context-governed");
            if (!(governed instanceof HTMLElement)) return;
            event.preventDefault();
            event.stopPropagation();
            const marker = target.closest(".gu-legend-toggle");
            if (!(marker instanceof HTMLElement)) return;
            const plotId = parsePlotIdFromClasses(marker);
            if (!plotId) return;
            try {
              model.send({
                type: "legend_context_request",
                action: "open_style_dialog",
                plot_id: decodeURIComponent(plotId),
              });
            } catch (e) {}
          };
          root.addEventListener("contextmenu", handler, true);
          el.__guLegendRoot = root;
          el.__guLegendContextHandler = handler;
        }

        function onRootChange() {
          attach();
        }

        model.on("change:root_class", onRootChange);
        attach();

        return () => {
          try { model.off("change:root_class", onRootChange); } catch (e) {}
          detach();
        };
      },
    };
    """


@dataclass
class LegendRowModel:
    """Widget and state bundle for one legend row bound to a plot id."""

    plot_id: str
    container: widgets.HBox
    toggle: widgets.ToggleButton
    label_widget: widgets.HTMLMath
    style_widget: widgets.HTML
    css_plot_id: str
    is_visible_for_active_view: bool = False


class LegendPanelManager:
    """Manage legend sidebar rows and synchronize them with plot lifecycle events."""

    def __init__(
        self,
        layout_box: widgets.Box,
        *,
        modal_host: widgets.Box | None = None,
        root_widget: widgets.Box | None = None,
    ) -> None:
        """Initialize a legend manager bound to the provided layout box."""
        self._layout_box = layout_box
        self._modal_host = modal_host
        self._rows: dict[str, LegendRowModel] = {}
        self._plots: dict[str, Any] = {}
        self._ordered_plot_ids: list[str] = []
        self._active_view_id: str | None = None
        self._suspended_plot_ids: set[str] = set()
        self._settings_open = False
        self._settings_plot_id: str | None = None
        self._suspend_settings_observers = False

        self._root_css_class = f"gu-figure-context-root-{uuid.uuid4().hex[:8]}"
        if root_widget is not None:
            add_class = getattr(root_widget, "add_class", None)
            if callable(add_class):
                add_class(self._root_css_class)
                add_class("gu-figure-context-governed")
        self._context_bridge = _LegendContextMenuBridge(
            root_class=self._root_css_class,
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._context_bridge.on_msg(self._handle_context_bridge_message)

        self._dialog_style = widgets.HTML(
            value=self._dialog_style_html(),
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._dialog_color = widgets.Text(
            value="",
            description="Color:",
            placeholder="#636efa or red",
            continuous_update=False,
            layout=widgets.Layout(width="100%", min_width="0"),
        )
        self._dialog_width = widgets.BoundedFloatText(
            value=2.0,
            min=0.0,
            description="Width:",
            layout=widgets.Layout(width="100%", min_width="0"),
        )
        self._dialog_opacity = widgets.BoundedFloatText(
            value=1.0,
            min=0.0,
            max=1.0,
            description="Opacity:",
            layout=widgets.Layout(width="100%", min_width="0"),
        )
        self._dialog_dash = widgets.Dropdown(
            options=_DASH_STYLE_OPTIONS,
            value="solid",
            description="Style:",
            layout=widgets.Layout(width="100%", min_width="0"),
        )
        self._dialog_close_button = widgets.Button(
            description="Close legend style settings",
            tooltip="Close legend style settings",
            layout=widgets.Layout(width="24px", height="24px", padding="0px"),
        )
        self._dialog_close_button.add_class("smart-slider-icon-button")
        self._dialog_close_button.add_class("smart-slider-close-button")
        self._dialog_close_button.on_click(self._close_style_dialog)
        self._dialog_title_text = widgets.HTML("<b>Legend style</b>")
        self._dialog_subject = widgets.HTMLMath(
            value="",
            layout=widgets.Layout(min_width="0", margin="0px"),
        )
        self._dialog_title = widgets.HBox(
            [self._dialog_title_text, self._dialog_subject],
            layout=widgets.Layout(
                align_items="center",
                gap="4px",
                flex="1 1 auto",
                min_width="0",
                flex_flow="row wrap",
            ),
        )
        self._dialog_title.add_class("smart-slider-settings-title")
        self._dialog_subject.add_class("smart-slider-settings-title-subject")
        self._dialog_title_text.add_class("smart-slider-settings-title-text")
        dialog_header = widgets.HBox(
            [self._dialog_title, self._dialog_close_button],
            layout=widgets.Layout(
                justify_content="space-between",
                align_items="flex-start",
                gap="8px",
                width="100%",
                min_width="0",
            ),
        )
        self._dialog_panel = widgets.VBox(
            [
                dialog_header,
                widgets.HBox([self._dialog_color], layout=widgets.Layout(width="100%", min_width="0")),
                widgets.HBox([self._dialog_width], layout=widgets.Layout(width="100%", min_width="0")),
                widgets.HBox([self._dialog_opacity], layout=widgets.Layout(width="100%", min_width="0")),
                widgets.HBox([self._dialog_dash], layout=widgets.Layout(width="100%", min_width="0")),
            ],
            layout=widgets.Layout(
                width="440px",
                min_width="380px",
                max_width="calc(100vw - 32px)",
                display="none",
                border="1px solid rgba(15, 23, 42, 0.12)",
                padding="12px",
                gap="8px",
                background_color="white",
                opacity="1",
                box_shadow="0 10px 28px rgba(15, 23, 42, 0.28)",
                align_items="stretch",
                overflow_x="hidden",
                overflow_y="auto",
            ),
        )
        self._dialog_panel.add_class("smart-slider-settings-panel")
        self._dialog_modal = widgets.Box(
            [self._dialog_panel],
            layout=widgets.Layout(
                display="none",
                position="fixed",
                top="0",
                left="0",
                width="100vw",
                height="100vh",
                align_items="center",
                justify_content="center",
                background_color="rgba(15, 23, 42, 0.12)",
                z_index="1000",
                overflow_x="hidden",
                overflow_y="hidden",
            ),
        )
        self._dialog_modal.add_class("smart-slider-settings-modal")
        self._dialog_modal.add_class("smart-slider-settings-modal-hosted")

        for control in (
            self._dialog_color,
            self._dialog_width,
            self._dialog_opacity,
            self._dialog_dash,
        ):
            control.observe(self._on_dialog_value_changed, names="value")

        if self._modal_host is not None:
            if self._dialog_style not in self._modal_host.children:
                self._modal_host.children += (self._dialog_style,)
            if self._dialog_modal not in self._modal_host.children:
                self._modal_host.children += (self._dialog_modal,)
        if self._modal_host is not None and self._context_bridge not in self._modal_host.children:
            self._modal_host.children += (self._context_bridge,)

    @property
    def has_legend(self) -> bool:
        """Return ``True`` when at least one row is visible for the active view."""
        return any(row.is_visible_for_active_view for row in self._rows.values())

    def on_plot_added(self, plot: Any) -> None:
        """Register a plot and create a row if needed."""
        plot_id = self._normalize_plot_id(getattr(plot, "id", None), fallback_prefix="plot")
        self._plots[plot_id] = plot
        if plot_id not in self._ordered_plot_ids:
            self._ordered_plot_ids.append(plot_id)
        if plot_id not in self._rows:
            self._rows[plot_id] = self._create_row(plot_id)
        self.refresh(reason="plot_added")

    def on_plot_updated(self, plot: Any) -> None:
        """Refresh row contents for an existing plot or lazily add it."""
        plot_id = self._normalize_plot_id(getattr(plot, "id", None), fallback_prefix="plot")
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
        if self._settings_plot_id == key:
            self._set_style_dialog_open(False)
            self._settings_plot_id = None
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
        self._sync_dialog_from_plot_state()

    def _plot_in_active_view(self, plot: Any) -> bool:
        """Return whether ``plot`` belongs to the current active view."""
        if self._active_view_id is None:
            return True
        plot_views = getattr(plot, "views", ())
        return self._active_view_id in tuple(str(view_id) for view_id in plot_views)

    def _create_row(self, plot_id: str) -> LegendRowModel:
        """Create a legend row widget bundle with toggle and label controls."""
        css_plot_id = self._css_safe_plot_id(plot_id)
        toggle = widgets.ToggleButton(
            value=False,
            description="Toggle plot visibility",
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
        toggle.add_class(f"gu-legend-plot-id-{css_plot_id}")
        label_widget = widgets.HTMLMath(value="", layout=widgets.Layout(margin="0", width="100%"))
        style_widget = widgets.HTML(
            value=(
                "<style>"
                ".gu-legend-row {overflow: hidden !important;}"
                ".gu-legend-toggle,.gu-legend-toggle:hover,.gu-legend-toggle:focus,.gu-legend-toggle:active,"
                ".gu-legend-toggle.mod-active,.gu-legend-toggle.mod-active:hover,.gu-legend-toggle.mod-active:focus,"
                ".gu-legend-toggle button,.gu-legend-toggle button:hover,.gu-legend-toggle button:focus,.gu-legend-toggle button:active,"
                ".gu-legend-toggle .widget-button,.gu-legend-toggle .widget-button:hover,.gu-legend-toggle .widget-button:focus,"
                ".gu-legend-toggle .jupyter-button,.gu-legend-toggle .jupyter-button:hover,.gu-legend-toggle .jupyter-button:focus {"
                "background: transparent !important;background-color: transparent !important;background-image: none !important;"
                "border: none !important;box-shadow: none !important;outline: none !important;}"
                ".gu-legend-toggle {position: relative !important;overflow: hidden !important;border-radius: 999px !important;font-size: 0 !important;line-height: 0 !important;}"
                ".gu-legend-toggle::before {display: inline-flex !important;align-items: center !important;justify-content: center !important;width: 100% !important;height: 100% !important;font-size: 15px !important;line-height: 1 !important;}"
                ".gu-legend-toggle.mod-visible::before {content: '●';}"
                ".gu-legend-toggle.mod-hidden::before {content: '⊘';}"
                ".gu-legend-toggle:hover,.gu-legend-toggle:focus-visible {background-color: rgba(15, 23, 42, 0.06) !important;}"
                "</style>"
            ),
            layout=widgets.Layout(display="none", width="0", height="0"),
        )
        container = widgets.HBox(
            [toggle, label_widget, style_widget],
            layout=widgets.Layout(width="100%", align_items="center", margin="0", gap="6px"),
        )
        container.add_class("gu-legend-row")
        container.add_class("gu-figure-context-governed")
        container.add_class(f"gu-legend-plot-id-{css_plot_id}")
        toggle.observe(lambda change, pid=plot_id: self._on_toggle_changed(pid, change), names="value")
        return LegendRowModel(
            plot_id=plot_id,
            container=container,
            toggle=toggle,
            label_widget=label_widget,
            style_widget=style_widget,
            css_plot_id=css_plot_id,
        )

    def _sync_row_widgets(self, *, row: LegendRowModel, plot: Any) -> None:
        """Incrementally update label/toggle to mirror current plot state."""
        label = self._format_label_value(plot=plot, default_plot_id=row.plot_id)
        if row.label_widget.value != label:
            row.label_widget.value = label

        target_value = self._coerce_visible_to_bool(getattr(plot, "visible", True))
        marker_color = self._resolve_plot_color(plot)
        self._sync_toggle_accessibility(
            toggle=row.toggle,
            plot_label=self._accessible_plot_label(plot, row.plot_id),
            is_visible=target_value,
        )
        self._style_toggle_marker(toggle=row.toggle, is_visible=target_value, marker_color=marker_color)
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
        self._sync_toggle_accessibility(
            toggle=row.toggle,
            plot_label=self._accessible_plot_label(plot, plot_id),
            is_visible=plot.visible is True,
        )

    @staticmethod
    def _style_toggle_marker(*, toggle: widgets.ToggleButton, is_visible: bool, marker_color: str) -> None:
        """Render the toggle marker as a color-coded circular legend control."""
        toggle.icon = "circle" if is_visible else "times-circle"
        toggle.button_style = ""
        toggle.style.text_color = marker_color
        toggle.style.button_color = "transparent"
        toggle.layout.border = "none"
        toggle.layout.opacity = "1" if is_visible else "0.6"
        add_class = getattr(toggle, "add_class", None)
        remove_class = getattr(toggle, "remove_class", None)
        if callable(remove_class):
            remove_class("mod-visible")
            remove_class("mod-hidden")
        if is_visible:
            if callable(add_class):
                add_class("mod-visible")
        elif callable(add_class):
            add_class("mod-hidden")

    @staticmethod
    def _sync_toggle_accessibility(*, toggle: widgets.ToggleButton, plot_label: str, is_visible: bool) -> None:
        """Provide a descriptive, stateful accessible name for the toggle."""
        action = "Hide" if is_visible else "Show"
        label = plot_label.strip() or "plot"
        description = f"{action} plot {label}"
        toggle.description = description
        toggle.tooltip = description

    @classmethod
    def _accessible_plot_label(cls, plot: Any, default_plot_id: str) -> str:
        raw_label = cls._safe_attr_str(plot, "label").strip()
        if raw_label:
            return raw_label
        raw_plot_id = cls._safe_attr_str(plot, "id").strip()
        if raw_plot_id:
            return raw_plot_id
        return default_plot_id

    @classmethod
    def _resolve_plot_color(cls, plot: Any) -> str:
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
        getter = getattr(plot, "_reference_trace_handle", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        return None

    @classmethod
    def _resolve_trace_handle_color(cls, trace_handle: Any) -> str:
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
        return value is True

    @staticmethod
    def _normalize_plot_id(raw_plot_id: Any, *, fallback_prefix: str) -> str:
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
        raw_label = cls._safe_attr_str(plot, "label")
        if raw_label.strip() != "":
            return html.escape(raw_label)
        raw_plot_id = cls._safe_attr_str(plot, "id")
        if raw_plot_id.strip() != "":
            return html.escape(raw_plot_id)
        return html.escape(default_plot_id)

    @staticmethod
    def _safe_attr_str(plot: Any, attr_name: str) -> str:
        try:
            value = getattr(plot, attr_name, "")
        except Exception:
            return ""
        try:
            return "" if value is None else str(value)
        except Exception:
            return ""

    @staticmethod
    def _css_safe_plot_id(plot_id: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]+", lambda m: "_".join(f"x{ord(ch):02x}" for ch in m.group(0)), plot_id)

    @staticmethod
    def _decode_css_plot_id(css_plot_id: str) -> str:
        return css_plot_id

    @staticmethod
    def _dialog_style_html() -> str:
        return (
            "<style>"
            ".smart-slider-icon-button,.smart-slider-icon-button:hover,.smart-slider-icon-button:focus,.smart-slider-icon-button:active,"
            ".smart-slider-icon-button button,.smart-slider-icon-button button:hover,.smart-slider-icon-button button:focus,.smart-slider-icon-button button:active,"
            ".smart-slider-icon-button .widget-button,.smart-slider-icon-button .widget-button:hover,.smart-slider-icon-button .widget-button:focus,"
            ".smart-slider-icon-button .jupyter-button,.smart-slider-icon-button .jupyter-button:hover,.smart-slider-icon-button .jupyter-button:focus {"
            "background: transparent !important;background-color: transparent !important;background-image: none !important;border: none !important;box-shadow: none !important;outline: none !important;}"
            ".smart-slider-icon-button {position: relative !important;overflow: hidden !important;border-radius: 999px !important;font-size: 0 !important;line-height: 0 !important;}"
            ".smart-slider-icon-button::before {display: inline-flex !important;align-items: center !important;justify-content: center !important;width: 100% !important;height: 100% !important;font-size: 13px !important;line-height: 1 !important;}"
            ".smart-slider-icon-button:hover,.smart-slider-icon-button:focus-visible {background-color: rgba(15, 23, 42, 0.06) !important;}"
            ".smart-slider-close-button::before {content: '✕';}"
            ".smart-slider-settings-title {flex: 1 1 auto !important;min-width: 0 !important;flex-wrap: wrap !important;}"
            ".smart-slider-settings-title-text,.smart-slider-settings-title-subject {min-width: 0 !important;}"
            ".smart-slider-settings-title-subject {overflow-wrap: anywhere !important;}"
            ".smart-slider-settings-panel :is(input, textarea, select, button):focus-visible {outline: 2px solid var(--jp-brand-color1, #0b76d1) !important;outline-offset: 1px !important;}"
            "</style>"
        )

    def _handle_context_bridge_message(self, _widget: Any, content: Any, _buffers: Any) -> None:
        if not isinstance(content, dict):
            return
        if content.get("type") != "legend_context_request":
            return
        if content.get("action") != "open_style_dialog":
            return
        raw_plot_id = content.get("plot_id")
        if not isinstance(raw_plot_id, str):
            return
        plot = self._plots.get(raw_plot_id)
        if plot is None:
            return
        self._open_style_dialog(raw_plot_id)

    def _open_style_dialog(self, plot_id: str) -> None:
        plot = self._plots.get(plot_id)
        if plot is None:
            return
        self._settings_plot_id = plot_id
        self._sync_dialog_from_plot_state(force=True)
        self._set_style_dialog_open(True)

    def _close_style_dialog(self, _event: Any) -> None:
        self._set_style_dialog_open(False)

    def _set_style_dialog_open(self, is_open: bool) -> None:
        self._settings_open = bool(is_open)
        self._dialog_panel.layout.display = "flex" if self._settings_open else "none"
        self._dialog_modal.layout.display = "flex" if self._settings_open else "none"

    def _sync_dialog_from_plot_state(self, *, force: bool = False) -> None:
        plot_id = self._settings_plot_id
        if plot_id is None:
            return
        plot = self._plots.get(plot_id)
        if plot is None:
            self._set_style_dialog_open(False)
            self._settings_plot_id = None
            return
        if not force and not self._settings_open:
            return
        current_color = self._resolve_plot_color(plot)
        current_width = self._safe_float(getattr(plot, "thickness", None), default=2.0)
        current_opacity = self._safe_float(getattr(plot, "opacity", None), default=1.0)
        current_dash = self._safe_attr_str(plot, "dash").strip() or "solid"
        self._suspend_settings_observers = True
        try:
            self._dialog_subject.value = self._format_label_value(plot=plot, default_plot_id=plot_id)
            self._dialog_color.value = current_color
            self._dialog_width.value = current_width
            self._dialog_opacity.value = current_opacity
            self._dialog_dash.value = current_dash if current_dash in {value for _, value in _DASH_STYLE_OPTIONS} else "solid"
        finally:
            self._suspend_settings_observers = False

    def _on_dialog_value_changed(self, change: dict[str, Any]) -> None:
        if change.get("name") != "value":
            return
        if self._suspend_settings_observers:
            return
        plot_id = self._settings_plot_id
        if plot_id is None:
            return
        plot = self._plots.get(plot_id)
        if plot is None:
            return
        plot.color = self._dialog_color.value.strip() or None
        plot.thickness = float(self._dialog_width.value)
        plot.opacity = float(self._dialog_opacity.value)
        plot.dash = str(self._dialog_dash.value or "solid")
        self.on_plot_updated(plot)

    @staticmethod
    def _safe_float(value: Any, *, default: float) -> float:
        try:
            if value is None:
                return float(default)
            return float(value)
        except Exception:
            return float(default)
