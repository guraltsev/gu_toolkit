"""Figure layout primitives.

This module builds the notebook widget tree used by :class:`Figure`.

Project 019 phase 3 adds a lightweight tab selector that allows the figure to
switch between multiple logical views while preserving the existing one-view
layout behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import ipywidgets as widgets
from IPython.display import display

# SECTION: OneShotOutput [id: OneShotOutput]
# =============================================================================


class OneShotOutput(widgets.Output):
    """
    A specialized Output widget that can only be displayed once.

    Why this exists
    ---------------
    In Jupyter, widgets are *live objects* connected to the frontend by a comm channel.
    If you display the same widget instance multiple times, it is easy to end up with
    confusing UI behavior (e.g., “Which copy should update?”, “Why did output appear
    in two places?”, etc.).

    ``OneShotOutput`` prevents accidental duplication by raising an error on the
    second display attempt.

    What counts as “display”?
    -------------------------
    Any of the following will count as displaying the widget:
    - having it be the last expression in a cell,
    - calling ``display(output)``,
    - placing it inside another widget/layout that is displayed.

     Attributes
    ----------
    _displayed : bool
        Internal flag tracking whether the widget has been displayed.

      Examples
    --------
    Basic output usage:

    >>> out = OneShotOutput()
    >>> with out:
    ...     print("Hello from inside the Output widget!")
    >>> out  # first display works

    Attempting to display again raises:

    >>> out  # doctest: +SKIP
    RuntimeError: OneShotOutput has already been displayed...

    Use case: preventing accidental double-display:

    >>> out = OneShotOutput()
    >>> with out:
    ...     print("I only want this shown once.")
    >>> display(out)  # ok
    >>> display(out)  # raises RuntimeError

    If you *really* need to display it again (advanced / use with caution),
    you can reset:

    >>> out.reset_display_state()
    >>> display(out)  # now allowed again

    (See ``reset_display_state`` for warnings.)
    """

    __slots__ = ("_displayed",)

    def __init__(self) -> None:
        """Initialize a new OneShotOutput widget.

        Returns
        -------
        None

        Examples
        --------
        >>> out = OneShotOutput()  # doctest: +SKIP
        >>> out.has_been_displayed
        False

        Notes
        -----
        Use :meth:`reset_display_state` only if you intentionally want to reuse
        the same widget instance across multiple displays.
        """
        super().__init__()
        self._displayed = False

    def _repr_mimebundle_(
        self, include: Any = None, exclude: Any = None, **kwargs: Any
    ) -> Any:
        """
        IPython rich display hook used by ipywidgets.

        This is what gets called when the widget is displayed (including via
        `display(self)` or by being the last expression in a cell).

        Parameters
        ----------
        include : Any, optional
            MIME types to include, forwarded to the base widget.
        exclude : Any, optional
            MIME types to exclude, forwarded to the base widget.
        **kwargs : Any
            Additional arguments passed to ``ipywidgets.Output``.

        Returns
        -------
        Any
            The rich display representation.

        Notes
        -----
        This method is invoked automatically by IPython during display; users
        should not call it directly. See :meth:`reset_display_state` if you need
        to re-display the widget intentionally.
        """
        if self._displayed:
            raise RuntimeError(
                "OneShotOutput has already been displayed. "
                "This widget supports only one-time display."
            )
        self._displayed = True
        return super()._repr_mimebundle_(include=include, exclude=exclude, **kwargs)

    @property
    def has_been_displayed(self) -> bool:
        """
        Check if the widget has been displayed.

        Returns
        -------
        bool
            True if the widget has been displayed, False otherwise.

        Examples
        --------
        >>> out = OneShotOutput()  # doctest: +SKIP
        >>> out.has_been_displayed
        False

        Notes
        -----
        This is a read-only convenience property; use
        :meth:`reset_display_state` to clear the flag.
        """
        return self._displayed

    def reset_display_state(self) -> None:
        """
        Reset the display state to allow re-display.

        Warning
        -------
        This method should be used with caution as it bypasses the
        one-time display protection.

        Returns
        -------
        None

        Examples
        --------
        >>> out = OneShotOutput()  # doctest: +SKIP
        >>> out.reset_display_state()

        See Also
        --------
        has_been_displayed : Check whether the widget has already been displayed.
        """
        self._displayed = False


# =============================================================================
# SECTION: FigureLayout (The View) [id: FigureLayout]
# =============================================================================


class FigureLayout:
    """
    Manages the visual structure and widget hierarchy of a Figure.

    This class isolates all the "messy" UI code (CSS strings, JavaScript injection,
    VBox/HBox nesting) from the mathematical logic.

    Responsibilities:
    - Building the HBox/VBox structure.
    - Providing the plot container and layout toggles.
    - Exposing containers for Plots, Parameters, and Info.
    - Handling layout toggles (e.g. full width, sidebar visibility).
    """

    def __init__(self, title: str = "") -> None:
        """Initialize the layout manager and build the widget tree.

        Parameters
        ----------
        title : str, optional
            Initial title text (rendered as HTML/LaTeX in the header).

        Returns
        -------
        None

        Examples
        --------
        >>> layout = FigureLayout(title="My Plot")  # doctest: +SKIP
        >>> layout.get_title()  # doctest: +SKIP
        'My Plot'

        Notes
        -----
        This class focuses on widget composition; :class:`Figure` handles
        plotting logic and parameter updates.
        """
        self._reflow_callback: Callable[[], None] | None = None
        self._view_reflow_callbacks: dict[str, Callable[[], None]] = {}
        self._tab_view_ids: tuple[str, ...] = ()
        self._suspend_tab_events = False
        self._view_plot_widgets: dict[str, widgets.Widget] = {}

        # 1. Title Bar
        #    We use HTMLMath for proper LaTeX title rendering.
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

        # 2. Plot Area (The "Left" Panel)
        #    Ensure a real pixel height for Plotly sizing.
        self.plot_container = widgets.Box(
            children=(),
            layout=widgets.Layout(
                width="100%",
                height="60vh",
                min_width="320px",
                min_height="260px",
                margin="0px",
                padding="0px",
                flex="1 1 560px",
            ),
        )
        self.view_tabs = widgets.Tab(
            children=(),
            selected_index=None,
            layout=widgets.Layout(display="none", width="100%", margin="0 0 6px 0"),
        )

        # 3. Controls Sidebar (The "Right" Panel)
        #    Initially hidden (display="none") until parameters/info/legend widgets are added.
        self.params_header = widgets.HTML(
            "<b>Parameters</b>", layout=widgets.Layout(display="none", margin="0")
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
            "<b>Legend</b>", layout=widgets.Layout(display="none", margin="10px 0 0 0")
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
                self.params_header,
                self.params_box,
                self.info_header,
                self.info_box,
                self.legend_header,
                self.legend_box,
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

        # 4. Main Content Wrapper (Flex)
        #    Uses flex-wrap so the sidebar drops below the plot on narrow screens.
        self.left_panel = widgets.VBox(
            [self.view_tabs, self.plot_container],
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

        # 4.5. Default print/output area (below the entire figure content)
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

        # 5. Root Widget
        self.root_widget = widgets.VBox(
            [self._titlebar, self.content_wrapper, self.print_area],
            layout=widgets.Layout(width="100%", position="relative"),
        )

        # Wire up internal logic
        self.full_width_checkbox.observe(self._on_full_width_change, names="value")

    @property
    def output_widget(self) -> OneShotOutput:
        """Return a OneShotOutput wrapping the layout, ready for display.

        Returns
        -------
        OneShotOutput
            A display-ready output widget containing the layout.

        Examples
        --------
        >>> layout = FigureLayout()  # doctest: +SKIP
        >>> out = layout.output_widget  # doctest: +SKIP

        See Also
        --------
        OneShotOutput : Prevents accidental multiple display of the same widget.
        """
        out = OneShotOutput()
        with out:
            display(self.root_widget)
        return out

    def set_title(self, text: str) -> None:
        """Set the title text shown above the plot.

        Parameters
        ----------
        text : str
            Title text (HTML/LaTeX supported).

        Returns
        -------
        None

        Examples
        --------
        >>> layout = FigureLayout()  # doctest: +SKIP
        >>> layout.set_title("Demo")  # doctest: +SKIP

        See Also
        --------
        get_title : Retrieve the current title.
        """
        self.title_html.value = text

    def get_title(self) -> str:
        """Get the current title text.

        Returns
        -------
        str
            The current title string.

        Examples
        --------
        >>> layout = FigureLayout(title="Demo")  # doctest: +SKIP
        >>> layout.get_title()  # doctest: +SKIP
        'Demo'

        See Also
        --------
        set_title : Update the title text.
        """
        return self.title_html.value

    def update_sidebar_visibility(
        self, has_params: bool, has_info: bool, has_legend: bool
    ) -> None:
        """
        Updates visibility of headers and the sidebar itself based on content.

        This prevents empty "Parameters" or "Info" headers from cluttering the UI.

        Parameters
        ----------
        has_params : bool
            Whether parameter sliders exist.
        has_info : bool
            Whether info outputs exist.
        has_legend : bool
            Whether legend rows exist.

        Returns
        -------
        None

        Examples
        --------
        >>> layout = FigureLayout()  # doctest: +SKIP
        >>> layout.update_sidebar_visibility(has_params=True, has_info=False, has_legend=False)  # doctest: +SKIP

        Notes
        -----
        Call this after adding or removing parameters/info outputs to ensure the
        UI reflects the current state.
        """
        self.params_header.layout.display = "block" if has_params else "none"
        self.params_box.layout.display = "flex" if has_params else "none"

        self.info_header.layout.display = "block" if has_info else "none"
        self.info_box.layout.display = "flex" if has_info else "none"

        self.legend_header.layout.display = "block" if has_legend else "none"
        self.legend_box.layout.display = "flex" if has_legend else "none"

        show_sidebar = has_params or has_info or has_legend
        self.sidebar_container.layout.display = "flex" if show_sidebar else "none"

    def set_plot_widget(
        self,
        widget: widgets.Widget,
        *,
        reflow_callback: Callable[[], None] | None = None,
    ) -> None:
        """Attach the plot widget to the layout and store a reflow callback.

        Parameters
        ----------
        widget : ipywidgets.Widget
            The plot widget to display.
        reflow_callback : callable, optional
            Callback to trigger when layout changes (e.g., full-width toggle).

        Returns
        -------
        None

        Examples
        --------
        >>> layout = FigureLayout()  # doctest: +SKIP
        >>> dummy = widgets.Box()  # doctest: +SKIP
        >>> layout.set_plot_widget(dummy)  # doctest: +SKIP

        Notes
        -----
        The ``reflow_callback`` is typically used to notify Plotly of size
        changes when the sidebar toggles.
        """
        self.plot_container.children = (widget,)
        self._reflow_callback = reflow_callback
        self._sync_plot_container_host(
            active_view_id=self._tab_view_ids[0] if self._tab_view_ids else None
        )

    def set_view_plot_widget(
        self,
        view_id: str,
        widget: widgets.Widget,
        *,
        reflow_callback: Callable[[], None] | None = None,
    ) -> None:
        """Attach a plot widget to a specific view tab.

        Parameters
        ----------
        view_id : str
            View identifier that should own the widget.
        widget : ipywidgets.Widget
            Plot widget to place inside the view tab content area.
        reflow_callback : callable, optional
            Reflow callback for this specific view.
        """
        view_key = str(view_id)
        self._view_plot_widgets[view_key] = widget
        if reflow_callback is not None:
            self._view_reflow_callbacks[view_key] = reflow_callback
        if len(self._tab_view_ids) <= 1:
            self.plot_container.children = (widget,)
        self._sync_plot_container_host(active_view_id=view_key)

    def set_view_tabs(self, view_ids: Sequence[str], *, active_view_id: str) -> None:
        """Configure the optional view-tab selector.

        Parameters
        ----------
        view_ids : sequence[str]
            Ordered list of view identifiers.
        active_view_id : str
            Identifier that should be selected.
        """
        labels = tuple(str(v) for v in view_ids)
        previous_labels = self._tab_view_ids
        self._tab_view_ids = labels
        self._suspend_tab_events = True
        try:
            if len(labels) <= 1:
                self.view_tabs.children = ()
                self.view_tabs.selected_index = None
                self.view_tabs.layout.display = "none"
                self.plot_container.layout.display = "flex"
                return

            # Rebuild tab children only when the tab set actually changes.
            # Recreating children on every selection change can reset the
            # underlying widget state and spuriously bounce selection back.
            if labels != previous_labels:
                children = []
                for view_id in labels:
                    child = widgets.Box(layout=widgets.Layout(width="100%"))
                    widget = self._view_plot_widgets.get(view_id)
                    if widget is not None:
                        child.children = (widget,)
                    children.append(child)
                self.view_tabs.children = tuple(children)
                for idx, view_id in enumerate(labels):
                    self.view_tabs.set_title(idx, view_id)

            self.view_tabs.layout.display = "flex"
            self.plot_container.layout.display = "none"
            self.view_tabs.selected_index = labels.index(active_view_id)
            self._sync_plot_container_host(active_view_id=active_view_id)
        finally:
            self._suspend_tab_events = False

    def _sync_plot_container_host(self, *, active_view_id: str | None) -> None:
        """Place plot widgets in the appropriate host (single-view vs tabbed)."""
        if len(self._tab_view_ids) <= 1:
            self.plot_container.layout.display = "flex"
            return
        if active_view_id is None or active_view_id not in self._tab_view_ids:
            return
        for idx, child in enumerate(self.view_tabs.children):
            view_id = self._tab_view_ids[idx]
            widget = self._view_plot_widgets.get(view_id)
            child.children = (widget,) if widget is not None else ()

    def trigger_reflow_for_view(self, view_id: str) -> None:
        """Trigger the registered reflow callback for ``view_id`` if present."""
        callback = self._view_reflow_callbacks.get(str(view_id))
        if callback is not None:
            callback()

    def observe_tab_selection(self, callback: Callable[[str], None]) -> None:
        """Observe tab selection and call ``callback`` with the selected view id."""

        def _on_tab_change(change: dict[str, Any]) -> None:
            if self._suspend_tab_events:
                return
            index = change.get("new")
            if index is None:
                return
            if 0 <= int(index) < len(self._tab_view_ids):
                callback(self._tab_view_ids[int(index)])

        self.view_tabs.observe(_on_tab_change, names="selected_index")

    def _on_full_width_change(self, change: dict[str, Any]) -> None:
        """Toggle CSS flex properties for full-width mode.

        Parameters
        ----------
        change : dict
            Traitlets change dictionary from the checkbox.

        Returns
        -------
        None
        """
        is_full = change["new"]
        layout = self.content_wrapper.layout
        plot_layout = self.left_panel.layout
        sidebar_layout = self.sidebar_container.layout

        if is_full:
            # Stack vertically, full width
            layout.flex_flow = "column"
            plot_layout.flex = "0 0 auto"
            sidebar_layout.flex = "0 0 auto"
            sidebar_layout.max_width = ""
            sidebar_layout.width = "100%"
            sidebar_layout.padding = "0px"
        else:
            # Side-by-side (wrapping), restricted width for sidebar
            layout.flex_flow = "row wrap"
            plot_layout.flex = "1 1 560px"
            sidebar_layout.flex = "0 1 380px"
            sidebar_layout.max_width = "400px"
            sidebar_layout.width = "auto"
            sidebar_layout.padding = "0px 0px 0px 10px"
        if len(self._tab_view_ids) > 1 and self._tab_view_ids:
            active_idx = self.view_tabs.selected_index
            if active_idx is not None and 0 <= int(active_idx) < len(
                self._tab_view_ids
            ):
                self.trigger_reflow_for_view(self._tab_view_ids[int(active_idx)])
                return
        if self._reflow_callback is not None:
            self._reflow_callback()


# =============================================================================
