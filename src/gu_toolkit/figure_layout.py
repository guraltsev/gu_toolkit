"""Figure widget layout manager.

`FigureLayout` is the notebook layout manager for a figure. It builds the
notebook widget tree, owns the concrete section widgets used by the current
shell, manages view-selector state, and provides the notebook display/mount
helper used by :class:`gu_toolkit.Figure.Figure`.

It does not own plot data, render policy, or pane reflow callbacks.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ._widget_stubs import widgets
from .figure_shell import _FigureShellSpec, _ShellPageSpec, _resolve_figure_shell_spec
from .ui_system import (
    build_layout,
    build_section_panel,
    build_tab_bar,
    configure_action_button,
    load_ui_css,
    set_tab_button_selected,
    shared_style_widget,
)
from IPython.display import clear_output, display

from .layout_logging import layout_value_snapshot
from .widget_chrome import TabListBridge, attach_host_children


class OneShotOutput(widgets.Output):
    """An ``Output`` widget that raises when displayed more than once.
    
    Full API
    --------
    ``OneShotOutput()``
    
    Public members exposed from this class: ``has_been_displayed``, ``reset_display_state``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    OneShotOutput
        New ``OneShotOutput`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``OneShotOutput`` lives in ``gu_toolkit.figure_layout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_layout import OneShotOutput
        obj = OneShotOutput(...)
    
    Discovery-oriented use::
    
        help(OneShotOutput)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(OneShotOutput)`` and ``dir(OneShotOutput)`` to inspect adjacent members.
    """

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
        """Return whether been displayed.
        
        Full API
        --------
        ``obj.has_been_displayed -> bool``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        bool
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``OneShotOutput``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = OneShotOutput(...)
            current = obj.has_been_displayed
        
        Discovery-oriented use::
        
            help(OneShotOutput)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(OneShotOutput)`` and ``dir(OneShotOutput)`` to inspect adjacent members.
        """

        return self._displayed

    def reset_display_state(self) -> None:
        """Work with reset display state on ``OneShotOutput``.
        
        Full API
        --------
        ``obj.reset_display_state() -> None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``OneShotOutput``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = OneShotOutput(...)
            obj.reset_display_state(...)
        
        Discovery-oriented use::
        
            help(OneShotOutput)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(OneShotOutput)`` and ``dir(OneShotOutput)`` to inspect adjacent members.
        """

        self._displayed = False


@dataclass
class _ViewPage:
    """Internal widget record for one persistent view host."""

    view_id: str
    title: str
    host_box: widgets.Box
    widget: widgets.Widget | None = None


@dataclass
class _ShellPageState:
    """Internal widget record for one persistent shell page host."""

    spec: _ShellPageSpec
    host_box: widgets.VBox
    row_box: widgets.Box
    center_box: widgets.VBox
    left_box: widgets.VBox
    right_box: widgets.VBox
    bottom_box: widgets.VBox
    tab_button: widgets.Button | None = None


class FigureLayout:
    """Own the widget tree used by a figure instance.
    
    Full API
    --------
    ``FigureLayout(title: str='')``
    
    Public members exposed from this class: ``bind_layout_debug``, ``bind_reflow_request``, ``output_widget``, ``layout_snapshot``,
        ``set_title``, ``get_title``, ``update_sidebar_visibility``, ``ensure_view_page``,
        ``attach_view_widget``, ``remove_view_page``, ``set_view_order``,
        ``set_active_view``, ``set_view_title``, ``observe_view_selection``,
        ``observe_full_width_change``, ``bind_view_reflow``, ``content_layout_mode``,
        ``set_plot_widget``, ``set_view_plot_widget``, ``set_view_tabs``,
        ``trigger_reflow_for_view``, ``observe_tab_selection``
    
    Parameters
    ----------
    title : str, optional
        Human-readable title text shown in the UI or stored in snapshots. Defaults to ``''``.
    
    Returns
    -------
    FigureLayout
        New ``FigureLayout`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``title=''``: Human-readable title text shown in the UI or stored in snapshots.
    
    Architecture note
    -----------------
    ``FigureLayout`` lives in ``gu_toolkit.figure_layout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_layout import FigureLayout
        obj = FigureLayout(...)
    
    Discovery-oriented use::
    
        help(FigureLayout)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
    """

    _STYLE_CSS = load_ui_css("figure_layout.css")

    def __init__(self, title: str = "", *, shell: str | None = None) -> None:
        self._view_pages: dict[str, _ViewPage] = {}
        self._layout_event_emitter: Callable[..., Any] | None = None
        self._layout_event_base: dict[str, Any] = {}
        self._ordered_view_ids: tuple[str, ...] = ()
        self._active_view_id: str | None = None
        self._suspend_view_selector_events = False
        self._reflow_callback: Callable[[str, str], Any] | None = None
        self._content_layout_mode = "wrapped"
        self._view_selector_items: tuple[tuple[str, str], ...] = ()
        self._view_selection_observers: list[Callable[[str], None]] = []
        self._shell_spec: _FigureShellSpec = _resolve_figure_shell_spec(shell)
        self._shell_pages: dict[str, _ShellPageState] = {}
        self._ordered_shell_page_ids: tuple[str, ...] = ()
        self._visible_shell_page_ids: tuple[str, ...] = ()
        self._active_shell_page_id: str | None = None
        self._shell_page_buttons: dict[str, widgets.Button] = {}
        self._content_rows: tuple[widgets.Box, ...] = ()
        self._center_boxes: tuple[widgets.VBox, ...] = ()
        self._sidebar_slots: tuple[widgets.VBox, ...] = ()
        self._section_visibility: dict[str, bool] = {
            "legend": False,
            "parameters": False,
            "info": False,
        }

        # 1. Title bar
        self.title_html = widgets.HTMLMath(
            value=title, layout=build_layout(margin="0px")
        )
        self.title_html.add_class("gu-figure-title")
        self.full_width_checkbox = widgets.Checkbox(
            value=False,
            description="Full width plot",
            indent=False,
            layout=build_layout(
                width="160px",
                margin="0px",
                display=("flex" if self._shell_spec.show_full_width_toggle else "none"),
            ),
        )
        self._titlebar = widgets.HBox(
            [self.title_html, self.full_width_checkbox],
            layout=build_layout(
                width="100%",
                align_items="center",
                justify_content="space-between",
                margin="0 0 6px 0",
            ),
        )
        self._titlebar.add_class("gu-figure-titlebar")

        # 2. Persistent view selector + stage
        self.view_selector = widgets.ToggleButtons(
            options=(),
            value=None,
            layout=build_layout(display="none", width="100%", margin="0 0 6px 0"),
        )
        self.view_selector.observe(self._on_view_selector_change, names="value")
        self.view_stage = widgets.Box(
            children=(),
            layout=build_layout(
                width="100%",
                height="60vh",
                min_width="0",
                min_height="260px",
                margin="0px",
                padding="0px",
                flex="1 1 560px",
                display="flex",
                flex_flow="column",
                overflow="hidden",
            ),
        )
        self.view_stage.add_class("gu-figure-view-stage")
        self.view_stage.add_class("gu-figure-context-governed")

        # 3. Stable section roots.
        self.legend_panel = build_section_panel(
            "Legend",
            variant="toolbar",
            display="none",
            extra_classes=("gu-figure-sidebar-panel", "gu-figure-panel-box"),
            body_extra_classes=("gu-figure-panel-body", "gu-figure-legend-area"),
        )
        self.legend_header = self.legend_panel.title
        self.legend_header_toolbar = self.legend_panel.toolbar
        self.legend_box = self.legend_panel.body

        self.params_panel = build_section_panel(
            "Parameters",
            variant="minimal",
            display="none",
            extra_classes=("gu-figure-sidebar-panel", "gu-figure-panel-box"),
            body_extra_classes=("gu-figure-panel-body",),
        )
        self.params_header = self.params_panel.title
        self.params_box = self.params_panel.body

        self.info_panel = build_section_panel(
            "Info",
            variant="minimal",
            display="none",
            extra_classes=("gu-figure-sidebar-panel", "gu-figure-panel-box"),
            body_extra_classes=("gu-figure-panel-body", "gu-figure-info-output"),
        )
        self.info_header = self.info_panel.title
        self.info_box = self.info_panel.body

        # 4. Stable region hosts used by shell pages.
        self.left_panel = widgets.VBox(
            [self.view_selector, self.view_stage],
            layout=build_layout(
                width="100%",
                min_width="0",
                flex="1 1 560px",
                margin="0px",
                padding="0px",
            ),
        )
        self.left_panel.add_class("gu-figure-left-panel")

        self.left_sidebar_container = self._build_sidebar_region(side="left")
        self.sidebar_container = self._build_sidebar_region(side="right")

        self.content_wrapper = widgets.Box(
            [],
            layout=build_layout(
                display="flex",
                flex_flow="row wrap",
                align_items="stretch",
                width="100%",
                min_width="0",
                min_height="0",
                gap="8px",
            ),
        )
        self.content_wrapper.add_class("gu-figure-content")

        self.bottom_section_container = self._build_bottom_region()

        # 5. Output area below the figure.
        self.print_output = widgets.Output(
            layout=build_layout(
                width="100%",
                min_width="0",
                min_height="32px",
                margin="0px",
                padding="0px",
            )
        )
        self.print_output.add_class("gu-figure-output-widget")
        self.output_panel = build_section_panel(
            "Output",
            variant="minimal",
            display="flex",
            extra_classes=("gu-figure-output-panel", "gu-figure-panel-box"),
            body_extra_classes=("gu-figure-output-body",),
        )
        self.print_header = self.output_panel.title
        self.print_panel = self.output_panel.panel
        self.output_panel.body.children = (self.print_output,)
        self.output_panel.body.layout.overflow_y = "auto"
        self.print_area = widgets.VBox(
            [self.print_panel],
            layout=build_layout(width="100%", margin="6px 0 0 0"),
        )
        self.print_area.add_class("gu-figure-context-governed")

        # 6. Shell-level page tabs + content surface.
        self.shell_page_bar = build_tab_bar([], extra_classes=("gu-figure-shell-tabs",))
        self.shell_page_tabs = widgets.VBox(
            [self.shell_page_bar],
            layout=build_layout(width="100%", min_width="0", margin="0 0 6px 0", display="none"),
        )
        self.shell_page_tabs.add_class("gu-figure-shell-tabs-host")
        self.shell_page_tabs.add_class("gu-figure-context-governed")
        self.shell_page_content = widgets.VBox(
            [],
            layout=build_layout(width="100%", min_width="0", margin="0px", padding="0px", gap="0px"),
        )
        self.shell_page_content.add_class("gu-figure-shell-page-content")
        self.shell_page_content.add_class("gu-figure-context-governed")
        self._shell_page_bridge = TabListBridge(
            tablist_selector=".gu-figure-shell-tabs",
            panel_selector=".gu-figure-shell-page-panel",
            selected_index=0,
        )

        self._style_widget = shared_style_widget(self._STYLE_CSS)

        self.root_widget = widgets.VBox(
            [
                self._style_widget,
                self._titlebar,
                self.shell_page_tabs,
                self.shell_page_content,
                self.print_area,
            ],
            layout=build_layout(width="100%", min_width="0", position="relative"),
        )
        self.root_widget.add_class("gu-figure-root")
        self.root_widget.add_class("gu-theme-root")
        attach_host_children(self.root_widget, self._shell_page_bridge)

        self._section_widgets = {
            "shell": self.root_widget,
            "title": self._titlebar,
            "navigation": self.view_selector,
            "stage": self.view_stage,
            "legend": self.legend_panel.panel,
            "parameters": self.params_panel.panel,
            "info": self.info_panel.panel,
            "output": self.print_panel,
            "page_tabs": self.shell_page_tabs,
            "page_content": self.shell_page_content,
        }
        self._shell_slots = {
            "title": self._titlebar,
            "navigation": self.view_selector,
            "stage": self.view_stage,
            "legend": self.legend_panel.panel,
            "parameters": self.params_panel.panel,
            "info": self.info_panel.panel,
            "output": self.print_panel,
            "page_tabs": self.shell_page_tabs,
            "page_content": self.shell_page_content,
            "left_region": self.left_sidebar_container,
            "right_region": self.sidebar_container,
            "bottom_region": self.bottom_section_container,
        }

        self._rebuild_shell_arrangement()
        self.full_width_checkbox.observe(self._on_full_width_change, names="value")
        self._apply_content_layout_mode(is_full=self.full_width_checkbox.value)
        self.update_sidebar_visibility(False, False, False)
        self._emit_layout_event(
            "layout_initialized",
            phase="completed",
            title=title,
            shell_preset=self._shell_spec.name,
            active_shell_page_id=self._active_shell_page_id,
            sidebar_display=self.sidebar_container.layout.display,
            view_stage=layout_value_snapshot(
                self.view_stage.layout,
                ("width", "height", "min_height", "display", "overflow"),
            ),
        )

    def bind_layout_debug(self, emitter: Callable[..., Any], **base_fields: Any) -> None:
        """Bind layout debug.
        
        Full API
        --------
        ``obj.bind_layout_debug(emitter: Callable[..., Any], **base_fields: Any) -> None``
        
        Parameters
        ----------
        emitter : Callable[Ellipsis, Any]
            Value for ``emitter`` in this API. Required.
        
        **base_fields : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``**base_fields``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.bind_layout_debug(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        self._layout_event_emitter = emitter
        self._layout_event_base = dict(base_fields)

    def _emit_layout_event(self, event: str, *, phase: str, **fields: Any) -> None:
        if self._layout_event_emitter is None:
            return
        payload = dict(self._layout_event_base)
        payload.update(fields)
        self._layout_event_emitter(event=event, source="FigureLayout", phase=phase, **payload)

    def bind_reflow_request(self, callback: Callable[[str, str], Any] | None) -> None:
        """Backward-compatible alias for :meth:`bind_view_reflow`.
        
        Full API
        --------
        ``obj.bind_reflow_request(callback: Callable[[str, str], Any] | None) -> None``
        
        Parameters
        ----------
        callback : Callable[[str, str], Any] | None
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.bind_reflow_request(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        self._reflow_callback = callback

    def _materialize_display_output(self) -> OneShotOutput:
        """Wrap the current shell root in a one-shot notebook output widget."""

        out = OneShotOutput()
        with out:
            display(self.root_widget)
        return out

    def _mount_parameter_control(self, control: Any) -> None:
        """Attach a parameter control to the notebook parameter section."""

        attach_fn = getattr(control, "set_modal_host", None)
        if callable(attach_fn):
            attach_fn(self.root_widget)
        if control not in self.params_box.children:
            self.params_box.children = (*self.params_box.children, control)

    @property
    def _legend_has_toolbar_host(self) -> bool:
        """Return whether the notebook legend section exposes a toolbar host."""

        return self.legend_header_toolbar is not None

    @property
    def _legend_body_children(self) -> tuple[widgets.Widget, ...]:
        """Return the widgets currently mounted in the notebook legend body."""

        return tuple(self.legend_box.children)

    def _add_legend_body_class(self, class_name: str) -> None:
        """Add a CSS class to the legend body when supported by the widget."""

        add_class = getattr(self.legend_box, "add_class", None)
        if callable(add_class):
            add_class(class_name)

    def _add_root_classes(self, *class_names: str) -> None:
        """Add CSS classes to the shell root widget."""

        add_class = getattr(self.root_widget, "add_class", None)
        if not callable(add_class):
            return
        for class_name in class_names:
            add_class(class_name)

    def _attach_overlay_children(self, *children: widgets.Widget) -> None:
        """Attach modal and bridge widgets to the layout root."""

        attach_host_children(self.root_widget, *children)

    def _set_legend_toolbar_children(self, children: Sequence[widgets.Widget]) -> None:
        """Replace the notebook legend toolbar widgets."""

        desired = tuple(children)
        if self.legend_header_toolbar.children != desired:
            self.legend_header_toolbar.children = desired

    def _set_legend_body_children(self, children: Sequence[widgets.Widget]) -> None:
        """Replace the notebook legend body widgets."""

        desired = tuple(children)
        if self.legend_box.children != desired:
            self.legend_box.children = desired

    @property
    def output_widget(self) -> OneShotOutput:
        """Work with output widget on ``FigureLayout``.
        
        Full API
        --------
        ``obj.output_widget -> OneShotOutput``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        OneShotOutput
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            current = obj.output_widget
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        return self._materialize_display_output()

    def layout_snapshot(self) -> dict[str, Any]:
        """Return a structural snapshot of the figure layout widget tree.
        
        Full API
        --------
        ``obj.layout_snapshot() -> dict[str, Any]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        dict[str, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            result = obj.layout_snapshot(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        pages = {
            view_id: {
                "title": page.title,
                "display": page.host_box.layout.display,
                "has_widget": page.widget is not None,
            }
            for view_id, page in self._view_pages.items()
        }
        shell_pages = {
            page_id: {
                "title": state.spec.title,
                "display": state.host_box.layout.display,
                "includes_stage": state.spec.include_stage,
                "main_sections": list(state.spec.main_sections),
                "left_sections": list(state.spec.left_sections),
                "right_sections": list(state.spec.right_sections),
                "bottom_sections": list(state.spec.bottom_sections),
            }
            for page_id, state in self._shell_pages.items()
        }
        return {
            "title": self.title_html.value,
            "full_width": bool(self.full_width_checkbox.value),
            "content_layout_mode": self._content_layout_mode,
            "shell_preset": self._shell_spec.name,
            "active_shell_page_id": self._active_shell_page_id,
            "visible_shell_page_ids": list(self._visible_shell_page_ids),
            "shell_tabs_display": self.shell_page_tabs.layout.display,
            "ordered_view_ids": list(self._ordered_view_ids),
            "active_view_id": self._active_view_id,
            "view_selector_display": self.view_selector.layout.display,
            "content_wrapper": layout_value_snapshot(
                self.content_wrapper.layout,
                ("display", "flex_flow", "gap", "width", "min_width", "min_height"),
            ),
            "left_panel": layout_value_snapshot(
                self.left_panel.layout,
                ("width", "min_width", "flex"),
            ),
            "view_stage": layout_value_snapshot(
                self.view_stage.layout,
                ("width", "height", "min_width", "min_height", "display", "flex", "overflow"),
            ),
            "sidebar": layout_value_snapshot(
                self.sidebar_container.layout,
                ("display", "flex", "min_width", "max_width", "width", "padding", "overflow"),
            ),
            "left_sidebar": layout_value_snapshot(
                self.left_sidebar_container.layout,
                ("display", "flex", "min_width", "max_width", "width", "padding", "overflow"),
            ),
            "bottom_region": layout_value_snapshot(
                self.bottom_section_container.layout,
                ("display", "width", "margin", "gap"),
            ),
            "print_area": layout_value_snapshot(
                self.print_area.layout,
                ("width", "margin"),
            ),
            "pages": pages,
            "shell_pages": shell_pages,
        }

    def set_title(self, text: str) -> None:
        """Set title.
        
        Full API
        --------
        ``obj.set_title(text: str) -> None``
        
        Parameters
        ----------
        text : str
            Human-readable text payload or label content. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_title(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        self.title_html.value = text

    def get_title(self) -> str:
        """Return title.
        
        Full API
        --------
        ``obj.get_title() -> str``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            result = obj.get_title(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        return self.title_html.value

    def update_sidebar_visibility(
        self, has_params: bool, has_info: bool, has_legend: bool
    ) -> bool:
        """Apply sidebar section visibility and report geometry changes.
        
        Full API
        --------
        ``obj.update_sidebar_visibility(has_params: bool, has_info: bool, has_legend: bool) -> bool``
        
        Parameters
        ----------
        has_params : bool
            Boolean flag or query related to availability of params. Required.
        
        has_info : bool
            Boolean flag or query related to availability of info. Required.
        
        has_legend : bool
            Boolean flag or query related to availability of legend. Required.
        
        Returns
        -------
        bool
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            result = obj.update_sidebar_visibility(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        old_state = self._shell_display_state()

        self._section_visibility = {
            "legend": bool(has_legend),
            "parameters": bool(has_params),
            "info": bool(has_info),
        }
        self._apply_shell_visibility()

        new_state = self._shell_display_state()
        changed = new_state != old_state
        self._emit_layout_event(
            "sidebar_visibility_changed" if changed else "sidebar_visibility_unchanged",
            phase="completed",
            has_params=has_params,
            has_info=has_info,
            has_legend=has_legend,
            shell_preset=self._shell_spec.name,
            active_shell_page_id=self._active_shell_page_id,
            available_shell_pages=list(self._visible_shell_page_ids),
            sidebar_display=self.sidebar_container.layout.display,
        )
        return changed

    def ensure_view_page(self, view_id: str, title: str) -> None:
        """Ensure a persistent host page exists for ``view_id``.
        
        Full API
        --------
        ``obj.ensure_view_page(view_id: str, title: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        title : str
            Human-readable title text shown in the UI or stored in snapshots. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.ensure_view_page(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        key = str(view_id)
        previous_order = self._ordered_view_ids
        page = self._view_pages.get(key)
        created = False
        if page is None:
            host_box = widgets.Box(
                children=(),
                layout=build_layout(
                    width="100%",
                    height="100%",
                    min_width="0",
                    min_height="0",
                    display="none",
                    flex="1 1 auto",
                    overflow="hidden",
                ),
            )
            host_box.add_class("gu-figure-view-page")
            page = _ViewPage(
                view_id=key,
                title=str(title),
                host_box=host_box,
                widget=None,
            )
            self._view_pages[key] = page
            if key not in self._ordered_view_ids:
                self._ordered_view_ids = (*self._ordered_view_ids, key)
            created = True
        else:
            page.title = str(title)

        self._rebuild_view_stage()
        self._refresh_view_selector()
        if self._ordered_view_ids != previous_order:
            self._emit_layout_event(
                "view_order_changed",
                phase="completed",
                ordered_view_ids=list(self._ordered_view_ids),
            )
        self._emit_layout_event(
            "view_page_created" if created else "view_page_updated",
            phase="completed",
            view_id=view_id,
            title=title,
            host_box=layout_value_snapshot(
                page.host_box.layout,
                ("width", "height", "display", "overflow"),
            ),
        )
        self._apply_active_page_visibility()

    def attach_view_widget(self, view_id: str, widget: widgets.Widget) -> None:
        """Attach ``widget`` to the persistent page for ``view_id``.
        
        Full API
        --------
        ``obj.attach_view_widget(view_id: str, widget: widgets.Widget) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        widget : widgets.Widget
            Widget/control instance associated with this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.attach_view_widget(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        key = str(view_id)
        if key in self._view_pages:
            title = self._view_pages[key].title
        else:
            title = key
        self.ensure_view_page(key, title=title)
        page = self._view_pages[key]
        attached_widget: widgets.Widget
        if isinstance(widget, widgets.Widget):
            attached_widget = widget
        else:
            fallback = widgets.Output(
                layout=build_layout(
                    width="100%",
                    height="100%",
                    min_width="0",
                    min_height="0",
                    overflow="hidden",
                )
            )
            add_class = getattr(fallback, "add_class", None)
            if callable(add_class):
                add_class("gu-figure-view-fallback-output")
            try:
                with fallback:
                    clear_output(wait=True)
                    display(widget)
            except Exception:
                pass
            attached_widget = fallback
        page.widget = attached_widget
        page.host_box.children = (attached_widget,)
        self._emit_layout_event("view_widget_attached", phase="completed", view_id=view_id, widget_type=type(widget).__name__)

    def remove_view_page(self, view_id: str) -> None:
        """Remove page bookkeeping for ``view_id`` if present.
        
        Full API
        --------
        ``obj.remove_view_page(view_id: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.remove_view_page(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        key = str(view_id)
        previous_order = self._ordered_view_ids
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
        if self._ordered_view_ids != previous_order:
            self._emit_layout_event(
                "view_order_changed",
                phase="completed",
                ordered_view_ids=list(self._ordered_view_ids),
            )
        self._emit_layout_event("view_page_removed", phase="completed", view_id=view_id)
        self._apply_active_page_visibility()

    def set_view_order(self, view_ids: Sequence[str]) -> None:
        """Set the visual order of registered view pages.
        
        Full API
        --------
        ``obj.set_view_order(view_ids: Sequence[str]) -> None``
        
        Parameters
        ----------
        view_ids : Sequence[str]
            Collection of view identifiers associated with this object or update. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_view_order(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
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
        """Show only the active view page and sync selector selection.
        
        Full API
        --------
        ``obj.set_active_view(view_id: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_active_view(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        key = str(view_id)
        if key not in self._view_pages:
            raise KeyError(f"Unknown view page: {key}")
        self._active_view_id = key
        self._apply_active_page_visibility()
        self._sync_view_selector_widget(selected_value=key)

    def set_view_title(self, view_id: str, title: str) -> None:
        """Update the selector title for ``view_id``.
        
        Full API
        --------
        ``obj.set_view_title(view_id: str, title: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        title : str
            Human-readable title text shown in the UI or stored in snapshots. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_view_title(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        page = self._view_pages.get(str(view_id))
        if page is None:
            return
        page.title = str(title)
        self._refresh_view_selector()

    def observe_view_selection(self, callback: Callable[[str], None]) -> None:
        """Call ``callback`` whenever the selector chooses a new view.
        
        Full API
        --------
        ``obj.observe_view_selection(callback: Callable[[str], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[str], None]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.observe_view_selection(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        self._view_selection_observers.append(callback)

    def observe_full_width_change(self, callback: Callable[[bool], None]) -> None:
        """Observe full-width layout toggle changes.
        
        Full API
        --------
        ``obj.observe_full_width_change(callback: Callable[[bool], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[bool], None]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.observe_full_width_change(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        def _on_full_width(change: dict[str, Any]) -> None:
            callback(bool(change.get("new")))

        self.full_width_checkbox.observe(_on_full_width, names="value")

    def bind_view_reflow(self, callback: Callable[[str, str], Any]) -> None:
        """Register a callback used by compatibility reflow wrappers.
        
        Full API
        --------
        ``obj.bind_view_reflow(callback: Callable[[str, str], Any]) -> None``
        
        Parameters
        ----------
        callback : Callable[[str, str], Any]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.bind_view_reflow(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        self._reflow_callback = callback

    @property
    def content_layout_mode(self) -> str:
        """Return the current high-level content layout mode.
        
        Full API
        --------
        ``obj.content_layout_mode -> str``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            current = obj.content_layout_mode
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        return self._content_layout_mode

    # ------------------------------------------------------------------
    # Compatibility wrappers kept for one refactor cycle.
    # ------------------------------------------------------------------

    def set_plot_widget(
        self,
        widget: widgets.Widget,
        *,
        reflow_callback: Callable[[], None] | None = None,
    ) -> None:
        """Set plot widget.
        
        Full API
        --------
        ``obj.set_plot_widget(widget: widgets.Widget, *, reflow_callback: Callable[[], None] | None=None) -> None``
        
        Parameters
        ----------
        widget : widgets.Widget
            Widget/control instance associated with this API. Required.
        
        reflow_callback : Callable[[], None] | None, optional
            Value for ``reflow_callback`` in this API. Defaults to ``None``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``reflow_callback=None``: Value for ``reflow_callback`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_plot_widget(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        if reflow_callback is not None:
            self.bind_view_reflow(lambda _view_id, _reason: reflow_callback())
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
        """Set view plot widget.
        
        Full API
        --------
        ``obj.set_view_plot_widget(view_id: str, widget: widgets.Widget, *, reflow_callback: Callable[[], None] | None=None) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        widget : widgets.Widget
            Widget/control instance associated with this API. Required.
        
        reflow_callback : Callable[[], None] | None, optional
            Value for ``reflow_callback`` in this API. Defaults to ``None``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``reflow_callback=None``: Value for ``reflow_callback`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_view_plot_widget(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        if reflow_callback is not None:
            self.bind_view_reflow(lambda _view_id, _reason: reflow_callback())
        self.ensure_view_page(str(view_id), str(view_id))
        self.attach_view_widget(str(view_id), widget)

    def set_view_tabs(self, view_ids: Sequence[str], *, active_view_id: str) -> None:
        """Set view tabs.
        
        Full API
        --------
        ``obj.set_view_tabs(view_ids: Sequence[str], *, active_view_id: str) -> None``
        
        Parameters
        ----------
        view_ids : Sequence[str]
            Collection of view identifiers associated with this object or update. Required.
        
        active_view_id : str
            Identifier for the currently selected view. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_view_tabs(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        self.set_view_order(view_ids)
        self.set_active_view(active_view_id)

    def trigger_reflow_for_view(self, view_id: str) -> None:
        """Work with trigger reflow for view on ``FigureLayout``.
        
        Full API
        --------
        ``obj.trigger_reflow_for_view(view_id: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.trigger_reflow_for_view(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        key = str(view_id)
        if self._reflow_callback is None:
            self._emit_layout_event(
                "reflow_callback_missing",
                phase="skipped",
                view_id=key,
                reason="compatibility_reflow",
            )
            return None
        self._emit_layout_event(
            "reflow_callback_invoked",
            phase="requested",
            view_id=key,
            reason="compatibility_reflow",
        )
        self._reflow_callback(key, "compatibility_reflow")
        return None

    def observe_tab_selection(self, callback: Callable[[str], None]) -> None:
        """Observe tab selection.
        
        Full API
        --------
        ``obj.observe_tab_selection(callback: Callable[[str], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[str], None]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.observe_tab_selection(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        self.observe_view_selection(callback)

    # ------------------------------------------------------------------
    # Internal helpers.
    # ------------------------------------------------------------------

    def _build_sidebar_region(self, *, side: str) -> widgets.VBox:
        padding = "0px 10px 0px 0px" if side == "left" else "0px 0px 0px 10px"
        box = widgets.VBox(
            [],
            layout=build_layout(
                margin="0px",
                padding=padding,
                flex="0 1 380px",
                min_width="260px",
                max_width="400px",
                display="none",
                overflow_x="hidden",
                overflow_y="auto",
                box_sizing="border-box",
            ),
        )
        box.add_class("gu-figure-sidebar")
        box.add_class(f"gu-figure-sidebar-{side}")
        box.add_class("gu-figure-context-governed")
        return box

    def _build_bottom_region(self) -> widgets.VBox:
        box = widgets.VBox(
            [],
            layout=build_layout(
                width="100%",
                min_width="0",
                margin="0px",
                padding="0px",
                display="none",
                gap="8px",
            ),
        )
        box.add_class("gu-figure-bottom-region")
        box.add_class("gu-figure-context-governed")
        return box

    def _set_children_if_changed(
        self,
        host: widgets.Box,
        children: Sequence[widgets.Widget],
    ) -> None:
        desired = tuple(children)
        if tuple(host.children) != desired:
            host.children = desired

    def _set_display_if_changed(self, widget: widgets.Widget, display: str) -> None:
        layout = getattr(widget, "layout", None)
        if layout is None:
            return
        if getattr(layout, "display", None) != display:
            layout.display = display

    def _section_panel_for_id(self, section_id: str) -> widgets.Widget:
        mapping = {
            "legend": self.legend_panel.panel,
            "parameters": self.params_panel.panel,
            "info": self.info_panel.panel,
        }
        if section_id not in mapping:
            raise KeyError(f"Unknown shell section id: {section_id}")
        return mapping[section_id]

    def _build_shell_page_button(self, page_spec: _ShellPageSpec) -> widgets.Button:
        button = widgets.Button(description=page_spec.title, tooltip=page_spec.title)
        configure_action_button(
            button,
            variant="tab",
            min_width_px=88,
            extra_classes=("gu-figure-shell-tab",),
        )
        button.on_click(
            lambda _button, page_id=page_spec.page_id: self._set_active_shell_page(
                page_id,
                reason="shell_page_selection",
            )
        )
        return button

    def _build_shell_page_state(self, page_spec: _ShellPageSpec) -> _ShellPageState:
        if page_spec.include_stage:
            left_box = self.left_sidebar_container
            center_box = self.left_panel
            right_box = self.sidebar_container
            row_box = self.content_wrapper
            bottom_box = self.bottom_section_container
        else:
            left_box = self._build_sidebar_region(side="left")
            center_box = widgets.VBox(
                [],
                layout=build_layout(
                    width="100%",
                    min_width="0",
                    flex="1 1 560px",
                    margin="0px",
                    padding="0px",
                    display="flex",
                    gap="8px",
                ),
            )
            center_box.add_class("gu-figure-left-panel")
            center_box.add_class("gu-figure-shell-main-region")
            row_box = widgets.Box(
                [],
                layout=build_layout(
                    display="flex",
                    flex_flow="row wrap",
                    align_items="stretch",
                    width="100%",
                    min_width="0",
                    min_height="0",
                    gap="8px",
                ),
            )
            row_box.add_class("gu-figure-content")
            right_box = self._build_sidebar_region(side="right")
            bottom_box = self._build_bottom_region()

        host_box = widgets.VBox(
            [row_box, bottom_box],
            layout=build_layout(
                width="100%",
                min_width="0",
                margin="0px",
                padding="0px",
                gap="8px",
                display="none",
            ),
        )
        host_box.add_class("gu-figure-shell-page")
        host_box.add_class("gu-figure-shell-page-panel")
        host_box.add_class("gu-tab-panel")
        host_box.add_class(f"gu-figure-shell-page-{page_spec.page_id}")

        tab_button = (
            self._build_shell_page_button(page_spec)
            if len(self._shell_spec.pages) > 1
            else None
        )
        return _ShellPageState(
            spec=page_spec,
            host_box=host_box,
            row_box=row_box,
            center_box=center_box,
            left_box=left_box,
            right_box=right_box,
            bottom_box=bottom_box,
            tab_button=tab_button,
        )

    def _rebuild_shell_arrangement(self) -> None:
        pages = tuple(self._shell_spec.pages)
        self._shell_pages = {}
        self._shell_page_buttons = {}
        self._ordered_shell_page_ids = tuple(page.page_id for page in pages)
        page_hosts: list[widgets.Widget] = []
        content_rows: list[widgets.Box] = []
        center_boxes: list[widgets.VBox] = []
        sidebar_slots: list[widgets.VBox] = []

        stage_page_count = 0
        for page_spec in pages:
            page_state = self._build_shell_page_state(page_spec)
            stage_page_count += 1 if page_spec.include_stage else 0
            self._shell_pages[page_spec.page_id] = page_state
            page_hosts.append(page_state.host_box)
            content_rows.append(page_state.row_box)
            center_boxes.append(page_state.center_box)
            sidebar_slots.extend((page_state.left_box, page_state.right_box))
            if page_state.tab_button is not None:
                self._shell_page_buttons[page_spec.page_id] = page_state.tab_button

            if page_spec.include_stage:
                stage_children: tuple[widgets.Widget, ...]
                stage_children = (
                    (self.view_selector, self.view_stage)
                    if page_spec.include_navigation
                    else (self.view_stage,)
                )
                self._set_children_if_changed(self.left_panel, stage_children)
                self._set_children_if_changed(page_state.center_box, stage_children)
            else:
                self._set_children_if_changed(
                    page_state.center_box,
                    tuple(
                        self._section_panel_for_id(section_id)
                        for section_id in page_spec.main_sections
                    ),
                )

            self._set_children_if_changed(
                page_state.left_box,
                tuple(
                    self._section_panel_for_id(section_id)
                    for section_id in page_spec.left_sections
                ),
            )
            self._set_children_if_changed(
                page_state.right_box,
                tuple(
                    self._section_panel_for_id(section_id)
                    for section_id in page_spec.right_sections
                ),
            )
            self._set_children_if_changed(
                page_state.bottom_box,
                tuple(
                    self._section_panel_for_id(section_id)
                    for section_id in page_spec.bottom_sections
                ),
            )

            row_children: list[widgets.Widget] = []
            if page_spec.left_sections:
                row_children.append(page_state.left_box)
            row_children.append(page_state.center_box)
            if page_spec.right_sections:
                row_children.append(page_state.right_box)
            self._set_children_if_changed(page_state.row_box, tuple(row_children))

        if stage_page_count != 1:
            raise ValueError(
                f"Shell preset {self._shell_spec.name!r} must define exactly one stage page."
            )

        self._content_rows = tuple(content_rows)
        self._center_boxes = tuple(center_boxes)
        self._sidebar_slots = tuple(sidebar_slots)
        self._set_children_if_changed(self.shell_page_content, tuple(page_hosts))
        if self._active_shell_page_id not in self._ordered_shell_page_ids:
            self._active_shell_page_id = self._shell_spec.default_page_id
        self._apply_shell_visibility()
        self._apply_content_layout_mode(is_full=bool(self.full_width_checkbox.value))
        self._emit_layout_event(
            "shell_arrangement_applied",
            phase="completed",
            shell_preset=self._shell_spec.name,
            shell_pages=[page.page_id for page in pages],
            active_shell_page_id=self._active_shell_page_id,
        )

    def _available_shell_page_ids(self) -> tuple[str, ...]:
        visible: list[str] = []
        for page_spec in self._shell_spec.pages:
            if page_spec.include_stage or any(
                self._section_visibility.get(section_id, False)
                for section_id in page_spec._all_sections()
            ):
                visible.append(page_spec.page_id)
        return tuple(visible)

    def _sync_shell_page_tabs(self) -> None:
        visible_ids = self._visible_shell_page_ids
        if len(visible_ids) > 1:
            children = tuple(
                self._shell_page_buttons[page_id]
                for page_id in visible_ids
                if page_id in self._shell_page_buttons
            )
            self._set_children_if_changed(self.shell_page_bar, children)
            self.shell_page_tabs.layout.display = "flex"
        else:
            self._set_children_if_changed(self.shell_page_bar, ())
            self.shell_page_tabs.layout.display = "none"

        for page_id, button in self._shell_page_buttons.items():
            set_tab_button_selected(button, page_id == self._active_shell_page_id)

        if self._visible_shell_page_ids and self._active_shell_page_id in self._visible_shell_page_ids:
            selected_index = self._visible_shell_page_ids.index(self._active_shell_page_id)
        else:
            selected_index = 0
        self._shell_page_bridge.selected_index = int(selected_index)

    def _apply_shell_visibility(self) -> None:
        self._visible_shell_page_ids = self._available_shell_page_ids()
        if self._active_shell_page_id not in self._visible_shell_page_ids:
            self._active_shell_page_id = (
                self._visible_shell_page_ids[0] if self._visible_shell_page_ids else None
            )

        active_sections: set[str] = set()
        for page_id, page_state in self._shell_pages.items():
            spec = page_state.spec
            page_available = page_id in self._visible_shell_page_ids
            page_active = page_available and page_id == self._active_shell_page_id

            left_visible = page_available and any(
                self._section_visibility.get(section_id, False)
                for section_id in spec.left_sections
            )
            center_visible = page_available and (
                spec.include_stage
                or any(
                    self._section_visibility.get(section_id, False)
                    for section_id in spec.main_sections
                )
            )
            right_visible = page_available and any(
                self._section_visibility.get(section_id, False)
                for section_id in spec.right_sections
            )
            bottom_visible = page_available and any(
                self._section_visibility.get(section_id, False)
                for section_id in spec.bottom_sections
            )

            self._set_display_if_changed(page_state.left_box, "flex" if left_visible else "none")
            self._set_display_if_changed(page_state.center_box, "flex" if center_visible else "none")
            self._set_display_if_changed(page_state.right_box, "flex" if right_visible else "none")
            self._set_display_if_changed(page_state.bottom_box, "flex" if bottom_visible else "none")
            self._set_display_if_changed(
                page_state.row_box,
                "flex" if (left_visible or center_visible or right_visible) else "none",
            )
            self._set_display_if_changed(page_state.host_box, "flex" if page_active else "none")
            if page_active:
                active_sections.update(spec._all_sections())

        params_visible = self._section_visibility.get("parameters", False) and "parameters" in active_sections
        info_visible = self._section_visibility.get("info", False) and "info" in active_sections
        legend_visible = self._section_visibility.get("legend", False) and "legend" in active_sections

        self.params_header.layout.display = "block" if params_visible else "none"
        self.params_panel.panel.layout.display = "flex" if params_visible else "none"
        self.info_header.layout.display = "block" if info_visible else "none"
        self.info_panel.panel.layout.display = "flex" if info_visible else "none"
        self.legend_header.layout.display = "none"
        self.legend_panel.panel.layout.display = "flex" if legend_visible else "none"

        self._sync_shell_page_tabs()

    def _set_active_shell_page(self, page_id: str, *, reason: str) -> None:
        key = str(page_id)
        if key not in self._visible_shell_page_ids or key == self._active_shell_page_id:
            return
        self._active_shell_page_id = key
        self._apply_shell_visibility()
        self._emit_layout_event(
            "shell_page_selected",
            phase="completed",
            page_id=key,
            available_shell_pages=list(self._visible_shell_page_ids),
        )
        self._request_active_shell_reflow(reason)

    def _request_active_shell_reflow(self, reason: str) -> None:
        if self._reflow_callback is None:
            self._emit_layout_event(
                "reflow_callback_missing",
                phase="skipped",
                reason=reason,
                active_shell_page_id=self._active_shell_page_id,
            )
            return
        if self._active_view_id is None:
            self._emit_layout_event(
                "shell_reflow_skipped",
                phase="skipped",
                reason=reason,
                active_shell_page_id=self._active_shell_page_id,
            )
            return
        active_page = self._shell_pages.get(self._active_shell_page_id or "")
        if active_page is None or not active_page.spec.include_stage:
            self._emit_layout_event(
                "shell_reflow_skipped",
                phase="skipped",
                reason=reason,
                active_shell_page_id=self._active_shell_page_id,
            )
            return
        self._emit_layout_event(
            "reflow_callback_invoked",
            phase="requested",
            view_id=self._active_view_id,
            reason=reason,
            active_shell_page_id=self._active_shell_page_id,
        )
        self._reflow_callback(self._active_view_id, reason)

    def _shell_display_state(self) -> tuple[Any, ...]:
        page_states = tuple(
            (
                page_id,
                state.host_box.layout.display,
                state.row_box.layout.display,
                state.left_box.layout.display,
                state.center_box.layout.display,
                state.right_box.layout.display,
                state.bottom_box.layout.display,
            )
            for page_id, state in self._shell_pages.items()
        )
        section_states = (
            self.params_header.layout.display,
            self.params_panel.panel.layout.display,
            self.info_header.layout.display,
            self.info_panel.panel.layout.display,
            self.legend_panel.panel.layout.display,
            self.left_sidebar_container.layout.display,
            self.sidebar_container.layout.display,
            self.bottom_section_container.layout.display,
            self.shell_page_tabs.layout.display,
            self._active_shell_page_id,
            self._visible_shell_page_ids,
        )
        return (section_states, page_states)

    def _on_view_selector_change(self, change: dict[str, Any]) -> None:
        if self._suspend_view_selector_events:
            return
        new_value = change.get("new")
        if new_value is None:
            return
        key = str(new_value)
        valid_values = {value for _, value in self._view_selector_items}
        if key not in valid_values or key == self._active_view_id:
            return
        self._active_view_id = key
        self._apply_active_page_visibility()
        for callback in tuple(self._view_selection_observers):
            callback(key)

    def _sync_view_selector_widget(self, *, selected_value: str | None) -> None:
        valid_values = {value for _, value in self._view_selector_items}
        desired = selected_value if selected_value in valid_values else None
        if desired is None and self._active_view_id in valid_values:
            desired = self._active_view_id
        if desired is None and self._view_selector_items:
            desired = self._view_selector_items[0][1]
        self._suspend_view_selector_events = True
        try:
            self.view_selector.options = self._view_selector_items
            self.view_selector.layout.display = (
                "flex" if len(self._view_selector_items) > 1 else "none"
            )
            if self.view_selector.value != desired:
                self.view_selector.value = desired
            elif desired is None and self.view_selector.value is not None:
                self.view_selector.value = None
        finally:
            self._suspend_view_selector_events = False
        self._active_view_id = desired

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
        options = tuple(
            (self._view_pages[view_id].title, view_id)
            for view_id in self._ordered_view_ids
            if view_id in self._view_pages
        )
        self._view_selector_items = tuple(
            (str(label), str(value)) for label, value in options
        )
        self._sync_view_selector_widget(selected_value=self._active_view_id)
        self._emit_layout_event(
            "view_selector_refreshed",
            phase="completed",
            options=[value for _, value in self._view_selector_items],
            selector_display=self.view_selector.layout.display,
            active_view_id=self._active_view_id,
        )

    def _apply_content_layout_mode(self, *, is_full: bool) -> None:
        if is_full:
            self._content_layout_mode = "stacked"
            row_flow = "column"
            center_flex = "0 0 auto"
            sidebar_flex = "0 0 auto"
            sidebar_max_width = ""
            sidebar_width = "100%"
        else:
            self._content_layout_mode = "wrapped"
            row_flow = "row wrap"
            center_flex = "1 1 560px"
            sidebar_flex = "0 1 380px"
            sidebar_max_width = "400px"
            sidebar_width = "auto"

        for row_box in self._content_rows:
            row_box.layout.flex_flow = row_flow
        for center_box in self._center_boxes:
            center_box.layout.flex = center_flex
        for sidebar_box in self._sidebar_slots:
            sidebar_box.layout.flex = sidebar_flex
            sidebar_box.layout.max_width = sidebar_max_width
            sidebar_box.layout.width = sidebar_width
            if is_full:
                sidebar_box.layout.padding = "0px"
            elif "gu-figure-sidebar-left" in getattr(sidebar_box, "_dom_classes", ()):
                sidebar_box.layout.padding = "0px 10px 0px 0px"
            else:
                sidebar_box.layout.padding = "0px 0px 0px 10px"

    def _on_full_width_change(self, change: dict[str, Any]) -> None:
        is_full = bool(change["new"])
        self._apply_content_layout_mode(is_full=is_full)
        layout = self.content_wrapper.layout
        plot_layout = self.left_panel.layout
        sidebar_layout = self.sidebar_container.layout
        left_sidebar_layout = self.left_sidebar_container.layout
        self._emit_layout_event(
            "full_width_layout_changed",
            phase="completed",
            is_full=is_full,
            layout_mode=self._content_layout_mode,
            content_wrapper=layout_value_snapshot(layout, ("display", "flex_flow", "gap")),
            left_panel=layout_value_snapshot(plot_layout, ("width", "min_width", "flex")),
            left_sidebar=layout_value_snapshot(left_sidebar_layout, ("display", "flex", "max_width", "width", "padding")),
            sidebar=layout_value_snapshot(sidebar_layout, ("display", "flex", "max_width", "width", "padding")),
        )
