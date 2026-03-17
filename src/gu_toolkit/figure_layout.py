"""Figure widget layout primitives.

`FigureLayout` owns widget composition only. It builds the notebook widget tree,
manages the view selector plus persistent per-view page hosts, and exposes the
sidebar and output regions used by :class:`gu_toolkit.Figure.Figure`.

It does not own plot data, render policy, or pane reflow callbacks.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import ipywidgets as widgets
from IPython.display import display

from .layout_logging import layout_value_snapshot


class OneShotOutput(widgets.Output):
    """An ``Output`` widget that raises when displayed more than once."""

    __slots__ = ("_displayed",)

    def __init__(self) -> None:
        super().__init__()
        self._displayed = False

    def _repr_mimebundle_(
        self, include: Any = None, exclude: Any = None, **kwargs: Any
    ) -> Any:
        if self._displayed:
            raise RuntimeError(
                "OneShotOutput has already been displayed. "
                "This widget supports only one-time display."
            )
        self._displayed = True
        return super()._repr_mimebundle_(include=include, exclude=exclude, **kwargs)

    @property
    def has_been_displayed(self) -> bool:
        return self._displayed

    def reset_display_state(self) -> None:
        self._displayed = False


@dataclass
class _ViewPage:
    """Internal widget record for one persistent view host."""

    view_id: str
    title: str
    host_box: widgets.Box
    widget: widgets.Widget | None = None


class FigureLayout:
    """Own the widget tree used by a figure instance."""

    def __init__(self, title: str = "") -> None:
        self._view_pages: dict[str, _ViewPage] = {}
        self._layout_event_emitter: Callable[..., Any] | None = None
        self._layout_event_base: dict[str, Any] = {}
        self._ordered_view_ids: tuple[str, ...] = ()
        self._active_view_id: str | None = None
        self._suspend_view_selector_events = False

        # 1. Title bar
        self.title_html = widgets.HTMLMath(
            value=title, layout=widgets.Layout(margin="0px")
        )
        self.full_width_checkbox = widgets.Checkbox(
            value=False,
            description="Full width plot",
            indent=False,
            layout=widgets.Layout(width="160px", margin="0px"),
        )
        self._titlebar = widgets.HBox(
            [self.title_html, self.full_width_checkbox],
            layout=widgets.Layout(
                width="100%",
                align_items="center",
                justify_content="space-between",
                margin="0 0 6px 0",
            ),
        )

        # 2. Persistent view selector + stage
        self.view_selector = widgets.ToggleButtons(
            options=(),
            value=None,
            layout=widgets.Layout(display="none", width="100%", margin="0 0 6px 0"),
        )
        self.view_stage = widgets.Box(
            children=(),
            layout=widgets.Layout(
                width="100%",
                height="60vh",
                min_width="320px",
                min_height="260px",
                margin="0px",
                padding="0px",
                flex="1 1 560px",
                display="flex",
                flex_flow="column",
                overflow="hidden",
            ),
        )

        # 3. Controls sidebar
        self.params_header = widgets.HTML(
            "<b>Parameters</b>",
            layout=widgets.Layout(display="none", margin="10px 0 0 0"),
        )
        self.params_box = widgets.VBox(
            layout=widgets.Layout(
                width="100%",
                display="none",
                padding="8px",
                border="1px solid rgba(15,23,42,0.08)",
                border_radius="10px",
            )
        )

        self.info_header = widgets.HTML(
            "<b>Info</b>", layout=widgets.Layout(display="none", margin="10px 0 0 0")
        )
        self.info_box = widgets.VBox(
            layout=widgets.Layout(
                width="100%",
                display="none",
                padding="8px",
                border="1px solid rgba(15,23,42,0.08)",
                border_radius="10px",
            )
        )

        self.legend_header = widgets.HTML(
            "<b>Legend</b>", layout=widgets.Layout(display="none", margin="0")
        )
        self.legend_box = widgets.VBox(
            layout=widgets.Layout(
                width="100%",
                display="none",
                padding="8px",
                border="1px solid rgba(15,23,42,0.08)",
                border_radius="10px",
            )
        )

        self.sidebar_container = widgets.VBox(
            [
                self.legend_header,
                self.legend_box,
                self.params_header,
                self.params_box,
                self.info_header,
                self.info_box,
            ],
            layout=widgets.Layout(
                margin="0px",
                padding="0px 0px 0px 10px",
                flex="0 1 380px",
                min_width="300px",
                max_width="400px",
                display="none",
            ),
        )

        # 4. Main content wrapper
        self.left_panel = widgets.VBox(
            [self.view_selector, self.view_stage],
            layout=widgets.Layout(
                width="100%", flex="1 1 560px", margin="0px", padding="0px"
            ),
        )

        self.content_wrapper = widgets.Box(
            [self.left_panel, self.sidebar_container],
            layout=widgets.Layout(
                display="flex",
                flex_flow="row wrap",
                align_items="flex-start",
                width="100%",
                gap="8px",
            ),
        )

        # 5. Output area below the figure
        self.print_header = widgets.HTML(
            "<b>Output</b>", layout=widgets.Layout(margin="8px 0 4px 0")
        )
        self.print_output = widgets.Output(
            layout=widgets.Layout(
                width="100%",
                min_height="48px",
                padding="8px",
                border="1px solid rgba(15,23,42,0.08)",
                border_radius="10px",
                overflow="auto",
            )
        )
        self.print_area = widgets.VBox(
            [self.print_header, self.print_output],
            layout=widgets.Layout(width="100%", margin="6px 0 0 0"),
        )

        self.root_widget = widgets.VBox(
            [self._titlebar, self.content_wrapper, self.print_area],
            layout=widgets.Layout(width="100%", position="relative"),
        )

        self.full_width_checkbox.observe(self._on_full_width_change, names="value")
        self._emit_layout_event(
            "layout_initialized",
            phase="completed",
            title=title,
            sidebar_display=self.sidebar_container.layout.display,
            view_stage=layout_value_snapshot(self.view_stage.layout, ("width", "height", "min_height", "display", "overflow")),
        )

    def bind_layout_debug(self, emitter: Callable[..., Any], **base_fields: Any) -> None:
        self._layout_event_emitter = emitter
        self._layout_event_base = dict(base_fields)

    def _emit_layout_event(self, event: str, *, phase: str, **fields: Any) -> None:
        if self._layout_event_emitter is None:
            return
        payload = dict(self._layout_event_base)
        payload.update(fields)
        self._layout_event_emitter(event=event, source="FigureLayout", phase=phase, **payload)

    @property
    def output_widget(self) -> OneShotOutput:
        out = OneShotOutput()
        with out:
            display(self.root_widget)
        return out

    def set_title(self, text: str) -> None:
        self.title_html.value = text

    def get_title(self) -> str:
        return self.title_html.value

    def update_sidebar_visibility(
        self, has_params: bool, has_info: bool, has_legend: bool
    ) -> bool:
        """Apply sidebar section visibility and report geometry changes."""
        old_state = (
            self.params_header.layout.display,
            self.params_box.layout.display,
            self.info_header.layout.display,
            self.info_box.layout.display,
            self.legend_header.layout.display,
            self.legend_box.layout.display,
            self.sidebar_container.layout.display,
        )

        self.params_header.layout.display = "block" if has_params else "none"
        self.params_box.layout.display = "flex" if has_params else "none"

        self.info_header.layout.display = "block" if has_info else "none"
        self.info_box.layout.display = "flex" if has_info else "none"

        self.legend_header.layout.display = "block" if has_legend else "none"
        self.legend_box.layout.display = "flex" if has_legend else "none"

        show_sidebar = has_params or has_info or has_legend
        self.sidebar_container.layout.display = "flex" if show_sidebar else "none"

        new_state = (
            self.params_header.layout.display,
            self.params_box.layout.display,
            self.info_header.layout.display,
            self.info_box.layout.display,
            self.legend_header.layout.display,
            self.legend_box.layout.display,
            self.sidebar_container.layout.display,
        )
        return new_state != old_state

    def ensure_view_page(self, view_id: str, title: str) -> None:
        """Ensure a persistent host page exists for ``view_id``."""
        key = str(view_id)
        page = self._view_pages.get(key)
        if page is None:
            host_box = widgets.Box(
                children=(),
                layout=widgets.Layout(
                    width="100%",
                    height="100%",
                    min_width="0",
                    min_height="0",
                    display="none",
                    flex="1 1 auto",
                    overflow="hidden",
                ),
            )
            self._view_pages[key] = _ViewPage(
                view_id=key,
                title=str(title),
                host_box=host_box,
                widget=None,
            )
            if key not in self._ordered_view_ids:
                self._ordered_view_ids = (*self._ordered_view_ids, key)
        else:
            page.title = str(title)
        self._rebuild_view_stage()
        self._refresh_view_selector()
        self._emit_layout_event("view_order_changed", phase="completed", ordered_view_ids=list(self._ordered_view_ids))
        self._emit_layout_event("view_page_removed", phase="completed", view_id=view_id)
        self._emit_layout_event("view_page_created", phase="completed", view_id=view_id, title=title, host_box=layout_value_snapshot(host_box.layout, ("width", "height", "display", "overflow")))
        self._apply_active_page_visibility()

    def attach_view_widget(self, view_id: str, widget: widgets.Widget) -> None:
        """Attach ``widget`` to the persistent page for ``view_id``."""
        key = str(view_id)
        if key in self._view_pages:
            title = self._view_pages[key].title
        else:
            title = key
        self.ensure_view_page(key, title=title)
        page = self._view_pages[key]
        page.widget = widget
        page.host_box.children = (widget,)
        self._emit_layout_event("view_widget_attached", phase="completed", view_id=view_id, widget_type=type(widget).__name__)

    def remove_view_page(self, view_id: str) -> None:
        """Remove page bookkeeping for ``view_id`` if present."""
        key = str(view_id)
        page = self._view_pages.pop(key, None)
        if page is None:
            return
        page.host_box.children = ()
        self._ordered_view_ids = tuple(v for v in self._ordered_view_ids if v != key)
        if self._active_view_id == key:
            self._active_view_id = (
                self._ordered_view_ids[0] if self._ordered_view_ids else None
            )
        self._rebuild_view_stage()
        self._refresh_view_selector()
        self._apply_active_page_visibility()

    def set_view_order(self, view_ids: Sequence[str]) -> None:
        """Set the visual order of registered view pages."""
        ordered = tuple(str(view_id) for view_id in view_ids if str(view_id) in self._view_pages)
        if ordered == self._ordered_view_ids:
            self._refresh_view_selector()
            self._apply_active_page_visibility()
            return
        self._ordered_view_ids = ordered
        if self._active_view_id not in self._ordered_view_ids:
            self._active_view_id = self._ordered_view_ids[0] if self._ordered_view_ids else None
        self._rebuild_view_stage()
        self._refresh_view_selector()
        self._apply_active_page_visibility()

    def set_active_view(self, view_id: str) -> None:
        """Show only the active view page and sync selector selection."""
        key = str(view_id)
        if key not in self._view_pages:
            raise KeyError(f"Unknown view page: {key}")
        self._active_view_id = key
        self._apply_active_page_visibility()
        self._refresh_view_selector()

    def set_view_title(self, view_id: str, title: str) -> None:
        """Update the selector title for ``view_id``."""
        page = self._view_pages.get(str(view_id))
        if page is None:
            return
        page.title = str(title)
        self._refresh_view_selector()

    def observe_view_selection(self, callback: Callable[[str], None]) -> None:
        """Call ``callback`` whenever the selector chooses a new view."""

        def _on_selection(change: dict[str, Any]) -> None:
            if self._suspend_view_selector_events:
                return
            new_value = change.get("new")
            if new_value is None:
                return
            callback(str(new_value))

        self.view_selector.observe(_on_selection, names="value")

    def observe_full_width_change(self, callback: Callable[[bool], None]) -> None:
        """Observe full-width layout toggle changes."""

        def _on_full_width(change: dict[str, Any]) -> None:
            callback(bool(change.get("new")))

        self.full_width_checkbox.observe(_on_full_width, names="value")

    # ------------------------------------------------------------------
    # Compatibility wrappers kept for one refactor cycle.
    # ------------------------------------------------------------------

    def set_plot_widget(
        self,
        widget: widgets.Widget,
        *,
        reflow_callback: Callable[[], None] | None = None,
    ) -> None:
        del reflow_callback
        self.ensure_view_page("main", "main")
        self.attach_view_widget("main", widget)
        self.set_view_order(("main",))
        self.set_active_view("main")

    def set_view_plot_widget(
        self,
        view_id: str,
        widget: widgets.Widget,
        *,
        reflow_callback: Callable[[], None] | None = None,
    ) -> None:
        del reflow_callback
        self.ensure_view_page(str(view_id), str(view_id))
        self.attach_view_widget(str(view_id), widget)

    def set_view_tabs(self, view_ids: Sequence[str], *, active_view_id: str) -> None:
        self.set_view_order(view_ids)
        self.set_active_view(active_view_id)

    def trigger_reflow_for_view(self, view_id: str) -> None:
        del view_id
        return None

    def observe_tab_selection(self, callback: Callable[[str], None]) -> None:
        self.observe_view_selection(callback)

    # ------------------------------------------------------------------
    # Internal helpers.
    # ------------------------------------------------------------------

    def _rebuild_view_stage(self) -> None:
        self.view_stage.children = tuple(
            self._view_pages[view_id].host_box
            for view_id in self._ordered_view_ids
            if view_id in self._view_pages
        )

    def _apply_active_page_visibility(self) -> None:
        for view_id, page in self._view_pages.items():
            display = "flex" if view_id == self._active_view_id else "none"
            page.host_box.layout.display = display
            self._emit_layout_event("view_page_visibility_changed", phase="completed", view_id=view_id, display_state=display, is_active=(view_id == self._active_view_id))

    def _refresh_view_selector(self) -> None:
        options = [
            (self._view_pages[view_id].title, view_id)
            for view_id in self._ordered_view_ids
            if view_id in self._view_pages
        ]
        show_selector = len(options) > 1
        desired_value = None
        if self._active_view_id is not None and any(val == self._active_view_id for _, val in options):
            desired_value = self._active_view_id
        elif options:
            desired_value = options[0][1]
            self._active_view_id = desired_value

        self._suspend_view_selector_events = True
        try:
            self.view_selector.options = tuple(options)
            self.view_selector.layout.display = "flex" if show_selector else "none"
            if desired_value is None:
                self.view_selector.value = None
            elif self.view_selector.value != desired_value:
                self.view_selector.value = desired_value
        finally:
            self._suspend_view_selector_events = False
        self._emit_layout_event("view_selector_refreshed", phase="completed", options=[val for _, val in options], selector_display=self.view_selector.layout.display, active_view_id=self._active_view_id)

    def _on_full_width_change(self, change: dict[str, Any]) -> None:
        is_full = bool(change["new"])
        layout = self.content_wrapper.layout
        plot_layout = self.left_panel.layout
        sidebar_layout = self.sidebar_container.layout

        if is_full:
            layout.flex_flow = "column"
            plot_layout.flex = "0 0 auto"
            sidebar_layout.flex = "0 0 auto"
            sidebar_layout.max_width = ""
            sidebar_layout.width = "100%"
            sidebar_layout.padding = "0px"
        else:
            layout.flex_flow = "row wrap"
            plot_layout.flex = "1 1 560px"
            sidebar_layout.flex = "0 1 380px"
            sidebar_layout.max_width = "400px"
            sidebar_layout.width = "auto"
            sidebar_layout.padding = "0px 0px 0px 10px"
        self._emit_layout_event("full_width_layout_changed", phase="completed", is_full=is_full, content_wrapper=layout_value_snapshot(layout, ("display", "flex_flow", "gap")), left_panel=layout_value_snapshot(plot_layout, ("width", "flex")), sidebar=layout_value_snapshot(sidebar_layout, ("display", "flex", "max_width", "width", "padding")))
