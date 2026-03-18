"""Interactive figure coordinator and public API hub.

Glossary
--------
Figure
    Top-level notebook object that coordinates layout, plots, parameters,
    info content, legends, views, snapshots, and code generation.
View
    Named plotting workspace inside one figure. Each public :class:`View`
    owns one stable Plotly widget runtime, its default axis ranges, remembered
    viewport, and axis labels.
Sidebar
    The optional right-hand panel that can show the toolkit legend,
    parameter controls, and the Info section.
Info section / info card
    The Info section is the sidebar area for explanatory content. An info card
    is a small rich-text block created with :meth:`Figure.info` or the
    module-level :func:`info` helper. Cards may be global or scoped to a
    specific view.
Current figure
    Thread-local routing target used by module-level helpers. ``with fig:``
    makes a figure current. ``with fig.views["detail"]:`` makes the figure
    current *and* activates that view for the duration of the block.
Module-level helpers
    Convenience functions from :mod:`gu_toolkit.figure_api` such as ``plot``,
    ``parameter``, ``info``, ``set_x_range``, and ``render``. They delegate to
    the current figure and current active view; they do not store independent
    plotting state.

Navigation map
--------------
- :mod:`gu_toolkit.figure_view` defines the public :class:`View` object and the
  :class:`FigureViews` facade.
- :mod:`gu_toolkit.figure_layout` owns widget composition only.
- :mod:`gu_toolkit.figure_plot` owns per-curve numeric sampling and trace
  updates.
- :mod:`gu_toolkit.figure_parameters` owns parameter controls and hooks.
- :mod:`gu_toolkit.figure_info` owns the Info section and info cards.
- :mod:`gu_toolkit.figure_legend` owns the toolkit sidebar legend.
- :mod:`gu_toolkit.FigureSnapshot` and :mod:`gu_toolkit.codegen` own
  reproducible state and source generation.

Logging
-------
Use Python's standard :mod:`logging` module rather than ``Figure(debug=...)``::

    import logging
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("gu_toolkit.layout").setLevel(logging.DEBUG)
"""

from __future__ import annotations

import logging
import time
import warnings
from collections.abc import Callable, Hashable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from typing import Any

import ipywidgets as widgets
import plotly.graph_objects as go
from IPython.display import display
from sympy.core.symbol import Symbol

from .codegen import CodegenOptions
from .layout_logging import (
    LayoutEventBuffer,
    is_layout_logger_explicitly_enabled,
    make_event_emitter,
    new_debug_id,
    new_request_id,
)
from .debouncing import QueuedDebouncer
from .figure_plot_normalization import PlotVarsSpec, normalize_plot_inputs
from .figure_plot_style import plot_style_option_docs, validate_style_kwargs
from .FigureSnapshot import FigureSnapshot, ViewSnapshot

from .InputConvert import InputConvert
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .PlotlyPane import PlotlyPane, PlotlyPaneStyle
from .figure_types import RangeLike, VisibleSpec

# Module logger
# - Uses a NullHandler so importing this module never configures global logging.
# - Callers can enable logs via standard logging configuration.
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


from .figure_context import (
    _FigureDefaultSentinel,
    _is_figure_default,
    _pop_current_figure,
    _push_current_figure,
    _use_figure,
    current_figure,  # noqa: F401 - re-exported for __init__.py
)
from .figure_info import InfoPanelManager
from .figure_layout import FigureLayout
from .figure_legend import LegendPanelManager
from .figure_parameters import ParameterManager
from .figure_plot import Plot
from .figure_view import FigureViews, View
from .figure_view_manager import ViewManager

# SECTION: Figure (The Coordinator) [id: Figure]
# =============================================================================
class Figure:
    """Notebook-facing coordinator for interactive plotting.

    ``Figure`` keeps high-level orchestration in one place while delegating
    specialized state and lifecycle logic to dedicated collaborators.

    Mental model
    ------------
    - ``fig.views["id"]`` returns the public :class:`View` object for one
      plotting workspace.
    - ``fig.views.current`` and ``fig.views.current_id`` are the canonical
      active-view accessors.
    - ``Figure.x_range`` and ``Figure.y_range`` are convenience shorthands for
      the current view, not figure-global axes.
    - :class:`FigureLayout` owns widget composition only; rendering decisions
      and relayout policy stay here in ``Figure``.
    - ``fig.info_manager`` is the advanced Info-section access point.
      ``fig.info(...)`` is the convenience API for small rich-text cards.

    Parameters
    ----------
    title : str, optional
        Figure title shown above the widget tree.
    sampling_points : int, optional
        Default sample count used when a plot does not set its own override.
    default_x_range, default_y_range : RangeLike, optional
        Initial default ranges seeded into the main view.
    x_label, y_label : str, optional
        Initial axis labels for the main view.
    show : bool, optional
        If ``True``, display immediately in IPython/Jupyter.
    display, x_range, y_range : optional
        Deprecated compatibility aliases accepted for one transition cycle.

    Attributes
    ----------
    plots : dict[str, Plot]
        Registry of plot objects keyed by plot id.
    views : FigureViews
        Mapping-like view facade with ``current`` / ``current_id`` helpers.
    parameters : ParameterManager
        Parameter manager used by sliders and plot evaluation.
    info_manager : InfoPanelManager
        Advanced access point for raw info outputs and info-card management.

    Notes
    -----
    ``Figure`` is intentionally a coordinator. Widget-building, parameter
    storage, and per-curve rendering each live in their own owner modules.
    """
    __slots__ = [
        "plots",
        "_layout",
        "_parameter_manager",
        "_info",
        "_legend",
        "_view_manager",
        "_views",
        "_sampling_points",
        "_render_info_last_log_t",
        "_render_debug_last_log_t",
        "_print_capture",
        "_context_depth",
        "_relayout_debouncer",
        "_pending_relayout_view_id",
        "_layout_debug_figure_id",
        "_layout_debug_enabled",
        "_layout_event_buffer",
        "_layout_event_emitter",
        "_layout_event_seq",
        "_has_been_displayed",
    ]

    def __init__(
        self,
        *,
        title: str = "",
        sampling_points: int = 500,
        default_x_range: RangeLike | None = None,
        default_y_range: RangeLike | None = None,
        x_label: str = "",
        y_label: str = "",
        show: bool = False,
        display: bool | None = None,
        x_range: RangeLike | None = None,
        y_range: RangeLike | None = None,
        **_deprecated_kwargs: Any,
    ) -> None:
        # Handle backwards-compatible keyword arguments that were removed from
        # the public constructor.

        def _same_range(lhs: RangeLike, rhs: RangeLike) -> bool:
            return tuple(lhs) == tuple(rhs)

        debug = bool(_deprecated_kwargs.pop("debug", False))
        default_view_id = _deprecated_kwargs.pop("default_view_id", None)
        plotly_legend_mode = _deprecated_kwargs.pop("plotly_legend_mode", None)
        if _deprecated_kwargs:
            unexpected = ", ".join(sorted(_deprecated_kwargs))
            raise TypeError(f"Figure() got unexpected keyword argument(s): {unexpected}")

        if debug:
            warnings.warn(
                "Figure(debug=...) is deprecated. Configure logging instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            logging.getLogger("gu_toolkit.layout").setLevel(logging.DEBUG)

        if default_view_id is not None:
            warnings.warn(
                "Figure(default_view_id=...) is deprecated and ignored; view ids are managed via fig.views.",
                DeprecationWarning,
                stacklevel=2,
            )
        if plotly_legend_mode is not None:
            warnings.warn(
                "Figure(plotly_legend_mode=...) is deprecated; the toolkit uses a side-panel legend.",
                DeprecationWarning,
                stacklevel=2,
            )

        if x_range is not None:
            warnings.warn(
                "Figure(x_range=...) is deprecated; use Figure(default_x_range=...) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if default_x_range is not None and not _same_range(x_range, default_x_range):
                raise ValueError(
                    "Figure() received both default_x_range= and deprecated x_range= with different values; use only default_x_range=."
                )
            default_x_range = x_range

        if y_range is not None:
            warnings.warn(
                "Figure(y_range=...) is deprecated; use Figure(default_y_range=...) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if default_y_range is not None and not _same_range(y_range, default_y_range):
                raise ValueError(
                    "Figure() received both default_y_range= and deprecated y_range= with different values; use only default_y_range=."
                )
            default_y_range = y_range

        if display is not None:
            warnings.warn(
                "Figure(show=...) is deprecated; use Figure(show=...) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if show is not False and bool(display) != bool(show):
                raise ValueError(
                    "Figure() received both show= and show= with different values; use only show=."
                )
            show = bool(display)

        if default_x_range is None:
            default_x_range = (-4, 4)
        if default_y_range is None:
            default_y_range = (-3, 3)

        self._sampling_points = sampling_points
        self.plots: dict[str, Plot] = {}
        self._print_capture: ExitStack | None = None
        self._context_depth = 0
        self._pending_relayout_view_id: str | None = None
        self._has_been_displayed = False
        self._layout_debug_figure_id = new_debug_id("figure")
        self._layout_debug_enabled = is_layout_logger_explicitly_enabled(
            "gu_toolkit.layout.figure"
        )
        self._layout_event_buffer = LayoutEventBuffer(maxlen=500)
        self._layout_event_seq = 0
        self._layout_event_emitter = make_event_emitter(
            logging.getLogger("gu_toolkit.layout.figure"),
            buffer=self._layout_event_buffer,
            base_fields={"figure_id": self._layout_debug_figure_id},
            seq_factory=self._next_layout_seq,
        )

        # 1. Initialize Layout (View)
        self._layout = FigureLayout(title=title)
        if self._layout_debug_enabled:
            self._layout.bind_layout_debug(
                self._emit_layout_event, figure_id=self._layout_debug_figure_id
            )

        # 2. Initialize Managers
        # Note: we pass a callback for rendering so params can trigger updates
        self._parameter_manager = ParameterManager(
            self.render,
            self._layout.params_box,
            modal_host=self._layout.root_widget,
        )
        self._info = InfoPanelManager(self._layout.info_box)
        self._info.bind_figure(self)
        self._legend = LegendPanelManager(self._layout.legend_box)

        # 3. Figure-level relayout debouncer + layout observers
        self._relayout_debouncer = QueuedDebouncer(
            self._dispatch_relayout,
            execute_every_ms=500,
            drop_overflow=True,
            name="Figure.relayout",
            event_sink=(self._emit_layout_event if self._layout_debug_enabled else (lambda **_kwargs: None)),
        )
        self._emit_layout_event("relayout_debouncer_created", source="Figure", phase="completed", level=logging.INFO)
        self._layout.observe_view_selection(self.set_active_view)
        self._layout.observe_full_width_change(
            lambda _is_full: self._request_active_view_reflow("full_width_change")
        )

        # 4. Views facade and model registry
        self._view_manager = ViewManager()
        self._views = FigureViews(self)

        # 5. Set initial state
        self.add_view(
            self._view_manager.default_view_id,
            x_range=default_x_range,
            y_range=default_y_range,
            x_label=x_label,
            y_label=y_label,
        )
        self._legend.set_active_view(self.views.current_id)
        self._emit_layout_event("active_view_after_remove", source="Figure", phase="completed", view_id=self.views.current_id)
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")

        self._emit_layout_event("figure_created", source="Figure", phase="completed", level=logging.INFO, title=title, sampling_points=sampling_points)

        # 6. Logging state
        self._render_info_last_log_t = 0.0
        self._render_debug_last_log_t = 0.0

        if show:
            self.show()

    def _next_layout_seq(self) -> int:
        self._layout_event_seq += 1
        return self._layout_event_seq

    def _emit_layout_event(self, event: str, *, source: str, phase: str, level: int = logging.DEBUG, **fields: Any) -> dict[str, Any]:
        if not self._layout_debug_enabled:
            return {}
        if "active_view_id" not in fields:
            fields["active_view_id"] = (
                self._view_manager.active_view_id
                if hasattr(self, "_view_manager")
                else None
            )
        return self._layout_event_emitter(
            event=event,
            source=source,
            phase=phase,
            level=level,
            **fields,
        )

    def _python_layout_snapshot(self, view_id: str | None = None) -> dict[str, Any]:
        active_id = view_id or (self.views.current_id if getattr(self, "_view_manager", None) and self._view_manager.views else None)
        snap = {
            "content_wrapper_display": self._layout.content_wrapper.layout.display,
            "content_wrapper_flex_flow": self._layout.content_wrapper.layout.flex_flow,
            "sidebar_display": self._layout.sidebar_container.layout.display,
            "view_stage_height": self._layout.view_stage.layout.height,
        }
        if active_id is not None and active_id in self.views:
            pane = self.views[active_id].pane
            snap.update({
                "pane_id": pane.debug_pane_id,
                "pane_widget_width": pane.widget.layout.width,
                "pane_widget_height": pane.widget.layout.height,
                "host_display": pane._host.layout.display,
                "host_width": pane._host.layout.width,
                "host_height": pane._host.layout.height,
            })
        return snap

    # --- Figure-level properties ---
    @property
    def title(self) -> str:
        """Return the title text shown above the figure.

        Returns
        -------
        str
            Current title (HTML/LaTeX is allowed).

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.title = "Demo"  # doctest: +SKIP
        >>> fig.title  # doctest: +SKIP
        'Demo'

        See Also
        --------
        FigureLayout.set_title : Underlying layout helper.
        """
        return self._layout.get_title()

    @title.setter
    def title(self, value: str) -> None:
        """Set the title text shown above the figure.

        Parameters
        ----------
        value : str
            Title text (HTML/LaTeX supported).

        Returns
        -------
        None

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.title = r"$y=\\sin(x)$"  # doctest: +SKIP

        See Also
        --------
        title : Read the current title text.
        """
        self._layout.set_title(value)

    # -------------------------------
    # Views
    # -------------------------------

    @property
    def views(self) -> FigureViews:
        """Mapping-like access to the figure's public :class:`View` objects.

        ``fig.views[view_id]`` returns the public view object. Use
        ``fig.views.current`` and ``fig.views.current_id`` for active-view
        access, and prefer ``with fig.views[view_id]:`` when module-level
        helpers should target a specific workspace temporarily.
        """
        return self._views

    @property
    def active_view_id(self) -> str:
        """Return the currently active view id.

        .. deprecated:: 0.0
            Use ``fig.views.current_id`` instead.
        """
        warnings.warn(
            "Figure.active_view_id is deprecated; use fig.views.current_id.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.views.current_id

    def _create_view(
        self,
        view_id: str,
        *,
        title: str | None = None,
        x_range: RangeLike | None = None,
        y_range: RangeLike | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
    ) -> View:
        """Create one public :class:`View` object with its stable runtime."""
        figure_widget = go.FigureWidget()
        figure_widget.update_layout(**self._default_figure_layout())
        pane = PlotlyPane(
            figure_widget,
            style=PlotlyPaneStyle(
                padding_px=8,
                border="1px solid rgba(15,23,42,0.08)",
                border_radius_px=10,
                overflow="hidden",
            ),
            autorange_mode="none",
            defer_reveal=True,
        )
        view = View(
            figure=self,
            id=view_id,
            title=(str(view_id) if title is None else str(title)),
            x_label=(x_label or ""),
            y_label=(y_label or ""),
            default_x_range=(x_range if x_range is not None else (-4, 4)),
            default_y_range=(y_range if y_range is not None else (-3, 3)),
            figure_widget=figure_widget,
            pane=pane,
        )
        if self._layout_debug_enabled:
            pane.bind_layout_debug(self._emit_layout_event, figure_id=self._layout_debug_figure_id, view_id=view_id)
        self._emit_layout_event("view_runtime_created", source="Figure", phase="completed", view_id=view_id, pane_id=pane.debug_pane_id, default_x_range=view.default_x_range, default_y_range=view.default_y_range)
        return view

    def _attach_view_callbacks(self, view: View) -> None:
        """Attach figure-level relayout routing to one view widget."""
        view.figure_widget.layout.on_change(
            lambda *args, _view_id=view.id: self._queue_relayout(_view_id, *args),
            "xaxis.range",
            "yaxis.range",
        )

    def _request_active_view_reflow(self, reason: str) -> None:
        """Explicitly reflow the active view pane after geometry changes."""
        if not self._view_manager.views:
            self._emit_layout_event("reflow_requested", source="Figure", phase="skipped", level=logging.WARNING, reason=reason, outcome="no_views")
            return
        view = self.views.current
        request_id = new_request_id()
        self._emit_layout_event("reflow_requested", source="Figure", phase="requested", level=logging.INFO, reason=reason, request_id=request_id, view_id=view.id, pane_id=view.pane.debug_pane_id, snapshot=self._python_layout_snapshot(view.id))
        try:
            view.pane.reflow(reason=reason, request_id=request_id, view_id=view.id, figure_id=self._layout_debug_figure_id)
        except Exception:  # pragma: no cover - defensive widget boundary
            self._emit_layout_event("reflow_send_failed", source="Figure", phase="failed", level=logging.ERROR, reason=reason, request_id=request_id, view_id=view.id, pane_id=view.pane.debug_pane_id)
            logger.debug("Active view reflow failed", exc_info=True)

    def add_view(
        self,
        id: str,
        *,
        title: str | None = None,
        x_range: RangeLike | None = None,
        y_range: RangeLike | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        activate: bool = False,
    ) -> View:
        """Create and register a new plotting workspace.

        Parameters
        ----------
        id:
            Stable view identifier.
        title:
            Optional human-readable selector label. Defaults to ``id``.
        x_range, y_range:
            Optional default axis ranges for the new view.
        x_label, y_label:
            Optional axis titles applied to the new view's Plotly widget.
        activate:
            If ``True``, make the new view current immediately. The default is
            ``False``.

        Returns
        -------
        View
            The newly created public view object.
        """
        view_id = str(id)
        view = self._create_view(
            view_id,
            title=title,
            x_range=x_range,
            y_range=y_range,
            x_label=x_label,
            y_label=y_label,
        )
        self._view_manager.register_view(view)
        self._layout.ensure_view_page(view.id, view.title)
        self._layout.attach_view_widget(view.id, view.pane.widget)
        self._layout.set_view_order(tuple(self._view_manager.views.keys()))
        self._attach_view_callbacks(view)
        if view.is_active:
            self._layout.set_active_view(view.id)
            self._info.set_active_view(view.id)
            self._legend.set_active_view(view.id)
        else:
            self._layout.set_active_view(self.views.current_id)
        self._emit_layout_event("view_registered", source="Figure", phase="completed", level=logging.INFO, view_id=view.id, pane_id=view.pane.debug_pane_id, activate=activate)
        if activate and not view.is_active:
            self.set_active_view(view_id)
        else:
            self._request_active_view_reflow("view_added")
        return view

    def set_active_view(self, id: str) -> None:
        """Set the active view id and synchronize widget ranges."""
        view_id = str(id)
        if not self._view_manager.views:
            raise KeyError(f"Unknown view: {view_id}")

        current_view = self.views.current
        if current_view.id == view_id:
            self._layout.set_active_view(view_id)
            self._emit_layout_event("view_switch_requested", source="Figure", phase="completed", view_id=view_id, outcome="already_active")
            return

        self._emit_layout_event("view_switch_requested", source="Figure", phase="requested", level=logging.INFO, view_id=view_id, previous_view_id=current_view.id)
        current_view.current_x_range
        current_view.current_y_range
        self._emit_layout_event("viewport_captured", source="Figure", phase="completed", view_id=current_view.id, viewport_x_range=current_view.viewport_x_range, viewport_y_range=current_view.viewport_y_range)

        transition = self._view_manager.set_active_view(view_id)
        if transition is None:
            self._layout.set_active_view(view_id)
            self._emit_layout_event("active_view_changed", source="Figure", phase="completed", level=logging.INFO, view_id=view_id)
            return

        _, nxt = transition
        self._layout.set_active_view(view_id)
        self._info.set_active_view(view_id)
        self._legend.set_active_view(view_id)

        nxt.current_x_range = nxt.viewport_x_range or nxt.x_range
        nxt.current_y_range = nxt.viewport_y_range or nxt.y_range
        self._emit_layout_event("active_view_changed", source="Figure", phase="completed", level=logging.INFO, view_id=view_id, previous_view_id=current_view.id)
        self._emit_layout_event("viewport_restored", source="Figure", phase="completed", view_id=view_id, viewport_x_range=nxt.viewport_x_range, viewport_y_range=nxt.viewport_y_range)
        self._request_active_view_reflow("view_activated")

        for plot in self.plots.values():
            plot.render(view_id=self.views.current_id)
        if nxt.is_stale:
            self._view_manager.clear_stale(self.views.current_id)

        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")

    @contextmanager
    def view(self, id: str) -> Iterator[Figure]:
        """Deprecated alias for ``with fig.views[id]:``."""
        warnings.warn(
            "Figure.view(...) is deprecated; use `with fig.views[view_id]:` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        with self.views[str(id)]:
            yield self

    def remove_view(self, id: str) -> None:
        """Remove a view and drop plot memberships to it."""
        view_id = str(id)
        if view_id not in self._view_manager.views:
            return
        for plot in self.plots.values():
            plot.remove_from_view(view_id)
            self._legend.on_plot_updated(plot)
        self._emit_layout_event("view_removed", source="Figure", phase="requested", level=logging.INFO, view_id=view_id)
        self._view_manager.remove_view(view_id)
        self._layout.remove_view_page(view_id)
        self._layout.set_view_order(tuple(self._view_manager.views.keys()))
        self._layout.set_active_view(self.views.current_id)
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")
        else:
            self._request_active_view_reflow("view_removed")

    def _sync_sidebar_visibility(self) -> bool:
        """Apply consolidated sidebar section visibility from all managers."""
        changed = self._layout.update_sidebar_visibility(
            self._parameter_manager.has_params,
            self._info.has_info,
            self._legend.has_legend,
        )
        self._emit_layout_event("sidebar_visibility_sync", source="Figure", phase="completed", changed=changed, params_visible=self._parameter_manager.has_params, info_visible=self._info.has_info, legend_visible=self._legend.has_legend)
        return changed


    # --- Layout ---
    def _default_figure_layout(self) -> dict[str, Any]:
        """Return shared Plotly layout defaults copied into each view widget."""
        return {
            "autosize": True,
            "template": "plotly_white",
            # The toolkit provides a dedicated legend side panel. Keep Plotly's
            # built-in legend off by default to avoid duplication.
            "showlegend": False,
            "margin": {"l": 48, "r": 28, "t": 48, "b": 44},
            "font": {
                "family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                "size": 14,
                "color": "#1f2933",
            },
            "paper_bgcolor": "#ffffff",
            "plot_bgcolor": "#f8fafc",
            "legend": {
                "bgcolor": "rgba(255,255,255,0.7)",
                "bordercolor": "rgba(15,23,42,0.08)",
                "borderwidth": 1,
            },
            "xaxis": {
                "zeroline": True,
                "zerolinewidth": 1.5,
                "zerolinecolor": "#334155",
                "showline": True,
                "linecolor": "#94a3b8",
                "linewidth": 1,
                "mirror": True,
                "ticks": "outside",
                "tickcolor": "#94a3b8",
                "ticklen": 6,
                "showgrid": True,
                "gridcolor": "rgba(148,163,184,0.35)",
                "gridwidth": 1,
            },
            "yaxis": {
                "zeroline": True,
                "zerolinewidth": 1.5,
                "zerolinecolor": "#334155",
                "showline": True,
                "linecolor": "#94a3b8",
                "linewidth": 1,
                "mirror": True,
                "ticks": "outside",
                "tickcolor": "#94a3b8",
                "ticklen": 6,
                "showgrid": True,
                "gridcolor": "rgba(148,163,184,0.35)",
                "gridwidth": 1,
            },
        }

    @property
    def figure_widget(self) -> go.FigureWidget:
        """Access the current view's Plotly ``FigureWidget``.

        This is a convenience shorthand for ``fig.views.current.figure_widget``.
        """
        return self.views.current.figure_widget

    def figure_widget_for(self, view_id: str) -> go.FigureWidget:
        """Return the Plotly FigureWidget backing ``view_id``.

        Parameters
        ----------
        view_id : str
            Target view identifier.

        Returns
        -------
        plotly.graph_objects.FigureWidget
            The widget owned by that view.
        """
        return self.views[str(view_id)].figure_widget

    @property
    def pane(self) -> PlotlyPane:
        """Access the active view's :class:`PlotlyPane`."""
        return self.views.current.pane

    def pane_for(self, view_id: str) -> PlotlyPane:
        """Return the :class:`PlotlyPane` backing ``view_id``."""
        return self.views[str(view_id)].pane


    # --- Parameters ---
    @property
    def parameters(self) -> ParameterManager:
        """The figure parameter manager."""
        return self._parameter_manager

    @property
    def info_manager(self) -> InfoPanelManager:
        """Advanced access to the Info section manager.

        Use :meth:`info` for simple rich-text cards. Reach for
        ``fig.info_manager`` when you need raw :class:`ipywidgets.Output`
        widgets, card snapshots, or other manager-level operations.
        """
        return self._info

    # --- Info Cards ---
    @property
    def info_output(self) -> Mapping[Hashable, widgets.Output]:
        """Compatibility view of raw info outputs keyed by id.

        Prefer :attr:`info_manager` for new advanced code. ``info_output`` is a
        thin read-only alias kept for callers that only need the raw output
        widgets created through :meth:`InfoPanelManager.get_output`.
        """
        return self._info.outputs

    @property
    def x_range(self) -> tuple[float, float]:
        """Return the default x-axis range.

        Returns
        -------
        tuple[float, float]
            Default x-axis range restored on double-click.

        Examples
        --------
        >>> fig = Figure(default_x_range=(-2, 2))  # doctest: +SKIP
        >>> fig.x_range  # doctest: +SKIP
        (-2.0, 2.0)

        See Also
        --------
        y_range : The default y-axis range.
        """
        return self.views.current.x_range

    @x_range.setter
    def x_range(self, value: RangeLike) -> None:
        """Set the default x-axis range.

        Parameters
        ----------
        value : RangeLike
            New axis range (min, max).

        Returns
        -------
        None

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.x_range = (-5, 5)  # doctest: +SKIP

        Notes
        -----
        This updates the default Plotly axis range and the visible viewport immediately.
        """
        self.views.current.x_range = value

    @property
    def y_range(self) -> tuple[float, float]:
        """Return the default y-axis range.

        Returns
        -------
        tuple[float, float]
            Default y-axis range.

        Examples
        --------
        >>> fig = Figure(default_y_range=(-1, 1))  # doctest: +SKIP
        >>> fig.y_range  # doctest: +SKIP
        (-1.0, 1.0)

        See Also
        --------
        x_range : The default x-axis range.
        """
        return self.views.current.y_range

    @y_range.setter
    def y_range(self, value: RangeLike) -> None:
        """Set the default y-axis range.

        Parameters
        ----------
        value : RangeLike
            New axis range (min, max).

        Returns
        -------
        None

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.y_range = (-2, 2)  # doctest: +SKIP

        Notes
        -----
        This updates the default Plotly axis range and the visible viewport immediately.
        """
        self.views.current.y_range = value

    @property
    def _viewport_x_range(self) -> tuple[float, float] | None:
        """Control for the current viewport x-range.

        Reading this property queries the live Plotly widget viewport.
        Setting it pans/zooms the visible x-range without changing ``x_range``.
        """
        return self.views.current.current_x_range

    @_viewport_x_range.setter
    def _viewport_x_range(self, value: RangeLike | None) -> None:
        self.views.current.current_x_range = value

    @property
    def _viewport_y_range(self) -> tuple[float, float] | None:
        """Control for the current viewport y-range.

        Reading this property queries the live Plotly widget viewport.
        Setting it pans/zooms the visible y-range without changing ``y_range``.
        """
        return self.views.current.current_y_range

    @_viewport_y_range.setter
    def _viewport_y_range(self, value: RangeLike | None) -> None:
        self.views.current.current_y_range = value

    @property
    def current_x_range(self) -> tuple[float, float] | None:
        """Return the current viewport x-range.

        Returns
        -------
        tuple[float, float] or None
            Current Plotly x-axis range, or ``None`` if not set.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.current_x_range  # doctest: +SKIP

        Notes
        -----
        This reflects the Plotly widget state after panning or zooming.
        """
        return self._viewport_x_range

    @property
    def current_y_range(self) -> tuple[float, float] | None:
        """Return the current viewport y-range (read-only).

        Returns
        -------
        tuple[float, float] or None
            Current Plotly y-axis range, or ``None`` if not set.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.current_y_range  # doctest: +SKIP

        Notes
        -----
        This reflects the Plotly widget state after panning or zooming.
        """
        return self._viewport_y_range

    @property
    def sampling_points(self) -> int | None:
        """Return the default number of sampling points per plot.

        Returns
        -------
        int or None
            Default sample count, or ``None`` for Plotly defaults.

        Examples
        --------
        >>> fig = Figure(sampling_points=300)  # doctest: +SKIP
        >>> fig.sampling_points  # doctest: +SKIP
        300

        See Also
        --------
        Plot.sampling_points : Per-plot overrides.
        """
        return self._sampling_points

    @sampling_points.setter
    def sampling_points(self, val: int | str | _FigureDefaultSentinel | None) -> None:
        """Set the default number of sampling points per plot.

        Parameters
        ----------
        val : int, str, FIGURE_DEFAULT, or None
            Sample count, or ``None``/``"figure_default"``/``"FIGURE_DEFAULT"``/``FIGURE_DEFAULT``
            to clear.

        Returns
        -------
        None

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.sampling_points = 200  # doctest: +SKIP

        Notes
        -----
        Use ``None``/``"figure_default"``/``"FIGURE_DEFAULT"``/``FIGURE_DEFAULT``
        to clear the override.
        """
        self._sampling_points = (
            int(InputConvert(val, int))
            if isinstance(val, (int, float, str)) and not _is_figure_default(val)
            else None
        )

    # --- Public API ---

    @staticmethod
    def plot_style_options() -> dict[str, str]:
        """Return discoverable help text for supported plot-style keywords.

        The returned mapping is generated from structured metadata in
        :mod:`gu_toolkit.figure_plot_style`, so aliases, accepted values, and
        default-behavior notes stay synchronized with the actual style contract.
        """
        return plot_style_option_docs()

    def plot(
        self,
        func: Any,
        var: Any,
        parameters: Sequence[Symbol] | None = None,
        id: str | None = None,
        label: str | None = None,
        visible: VisibleSpec = True,
        x_domain: RangeLike | None = None,
        sampling_points: int | str | None = None,
        color: str | None = None,
        thickness: int | float | None = None,
        width: int | float | None = None,
        dash: str | None = None,
        line: Mapping[str, Any] | None = None,
        opacity: int | float | None = None,
        alpha: int | float | None = None,
        trace: Mapping[str, Any] | None = None,
        view: str | Sequence[str] | None = None,
        vars: PlotVarsSpec | None = None,
    ) -> Plot:
        """
        Plot an expression/callable on the figure (and keep it “live”).

        Parameters
        ----------
        func : callable or NumericFunction or sympy.Expr
            Function/expression to plot.
        var : sympy.Symbol or tuple
            Plot variable ``x`` or ``(x, min, max)`` range tuple.
        parameters : list[sympy.Symbol] or None, optional
            Explicit parameter symbols to ensure. If omitted, symbols are
            inferred from the expression.
        x_domain : RangeLike or None, optional
            Domain of the independent variable (e.g. ``(-10, 10)``).
            If "figure_default", the figure's range is used when plotting.
            If None, it is the same as "figure_default" for new plots while no change for existing plots.
        id : str, optional
            Unique identifier. If exists, the existing plot is updated in-place.
        label : str, optional
            Legend label for the trace. If omitted, new plots default to ``id``;
            existing plots keep their current label.
        visible : bool, optional
            Visibility state for the trace. Hidden traces skip sampling until
            shown.

        sampling_points : int or str, optional
            Number of sampling points for this plot. Use ``"figure_default"``
            to inherit from the figure setting.
        color : str or None, optional
            Line color. Common formats include named colors (e.g., ``"red"``),
            hex values (e.g., ``"#ff0000"``), and ``rgb(...)``/``rgba(...)``.
        thickness : int or float, optional
            Line width in pixels. ``1`` is thin; larger values produce thicker lines.
        width : int or float, optional
            Supported alias for ``thickness``.
        dash : str or None, optional
            Line pattern. Supported values: ``"solid"``, ``"dot"``, ``"dash"``,
            ``"longdash"``, ``"dashdot"``, ``"longdashdot"``.
        line : mapping or None, optional
            Extra per-line style fields as a mapping (advanced usage).
        opacity : int or float, optional
            Overall curve opacity between ``0.0`` (fully transparent) and
            ``1.0`` (fully opaque).
        alpha : int or float, optional
            Supported alias for ``opacity``.
        trace : mapping or None, optional
            Extra full-trace style fields as a mapping (advanced usage).
        vars : Symbol or sequence or mapping, optional
            Optional callable-variable specification shared with
            :func:`numpify` normalization.

            Supported forms:
            - ``x`` (single symbol),
            - ``(x, a, b)`` (ordered positional symbols),
            - ``{0: x, 1: a, "b": b}`` (mixed positional+keyed mapping),
            - ``(x, a, {"b": b})`` (tuple positional prefix + keyed mapping).

            Integer mapping keys must be contiguous starting at ``0``.

        Returns
        -------
        Plot
            The created or updated plot instance.

        Examples
        --------
        >>> import sympy as sp
        >>> x, a = sp.symbols("x a")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> with fig:
        >>>     plot(a * sp.sin(x), x, id="a_sin")  # doctest: +SKIP
        >>>     plot(sp.sin(x), x, id="sin")  # doctest: +SKIP
        >>> fig.show()
        
        Notes
        -----
        Prefer explicit parameter setup with :meth:`parameter`/``parameters``
        before plotting.

        The ``vars=`` grammar is normalized by :func:`numpify._normalize_vars`
        so callable plotting and numeric helpers share one variable-resolution
        contract.

        String-keyed aliases from ``vars=`` mappings are the same keys accepted
        by :meth:`numpify.NumericFunction.freeze` and
        :meth:`numpify.NumericFunction.unfreeze`.

        All supported style options for this method are discoverable via
        :meth:`Figure.plot_style_options`, which is generated from the
        structured metadata in :mod:`gu_toolkit.figure_plot_style`.

        See Also
        --------
        parameter : Create sliders without plotting.
        plot_style_options : List supported style kwargs and meanings
            (`color`, `thickness`/`width`, `dash`, `opacity`/`alpha`, `line`, `trace`).
        """
        # ID Generation
        if id is None:
            for i in range(100):
                if f"f_{i}" not in self.plots:
                    id = f"f_{i}"
                    break
            if id is None:
                raise ValueError("Too many auto-generated IDs")

        normalized_var, normalized_func, normalized_numeric_fn, inferred_parameters = (
            normalize_plot_inputs(
                func,
                var,
                vars=vars,
                id_hint=id,
            )
        )

        if isinstance(var, tuple) and len(var) == 3 and x_domain is not None:
            raise ValueError(
                "plot() cannot combine a range tuple with x_domain=. "
                "Use only one range source, e.g. plot(f, (x, -4, 4))."
            )

        if isinstance(var, tuple) and len(var) == 3:
            x_domain = (var[1], var[2])

        style_kwargs = validate_style_kwargs(
            {
                "color": color,
                "thickness": thickness,
                "width": width,
                "dash": dash,
                "line": line,
                "opacity": opacity,
                "alpha": alpha,
                "trace": trace,
            },
            caller="plot()",
        )
        color = style_kwargs.get("color")
        thickness = style_kwargs.get("thickness")
        dash = style_kwargs.get("dash")
        line = style_kwargs.get("line")
        opacity = style_kwargs.get("opacity")
        trace = style_kwargs.get("trace")

        # Parameter Autodetection
        if parameters is None:
            parameters = list(inferred_parameters)

        # Ensure Parameters Exist (Delegate to Manager)
        if parameters:
            self.parameter(parameters)

        # Update UI visibility
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")

        # Create or Update Plot
        if id in self.plots:
            update_dont_create = True
        else:
            update_dont_create = False

        if update_dont_create:
            update_kwargs: dict[str, Any] = {
                "var": normalized_var,
                "func": normalized_func,
                "parameters": parameters,
                "visible": visible,
                "x_domain": x_domain,
                "sampling_points": sampling_points,
                "color": color,
                "thickness": thickness,
                "dash": dash,
                "line": line,
                "opacity": opacity,
                "trace": trace,
                "view": view,
            }
            if normalized_numeric_fn is not None:
                update_kwargs["numeric_function"] = normalized_numeric_fn
            if label is not None:
                update_kwargs["label"] = label
            self.plots[id].update(**update_kwargs)
            plot = self.plots[id]
            self._legend.on_plot_updated(plot)
            if self._sync_sidebar_visibility():
                self._request_active_view_reflow("sidebar_visibility")
        else:
            view_ids = (
                (view,)
                if isinstance(view, str)
                else (
                    tuple(view)
                    if view is not None
                    else (self.views.current_id,)
                )
            )
            plot = Plot(
                var=normalized_var,
                func=normalized_func,
                smart_figure=self,
                parameters=parameters,
                x_domain=x_domain,
                sampling_points=sampling_points,
                label=(id if label is None else label),
                visible=visible,
                color=color,
                thickness=thickness,
                dash=dash,
                line=line,
                opacity=opacity,
                trace=trace,
                plot_id=id,
                view_ids=view_ids,
                numeric_function=normalized_numeric_fn,
            )
            self.plots[id] = plot
            self._legend.on_plot_added(plot)
            if self._sync_sidebar_visibility():
                self._request_active_view_reflow("sidebar_visibility")

        return plot

    def parameter(
        self,
        symbols: Symbol | Sequence[Symbol],
        *,
        control: Any | None = None,
        **control_kwargs: Any,
    ):
        """
        Create or ensure parameters and return refs.

        Parameters
        ----------
        symbols : sympy.Symbol or sequence[sympy.Symbol]
            Parameter symbol(s) to ensure.
        control : Any, optional
            Optional control instance to use for the parameter(s).
        **control_kwargs : Any
            Control configuration options (min, max, value, step).

        Returns
        -------
        ParamRef or dict[Symbol, ParamRef]
            ParamRef for a single symbol, or mapping for multiple symbols.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> fig.parameter(a, min=-2, max=2)  # doctest: +SKIP

        """
        result = self._parameter_manager.parameter(
            symbols, control=control, **control_kwargs
        )
        self._emit_layout_event("parameter_controls_updated", source="Figure", phase="completed")
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")
        return result

    def render(self, reason: str = "manual", trigger: ParamEvent | None = None) -> None:
        """
        Render all plots on the figure.

        This is a *hot* method: it is called during slider drags and (throttled)
        pan/zoom relayout events.

        Parameters
        ----------
        reason : str, optional
            Reason for rendering (e.g., ``"manual"``, ``"param_change"``, ``"relayout"``).
        trigger : Any, optional
            Change payload from the event that triggered rendering.

        Returns
        -------
        None

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.render()  # doctest: +SKIP

        Notes
        -----
        When called due to a parameter change, hooks registered via
        :meth:`add_param_change_hook` are invoked after plotting.
        """
        self._emit_layout_event("render_started", source="Figure", phase="started", level=logging.INFO, reason=reason, trigger_type=(type(trigger).__name__ if trigger is not None else None))
        self._log_render(reason, trigger)

        # 1. Update active-view plots
        current_view_id = self.views.current_id

        for plot in self.plots.values():
            plot.render(view_id=current_view_id)

        # 1b. Mark inactive memberships stale on parameter changes.
        if reason == "param_change":
            for plot in self.plots.values():
                for view_id in plot.views:
                    if view_id != current_view_id:
                        self._view_manager.mark_stale(view_id=view_id)

        # 2. Run hooks (if triggered by parameter change)
        # Note: ParameterManager triggers this render, then we run hooks.
        if reason == "param_change" and trigger:
            hooks = self._parameter_manager.get_hooks()
            for h_id, callback in list(hooks.items()):
                try:
                    callback(trigger)
                except Exception as e:
                    warnings.warn(f"Hook {h_id} failed: {e}", stacklevel=2)

        self._info.schedule_info_update(reason=reason, trigger=trigger)
        self._emit_layout_event("render_completed", source="Figure", phase="completed", level=logging.INFO, reason=reason, view_id=current_view_id)

    def snapshot(self) -> FigureSnapshot:
        """Return an immutable snapshot of the entire figure state.

        The snapshot captures figure-level settings, full parameter metadata,
        plot symbolic expressions with styling, and static info card content.
        Top-level ``x_range`` / ``y_range`` fields intentionally mirror the
        main view defaults rather than the currently active view.

        Returns
        -------
        FigureSnapshot

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> snap = fig.snapshot()  # doctest: +SKIP
        >>> snap.x_range  # doctest: +SKIP
        (-4.0, 4.0)

        See Also
        --------
        to_code : Generate a Python script from the snapshot.
        """
        active_view = self.views.current
        active_view.current_x_range
        active_view.current_y_range
        main_view = self.views[self._view_manager.default_view_id]

        # The top-level x/y fields intentionally mirror main-view defaults so
        # snapshot/code generation is independent of whichever view happens to
        # be active when ``snapshot()`` is called.
        return FigureSnapshot(
            x_range=main_view.x_range,
            y_range=main_view.y_range,
            sampling_points=self.sampling_points or 500,
            title=self.title or "",
            parameters=self._parameter_manager.snapshot(full=True),
            plots={pid: p.snapshot(id=pid) for pid, p in self.plots.items()},
            info_cards=self._info.snapshot(),
            views=tuple(
                ViewSnapshot(
                    id=view.id,
                    title=view.title,
                    x_label=view.x_label,
                    y_label=view.y_label,
                    x_range=view.x_range,
                    y_range=view.y_range,
                    viewport_x_range=view.viewport_x_range,
                    viewport_y_range=view.viewport_y_range,
                )
                for view in self.views.values()
            ),
            active_view_id=self.views.current_id,
        )

    def to_code(self, *, options: CodegenOptions | None = None) -> str:
        """Generate a self-contained Python script that recreates this figure.

        Parameters
        ----------
        options : CodegenOptions | None, optional
            Configuration for generated output structure.

        Returns
        -------
        str
            Complete Python source code.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> print(fig.to_code())  # doctest: +SKIP

        See Also
        --------
        snapshot : Capture the underlying state object.
        """
        from .codegen import figure_to_code

        return figure_to_code(self.snapshot(), options=options)

    @property
    def code(self) -> str:
        """Read-only shorthand for :meth:`to_code`.

        Returns
        -------
        str
            Generated Python source that recreates the current figure state.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> print(fig.code)  # doctest: +SKIP

        See Also
        --------
        get_code : Configurable code generation helper.
        to_code : Underlying serializer implementation.
        """
        return self.to_code()

    def get_code(self, options: CodegenOptions | None = None) -> str:
        """Return generated figure code with optional serialization settings.

        Parameters
        ----------
        options : CodegenOptions | None, optional
            Optional code-generation configuration.

        Returns
        -------
        str
            Generated Python source code for the current figure state.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> print(fig.get_code())  # doctest: +SKIP

        See Also
        --------
        code : Read-only default code serialization.
        to_code : Keyword-only variant used internally.
        """
        return self.to_code(options=options)

    def info(
        self,
        spec: str
        | Callable[[Figure, Any], str]
        | Sequence[str | Callable[[Figure, Any], str]],
        id: Hashable | None = None,
        *,
        view: str | None = None,
    ) -> None:
        """Create or replace a simple info card in the Info sidebar.

        An *info card* is a small rich-text block shown in the figure's
        ``Info`` section. ``spec`` may be a static string, a callable, or a
        mixed sequence of static and dynamic segments. Dynamic callables receive
        ``(figure, context)`` and are re-evaluated after renders.

        Parameters
        ----------
        spec:
            Static text, one dynamic callable, or a mixed sequence of both.
        id:
            Optional stable card identifier used for replacement.
        view:
            Optional view id. When provided, the card is only visible while that
            view is active.
        """
        self._info.set_simple_card(spec=spec, id=id, view=view)
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")

    def add_param_change_hook(
        self,
        callback: Callable[[ParamEvent | None], Any],
        hook_id: Hashable | None = None,
        *,
        run_now: bool = True,
    ) -> Hashable:
        """
        Register a callback to run when *any* parameter value changes.

        Parameters
        ----------
        callback : callable
            Function with signature ``(event)``. For ``run_now=True``, the
            callback is invoked once with ``None`` after a manual render.
        hook_id : hashable, optional
            Unique identifier for the hook.
        run_now : bool, optional
            Whether to run once immediately with a ``None`` event.

        Returns
        -------
        hashable
            The hook identifier used for registration.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.add_param_change_hook(lambda *_: None, run_now=False)  # doctest: +SKIP

        Notes
        -----
        Hooks are executed after the figure re-renders in response to changes.
        """

        def _wrapped(event: ParamEvent | None) -> Any:
            with _use_figure(self):
                return callback(event)

        hook_id = self._parameter_manager.add_hook(_wrapped, hook_id)

        if run_now:
            try:
                self.render(reason="manual", trigger=None)
                _wrapped(None)
            except Exception as e:
                warnings.warn(f"Hook failed on init: {e}", stacklevel=2)

        return hook_id

    # --- Internal / Plumbing ---

    def _queue_relayout(self, view_id: str, *_: Any) -> None:
        """Queue a relayout event on the figure-level debouncer."""
        self._pending_relayout_view_id = str(view_id)
        self._emit_layout_event("plotly_relayout_queued", source="Figure", phase="queued", view_id=str(view_id))
        self._relayout_debouncer()

    def _dispatch_relayout(self) -> None:
        """Dispatch the most recent queued relayout event."""
        target_view = self._pending_relayout_view_id
        self._pending_relayout_view_id = None
        if target_view is None:
            self._emit_layout_event("plotly_relayout_dispatched", source="Figure", phase="skipped", outcome="no_pending_view")
            return
        if target_view not in self.views:
            self._emit_layout_event("plotly_relayout_dispatched", source="Figure", phase="skipped", outcome="missing_view", view_id=target_view)
            return
        if target_view == self.views.current_id:
            self._emit_layout_event("plotly_relayout_dispatched", source="Figure", phase="completed", view_id=target_view)
            self.render(reason="relayout")
        else:
            self._view_manager.mark_stale(view_id=target_view)
            self._emit_layout_event("inactive_view_marked_stale", source="Figure", phase="completed", view_id=target_view)

    def _log_render(self, reason: str, trigger: Any) -> None:
        """Log render information with rate-limiting.

        Parameters
        ----------
        reason : str
            Render reason string.
        trigger : Any
            Trigger payload (unused except for context).

        Returns
        -------
        None
        """
        self._emit_layout_event("render_debug", source="Figure", phase="completed", reason=reason, trigger_type=(type(trigger).__name__ if trigger is not None else None))
        # Simple rate-limited logging implementation
        now = time.monotonic()
        if (
            logger.isEnabledFor(logging.INFO)
            and (now - self._render_info_last_log_t) > 1.0
        ):
            self._render_info_last_log_t = now
            logger.info(f"render(reason={reason}) plots={len(self.plots)}")

        if (
            logger.isEnabledFor(logging.DEBUG)
            and (now - self._render_debug_last_log_t) > 0.5
        ):
            self._render_debug_last_log_t = now
            logger.debug(f"ranges x={self.x_range} y={self.y_range}")

    def _ipython_display_(self, **kwargs: Any) -> None:
        """
        Special method called by IPython to display the object.
        Uses IPython.display.display() to render the underlying widget.

        Parameters
        ----------
        **kwargs : Any
            Display keyword arguments forwarded by IPython (unused).

        Returns
        -------
        None

        Notes
        -----
        This method defines the display lifecycle contract used in notebooks:
        explicit display (for example ``display(fig)``) drives first render.
        ``Figure(...)`` construction itself is intentionally side-effect free.
        """
        del kwargs
        self._has_been_displayed = True
        self._emit_layout_event(
            "figure_displayed",
            source="Figure",
            phase="completed",
            level=logging.INFO,
            display_method="_ipython_display_",
        )
        display(self._layout.output_widget)

    def show(self) -> None:
        """Display the figure in IPython/Jupyter.

        This is a small convenience wrapper around ``display(fig)``.
        """
        self._has_been_displayed = True
        self._emit_layout_event(
            "figure_displayed",
            source="Figure",
            phase="completed",
            level=logging.INFO,
            display_method="show",
        )
        display(self._layout.output_widget)

    def __enter__(self) -> Figure:
        """Enter a context where this figure becomes the current target.

        Nested ``with fig:`` and ``with fig.views[view_id]:`` blocks are safe:
        the figure keeps one shared output-capture context open until the
        outermost block exits.
        """
        _push_current_figure(self)
        self._context_depth += 1
        if self._context_depth == 1 and self._print_capture is None:
            stack = ExitStack()
            stack.enter_context(self._layout.print_output)
            self._print_capture = stack
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit the current-figure context.

        Parameters
        ----------
        exc_type : Any
            Exception type, if any.
        exc : Any
            Exception instance, if any.
        tb : Any
            Traceback, if any.

        Returns
        -------
        None

        Notes
        -----
        This removes the figure from the module-level stack used by
        :func:`plot` and :func:`parameter`.
        """
        try:
            _pop_current_figure(self)
        finally:
            if self._context_depth > 0:
                self._context_depth -= 1
            if self._context_depth == 0 and self._print_capture is not None:
                self._print_capture.close()
                self._print_capture = None


from . import figure_api as _figure_api

get_sampling_points = _figure_api.get_sampling_points
get_title = _figure_api.get_title
get_x_range = _figure_api.get_x_range
get_y_range = _figure_api.get_y_range
info = _figure_api.info
parameter = _figure_api.parameter
parameters = _figure_api.parameters
plot = _figure_api.plot
plots = _figure_api.plots
plot_style_options = _figure_api.plot_style_options
render = _figure_api.render
set_sampling_points = _figure_api.set_sampling_points
set_title = _figure_api.set_title
set_x_range = _figure_api.set_x_range
set_y_range = _figure_api.set_y_range


__all__ = [
    # Coordinator entry point
    "Figure",
    "FigureViews",
    # Common collaborating types (re-exported for convenience)
    "FigureLayout",
    "Plot",
    "View",
    "FigureSnapshot",
    "ViewSnapshot",
    # Context
    "current_figure",
    # Module-level helpers (figure_api)
    "plot",
    "plots",
    "parameter",
    "parameters",
    "info",
    "render",
    "get_sampling_points",
    "set_sampling_points",
    "get_x_range",
    "set_x_range",
    "get_y_range",
    "set_y_range",
    "get_title",
    "set_title",
    "plot_style_options",
]
