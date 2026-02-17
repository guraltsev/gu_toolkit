"""Interactive Figure orchestration for notebook plotting.

Purpose
-------
This module provides the public ``Figure`` class and module-level convenience
helpers that power the interactive plotting workflow in ``gu_toolkit``. It
connects symbolic SymPy expressions to Plotly traces and notebook widgets so
users can explore parameterized functions in real time.

Concepts and structure
----------------------
The implementation is composition-based:

- ``Figure`` coordinates rendering and exposes the public plotting API.
- ``FigureLayout`` owns widget/layout construction.
- ``ParameterManager`` owns controls and parameter hooks.
- ``InfoPanelManager`` owns sidebar output/components.
- ``Plot`` (from ``figure_plot``) encapsulates per-curve math/trace logic.

Architecture notes
------------------
``Figure`` delegates as much behavior as possible to specialized collaborators
(``figure_layout``, ``figure_parameters``, ``figure_info``, ``figure_plot``),
while this module provides the top-level coordinator and user-facing helper
functions (``plot``, ``parameter``, ``render``, range/title helpers, etc.).

Important gotchas
-----------------
- Plotly ``FigureWidget`` requires a real container height; use the layout
  helpers as designed when embedding in custom notebook UIs.
- Parameter updates and relayout events are debounced/throttled to prevent
  excessive rerenders.
- Global helper functions route through the active figure context; ensure a
  current figure is set (e.g., by using ``with fig:``) before calling them.

Examples
--------
>>> import sympy as sp
>>> from gu_toolkit.Figure import Figure
>>> x, a = sp.symbols("x a")
>>> fig = Figure()
>>> fig.parameter(a, min=-2, max=2)  # doctest: +SKIP
>>> fig.plot(a * sp.sin(x), x, id="wave")  # doctest: +SKIP
>>> fig  # doctest: +SKIP

Discoverability
---------------
If you are extending behavior, inspect next:

- ``figure_plot.py`` for per-curve sampling/render internals.
- ``figure_parameters.py`` for parameter registration and hooks.
- ``figure_layout.py`` for widget tree/layout decisions.
- ``PlotlyPane.py`` for robust Plotly resizing in notebook containers.
"""

from __future__ import annotations


import inspect
import re
import time
import warnings
import logging
from contextlib import ExitStack, contextmanager
from collections.abc import Mapping
from typing import Any, Callable, Hashable, Optional, Sequence, Tuple, Union, Dict, Iterator, List, NamedTuple, TypeAlias

import ipywidgets as widgets
import numpy as np
import plotly.graph_objects as go
import sympy as sp
from IPython.display import display
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

# Internal imports (assumed to exist in the same package)
from .InputConvert import InputConvert
from .numpify import NumericFunction, numpify_cached, _normalize_vars
from .PlotlyPane import PlotlyPane, PlotlyPaneStyle
from .Slider import FloatSlider
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .ParameterSnapshot import ParameterSnapshot, ParameterValueSnapshot
from .FigureSnapshot import FigureSnapshot, ViewSnapshot
from .debouncing import QueuedDebouncer


# Module logger
# - Uses a NullHandler so importing this module never configures global logging.
# - Callers can enable logs via standard logging configuration.
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

_FIGURE_STACK: List["Figure"] = []




from .figure_context import (
    FIGURE_DEFAULT,
    _is_figure_default,
    _current_figure,
    _pop_current_figure,
    _push_current_figure,
    _require_current_figure,
    _use_figure,
    current_figure,
)
from .figure_layout import FigureLayout, OneShotOutput
from .figure_parameters import ParameterManager
from .figure_info import InfoPanelManager
from .figure_legend import LegendPanelManager
from .figure_plot import Plot
from .figure_view import View

# -----------------------------
# Small type aliases
# -----------------------------
NumberLike = Union[int, float]
NumberLikeOrStr = Union[int, float, str]
RangeLike = Tuple[NumberLikeOrStr, NumberLikeOrStr]
VisibleSpec = Union[bool, str]  # Plotly uses True/False or the string "legendonly".
PlotVarsSpec: TypeAlias = Union[
    Symbol,
    Sequence[Union[Symbol, Mapping[str, Symbol]]],
    Mapping[Union[int, str], Symbol],
]

PLOT_STYLE_OPTIONS: Dict[str, str] = {
    "color": "Line color. Accepts CSS-like names (e.g., red), hex (#RRGGBB), or rgb()/rgba() strings.",
    "thickness": "Line width in pixels. Larger values draw thicker lines.",
    "width": "Alias for thickness.",
    "dash": "Line pattern. Supported values: solid, dot, dash, longdash, dashdot, longdashdot.",
    "opacity": "Overall trace opacity from 0.0 (fully transparent) to 1.0 (fully opaque).",
    "alpha": "Alias for opacity.",
    "line": "Extra line-style fields as a mapping (for advanced per-line styling).",
    "trace": "Extra trace fields as a mapping (for advanced full-trace styling).",
}


def _resolve_style_aliases(*, thickness: Optional[Union[int, float]], width: Optional[Union[int, float]], opacity: Optional[Union[int, float]], alpha: Optional[Union[int, float]]) -> tuple[Optional[Union[int, float]], Optional[Union[int, float]]]:
    """Resolve plot style aliases into canonical values.

    Raises
    ------
    ValueError
        If alias and canonical values are both provided with different values.
    """
    if width is not None:
        if thickness is not None and width != thickness:
            raise ValueError("plot() received both thickness= and width= with different values; use only one.")
        thickness = width if thickness is None else thickness

    if alpha is not None:
        if opacity is not None and alpha != opacity:
            raise ValueError("plot() received both opacity= and alpha= with different values; use only one.")
        opacity = alpha if opacity is None else opacity

    return thickness, opacity



def _coerce_symbol(value: Any, *, role: str) -> Symbol:
    """Return ``value`` as a SymPy symbol or raise a clear ``TypeError``."""
    if isinstance(value, Symbol):
        return value
    raise TypeError(f"plot() expects {role} to be a sympy.Symbol, got {type(value).__name__}")


def _rebind_numeric_function_vars(
    numeric_fn: NumericFunction,
    *,
    vars_spec: Any,
    source_callable: Optional[Callable[..., Any]] = None,
) -> NumericFunction:
    """Return a ``NumericFunction`` rebound to ``bound_symbols`` order.

    This is used by callable-first normalization when the user-provided plotting
    variable should replace inferred callable argument symbols (for example,
    ``plot(lambda t: t**2, x)``). Rebinding keeps the positional callable
    contract but aligns symbol identity with figure parameter/freeze semantics.
    """
    fn = source_callable if source_callable is not None else getattr(numeric_fn, "_fn")
    return NumericFunction(
        fn,
        vars=vars_spec,
        symbolic=numeric_fn.symbolic,
        source=numeric_fn.source,
    )


def _normalize_plot_inputs(
    first: Any,
    second: Any,
    *,
    vars: Optional[PlotVarsSpec] = None,
    id_hint: Optional[str] = None,
) -> tuple[Symbol, Expr, Optional[NumericFunction], tuple[Symbol, ...]]:
    """Normalize callable-first ``plot()`` inputs.

    Returns
    -------
    tuple
        ``(plot_var, symbolic_expr, numeric_fn_or_none, parameter_symbols)``.
    """
    vars_spec: Any = None
    if vars is not None:
        normalized = _normalize_vars(sp.Integer(0), vars)
        vars_tuple = tuple(normalized["all"])
        if not vars_tuple:
            raise ValueError("plot() vars must not be empty when provided")
        vars_spec = normalized["spec"]
    else:
        vars_tuple = None

    f = first
    var_or_range = second

    numeric_fn: Optional[NumericFunction] = None
    source_callable: Optional[Callable[..., Any]] = None
    expr: Expr
    call_symbols: tuple[Symbol, ...]

    if isinstance(f, Expr):
        expr = f
        call_symbols = tuple(sorted(expr.free_symbols, key=lambda s: s.sort_key()))
    elif isinstance(f, NumericFunction):
        numeric_fn = f
        source_callable = getattr(f, "_fn")
        call_symbols = tuple(f.free_vars)
        symbolic = f.symbolic
        if isinstance(symbolic, Expr):
            expr = symbolic
        else:
            fallback_name = id_hint or "f"
            expr = sp.Symbol(f"{fallback_name}_numeric")
    elif callable(f):
        source_callable = f
        sig = inspect.signature(f)
        positional = [
            p for p in sig.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if any(p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD) for p in sig.parameters.values()):
            raise TypeError("plot() callable does not support *args/**kwargs signatures")
        call_symbols = tuple(sp.Symbol(p.name) for p in positional)
        numeric_fn = NumericFunction(f, vars=vars_spec if vars_spec is not None else call_symbols)
        if vars_spec is not None:
            call_symbols = tuple(numeric_fn.free_vars)
        expr = sp.Symbol(id_hint or getattr(f, "__name__", "f"))
    else:
        raise TypeError(
            "plot() expects first argument to be a SymPy expression, NumericFunction, or callable."
        )

    if vars_tuple is not None:
        bound_symbols = vars_tuple
        if numeric_fn is not None:
            numeric_fn = _rebind_numeric_function_vars(
                numeric_fn,
                vars_spec=vars_spec if vars_spec is not None else bound_symbols,
                source_callable=source_callable,
            )
    else:
        bound_symbols = call_symbols

    if isinstance(var_or_range, tuple):
        if len(var_or_range) != 3:
            raise ValueError(
                "plot() range tuple must have shape (var, min, max), e.g. (x, -4, 4)"
            )
        plot_var = _coerce_symbol(var_or_range[0], role="range tuple variable")
    elif var_or_range is None:
        if len(bound_symbols) == 1:
            plot_var = bound_symbols[0]
        else:
            raise ValueError(
                "plot() could not infer plotting variable for callable-first usage. "
                "Pass an explicit symbol or range tuple, e.g. plot(f, x) or plot(f, (x, -4, 4))."
            )
    else:
        plot_var = _coerce_symbol(var_or_range, role="plot variable")

    if plot_var not in bound_symbols:
        if len(bound_symbols) == 1:
            bound_symbols = (plot_var,)
            if numeric_fn is not None:
                numeric_fn = _rebind_numeric_function_vars(
                    numeric_fn,
                    vars_spec=bound_symbols,
                    source_callable=source_callable,
                )
        else:
            raise ValueError(
                f"plot() variable {plot_var!r} is not present in callable variables {bound_symbols!r}. "
                "Use vars=... to declare callable variable order explicitly."
            )

    parameters = tuple(sym for sym in bound_symbols if sym != plot_var)
    return plot_var, expr, numeric_fn, parameters

# SECTION: Figure (The Coordinator) [id: Figure]
# =============================================================================


class _ViewRuntime(NamedTuple):
    """Runtime objects owned by a single workspace view."""

    figure_widget: go.FigureWidget
    pane: PlotlyPane


class Figure:
    """
    An interactive Plotly figure for plotting SymPy functions with slider parameters.

    What problem does this solve?
    -----------------------------
    We often want to:
    - type a symbolic function like ``sin(x)`` or ``a*x**2 + b`` (SymPy),
    - *see* it immediately (Plotly),
    - and then explore “What happens if I change a parameter?”

    ``Figure`` provides a simple API that encourages experimentation.

    Key features
    ------------
    - Uses Plotly ``FigureWidget`` so it is interactive inside notebooks.
    - Uses a right-side controls panel for parameter sliders.
    - Supports plotting multiple curves identified by an ``id``.
    - Re-renders curves on:
      - slider changes,
      - pan/zoom changes (throttled to at most once every 0.5 seconds).

    Examples
    --------
    >>> import sympy as sp
    >>> x, a = sp.symbols("x a")
    >>> fig = Figure()
    >>> fig.parameter(a, min=-2, max=2)
    >>> fig.plot(a*sp.sin(x), x, id="a_sin")
    >>> fig
    """
    
    __slots__ = [
        "_layout", "_params", "_info", "_legend", "_view_runtime", "_figure", "_pane", "plots",
        "_views", "_active_view_id", "_default_view_id", "_sampling_points", "_debug",
        "_render_info_last_log_t", "_render_debug_last_log_t", "_relayout_debouncers",
        "_has_been_displayed", "_print_capture"
    ]

    def __init__(
        self,
        sampling_points: int = 500,
        x_range: RangeLike = (-4, 4),
        y_range: RangeLike = (-3, 3),
        debug: bool = False,
        default_view_id: str = "main",
    ) -> None:
        """Initialize a Figure instance with default ranges and sampling.

        Parameters
        ----------
        sampling_points : int, optional
            Default number of samples per plot.
        x_range : RangeLike, optional
            Initial x-axis range.
        y_range : RangeLike, optional
            Initial y-axis range.
        debug : bool, optional
            Enable debug logging for renders and ranges.

        Returns
        -------
        None

        Examples
        --------
        >>> fig = Figure(x_range=(-6, 6), y_range=(-2, 2))  # doctest: +SKIP
        >>> fig.sampling_points  # doctest: +SKIP
        500

        Notes
        -----
        Parameters are managed by :class:`ParameterManager` and exposed through
        :attr:`params`.
        """
        self._debug = debug
        self._sampling_points = sampling_points
        self.plots: Dict[str, Plot] = {}
        self._has_been_displayed = False
        self._print_capture: Optional[ExitStack] = None

        # 1. Initialize Layout (View)
        self._layout = FigureLayout()
        
        # 2. Initialize Managers
        # Note: we pass a callback for rendering so params can trigger updates
        self._params = ParameterManager(
            self.render,
            self._layout.params_box,
            modal_host=self._layout.root_widget,
        )
        self._info = InfoPanelManager(self._layout.info_box)
        self._info.bind_figure(self)
        self._legend = LegendPanelManager(self._layout.legend_box)

        # 3. Initialize Per-View Plotly Runtime
        self._view_runtime: Dict[str, _ViewRuntime] = {}
        self._relayout_debouncers: Dict[str, QueuedDebouncer] = {}
        self._layout.observe_tab_selection(self.set_active_view)

        # 4. Set Initial State
        self._default_view_id = str(default_view_id)
        self._views: Dict[str, View] = {}
        self._active_view_id = self._default_view_id
        self.add_view(self._default_view_id, x_range=x_range, y_range=y_range)
        self._legend.set_active_view(self._active_view_id)
        self._sync_sidebar_visibility()

        # Backward-compat convenience aliases mirror the active view runtime.
        active_runtime = self._runtime_for_view(self._active_view_id)
        self._figure = active_runtime.figure_widget
        self._pane = active_runtime.pane

        # 5. Bind Events
        self._render_info_last_log_t = 0.0
        self._render_debug_last_log_t = 0.0

    # --- Properties ---

    @property
    def active_view_id(self) -> str:
        """Return the currently active view identifier."""
        return self._active_view_id

    @property
    def views(self) -> Dict[str, View]:
        """Return the workspace view registry."""
        return self._views

    def _active_view(self) -> View:
        """Return the active view model."""
        return self._views[self._active_view_id]

    def _default_figure_layout(self) -> Dict[str, Any]:
        """Return shared Plotly layout defaults copied into each view widget."""
        return dict(
            autosize=True,
            template="plotly_white",
            showlegend=True,
            margin=dict(l=48, r=28, t=48, b=44),
            font=dict(
                family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                size=14,
                color="#1f2933",
            ),
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            legend=dict(
                bgcolor="rgba(255,255,255,0.7)",
                bordercolor="rgba(15,23,42,0.08)",
                borderwidth=1,
            ),
            xaxis=dict(
                zeroline=True,
                zerolinewidth=1.5,
                zerolinecolor="#334155",
                showline=True,
                linecolor="#94a3b8",
                linewidth=1,
                mirror=True,
                ticks="outside",
                tickcolor="#94a3b8",
                ticklen=6,
                showgrid=True,
                gridcolor="rgba(148,163,184,0.35)",
                gridwidth=1,
            ),
            yaxis=dict(
                zeroline=True,
                zerolinewidth=1.5,
                zerolinecolor="#334155",
                showline=True,
                linecolor="#94a3b8",
                linewidth=1,
                mirror=True,
                ticks="outside",
                tickcolor="#94a3b8",
                ticklen=6,
                showgrid=True,
                gridcolor="rgba(148,163,184,0.35)",
                gridwidth=1,
            ),
        )

    def _runtime_for_view(self, view_id: str) -> _ViewRuntime:
        """Return the per-view runtime bundle for ``view_id``."""
        return self._view_runtime[view_id]

    def _create_view_runtime(self, *, view_id: str) -> _ViewRuntime:
        """Create and register per-view widget runtime state."""
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
        runtime = _ViewRuntime(figure_widget=figure_widget, pane=pane)
        self._view_runtime[view_id] = runtime
        self._layout.set_view_plot_widget(view_id, pane.widget, reflow_callback=pane.reflow)

        debouncer = QueuedDebouncer(
            lambda *args: self._run_relayout(view_id=view_id, *args),
            execute_every_ms=500,
            drop_overflow=True,
        )
        self._relayout_debouncers[view_id] = debouncer
        figure_widget.layout.on_change(
            lambda *args: self._throttled_relayout(view_id, *args),
            "xaxis.range", "yaxis.range",
        )
        return runtime

    def add_view(
        self,
        id: str,
        *,
        title: Optional[str] = None,
        x_range: Optional[RangeLike] = None,
        y_range: Optional[RangeLike] = None,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
    ) -> View:
        """Add a view model to the workspace registry."""
        view_id = str(id)
        if view_id in self._views:
            raise ValueError(f"View '{view_id}' already exists")
        xr = x_range if x_range is not None else (-4.0, 4.0)
        yr = y_range if y_range is not None else (-3.0, 3.0)
        view = View(
            id=view_id,
            title=title or view_id,
            x_label=x_label or "",
            y_label=y_label or "",
            default_x_range=(float(InputConvert(xr[0], float)), float(InputConvert(xr[1], float))),
            default_y_range=(float(InputConvert(yr[0], float)), float(InputConvert(yr[1], float))),
            is_active=(not self._views),
        )
        self._views[view_id] = view
        runtime = self._create_view_runtime(view_id=view_id)
        runtime.figure_widget.update_xaxes(range=view.default_x_range)
        runtime.figure_widget.update_yaxes(range=view.default_y_range)
        if view.is_active:
            self._active_view_id = view_id
            self._info.set_active_view(view_id)
            self._legend.set_active_view(view_id)
            self._figure = runtime.figure_widget
            self._pane = runtime.pane
        self._layout.set_view_tabs(tuple(self._views.keys()), active_view_id=self._active_view_id)
        return view

    def set_active_view(self, id: str) -> None:
        """Set the active view id and synchronize widget ranges."""
        if id not in self._views:
            raise KeyError(f"Unknown view: {id}")
        if id == self._active_view_id:
            return

        current = self._active_view()
        current.viewport_x_range = self._viewport_x_range
        current.viewport_y_range = self._viewport_y_range
        current.is_active = False

        self._active_view_id = id
        nxt = self._active_view()
        nxt.is_active = True
        self._info.set_active_view(id)
        self._legend.set_active_view(id)

        runtime = self._runtime_for_view(id)
        self._figure = runtime.figure_widget
        self._pane = runtime.pane
        self._figure.update_xaxes(range=nxt.viewport_x_range or nxt.default_x_range)
        self._figure.update_yaxes(range=nxt.viewport_y_range or nxt.default_y_range)

        for plot in self.plots.values():
            plot.render(view_id=self._active_view_id)
        if nxt.is_stale:
            nxt.is_stale = False

        self._layout.set_view_tabs(tuple(self._views.keys()), active_view_id=self._active_view_id)
        self._layout.trigger_reflow_for_view(self._active_view_id)
        self._sync_sidebar_visibility()

    @contextmanager
    def view(self, id: str) -> Iterator["Figure"]:
        """Temporarily switch the active workspace view within a context."""
        previous = self.active_view_id
        self.set_active_view(id)
        try:
            yield self
        finally:
            if previous in self._views:
                self.set_active_view(previous)

    def remove_view(self, id: str) -> None:
        """Remove a view and drop plot memberships to it."""
        if id == self._active_view_id:
            raise ValueError("Cannot remove active view")
        if id == self._default_view_id:
            raise ValueError("Cannot remove default view")
        if id not in self._views:
            return
        for plot in self.plots.values():
            plot.remove_from_view(id)
            self._legend.on_plot_updated(plot)
        del self._views[id]
        self._view_runtime.pop(id, None)
        self._relayout_debouncers.pop(id, None)
        self._layout.set_view_tabs(tuple(self._views.keys()), active_view_id=self._active_view_id)
        self._sync_sidebar_visibility()

    def _sync_sidebar_visibility(self) -> None:
        """Apply consolidated sidebar section visibility from all managers."""
        self._layout.update_sidebar_visibility(
            self._params.has_params,
            self._info.has_info,
            self._legend.has_legend,
        )

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
    
    @property
    def figure_widget(self) -> go.FigureWidget:
        """Access the active view's Plotly FigureWidget.

        Returns
        -------
        plotly.graph_objects.FigureWidget
            The interactive Plotly widget for :attr:`active_view_id`.
        """
        return self._runtime_for_view(self._active_view_id).figure_widget

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
        if view_id not in self._views:
            raise KeyError(f"Unknown view: {view_id}")
        return self._runtime_for_view(view_id).figure_widget
    
    @property
    def parameters(self) -> ParameterManager:
        """The figure ParameterManager (preferred name)."""
        return self._params

    @property
    def params(self) -> ParameterManager:
        """Alias for :attr:`parameters` for backward compatibility."""
        return self.parameters
    
    @property
    def info_output(self) -> Dict[Hashable, widgets.Output]:
        """Dictionary of Info Output widgets indexed by id.

        Returns
        -------
        dict
            Mapping of output IDs to ``ipywidgets.Output`` instances.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> isinstance(fig.info_output, dict)  # doctest: +SKIP
        True

        """
        return self._info._outputs # Direct access for backward compat or advanced use

    @property
    def x_range(self) -> Tuple[float, float]:
        """Return the default x-axis range.

        Returns
        -------
        tuple[float, float]
            Default x-axis range restored on double-click.

        Examples
        --------
        >>> fig = Figure(x_range=(-2, 2))  # doctest: +SKIP
        >>> fig.x_range  # doctest: +SKIP
        (-2.0, 2.0)

        See Also
        --------
        y_range : The default y-axis range.
        """
        return self._active_view().default_x_range
    
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
        rng = (float(InputConvert(value[0], float)), float(InputConvert(value[1], float)))
        self._active_view().default_x_range = rng
        self._figure.update_xaxes(range=rng)

    @property
    def y_range(self) -> Tuple[float, float]:
        """Return the default y-axis range.

        Returns
        -------
        tuple[float, float]
            Default y-axis range.

        Examples
        --------
        >>> fig = Figure(y_range=(-1, 1))  # doctest: +SKIP
        >>> fig.y_range  # doctest: +SKIP
        (-1.0, 1.0)

        See Also
        --------
        x_range : The default x-axis range.
        """
        return self._active_view().default_y_range
    
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
        rng = (float(InputConvert(value[0], float)), float(InputConvert(value[1], float)))
        self._active_view().default_y_range = rng
        self._figure.update_yaxes(range=rng)

    @property
    def _viewport_x_range(self) -> Optional[Tuple[float, float]]:
        """Control for the current viewport x-range.

        Reading this property queries the live Plotly widget viewport.
        Setting it pans/zooms the visible x-range without changing ``x_range``.
        """
        rng = self._figure.layout.xaxis.range
        if rng is None:
            return None
        result = (float(rng[0]), float(rng[1]))
        self._active_view().viewport_x_range = result
        return result

    @_viewport_x_range.setter
    def _viewport_x_range(self, value: Optional[RangeLike]) -> None:
        if value is None:
            rng = self._active_view().default_x_range
            self._active_view().viewport_x_range = rng
            self._figure.update_xaxes(range=rng)
            return
        rng = (float(InputConvert(value[0], float)), float(InputConvert(value[1], float)))
        self._active_view().viewport_x_range = rng
        self._figure.update_xaxes(range=rng)

    @property
    def _viewport_y_range(self) -> Optional[Tuple[float, float]]:
        """Control for the current viewport y-range.

        Reading this property queries the live Plotly widget viewport.
        Setting it pans/zooms the visible y-range without changing ``y_range``.
        """
        rng = self._figure.layout.yaxis.range
        if rng is None:
            return None
        result = (float(rng[0]), float(rng[1]))
        self._active_view().viewport_y_range = result
        return result

    @_viewport_y_range.setter
    def _viewport_y_range(self, value: Optional[RangeLike]) -> None:
        if value is None:
            rng = self._active_view().default_y_range
            self._active_view().viewport_y_range = rng
            self._figure.update_yaxes(range=rng)
            return
        rng = (float(InputConvert(value[0], float)), float(InputConvert(value[1], float)))
        self._active_view().viewport_y_range = rng
        self._figure.update_yaxes(range=rng)

    @property
    def current_x_range(self) -> Optional[Tuple[float, float]]:
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
    def current_y_range(self) -> Optional[Tuple[float, float]]:
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
    def sampling_points(self) -> Optional[int]:
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
    def sampling_points(self, val: Union[int, str, _FigureDefaultSentinel, None]) -> None:
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
        self._sampling_points = int(InputConvert(val, int)) if isinstance(val, (int, float, str)) and not _is_figure_default(val) else None

    # --- Public API ---

    @staticmethod
    def plot_style_options() -> Dict[str, str]:
        """Return discoverable plot-style options supported by :meth:`plot`.

        Returns
        -------
        dict[str, str]
            Mapping of option names to short descriptions.

        Notes
        -----
        These options can be passed directly to :meth:`plot` and :func:`plot`.
        Current supported shortcut keys are: ``color``, ``thickness``/``width``,
        ``dash``, ``opacity``/``alpha``, ``line``, and ``trace``.
        """
        return dict(PLOT_STYLE_OPTIONS)

    def plot(
        self,
        func: Any,
        var: Any,
        parameters: Optional[Sequence[Symbol]] = None,
        id: Optional[str] = None,
        label: Optional[str] = None,
        visible: VisibleSpec = True,
        x_domain: Optional[RangeLike] = None,
        sampling_points: Optional[Union[int, str]] = None,
        color: Optional[str] = None,
        thickness: Optional[Union[int, float]] = None,
        width: Optional[Union[int, float]] = None,
        dash: Optional[str] = None,
        line: Optional[Mapping[str, Any]] = None,
        opacity: Optional[Union[int, float]] = None,
        alpha: Optional[Union[int, float]] = None,
        trace: Optional[Mapping[str, Any]] = None,
        view: Optional[Union[str, Sequence[str]]] = None,
        vars: Optional[PlotVarsSpec] = None,
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
            Deprecated. Use :meth:`parameter` / :attr:`parameters` to create and
            manage controls explicitly. If omitted, symbols are inferred from
            the expression.
        x_domain : RangeLike or None, optional
            Domain of the independent variable (e.g. ``(-10, 10)``).
            If "figure_default", the figure's range is used when plotting. 
            If None, it is the same as "figure_default" for new plots while no change for existing plots.
        id : str, optional
            Unique identifier. If exists, the existing plot is updated in-place.
        label : str, optional
            Legend label for the trace. If omitted, new plots default to ``id``;
            existing plots keep their current label.
        visible : bool or "legendonly", optional
            Plotly visibility state for the trace. Hidden traces skip sampling
            until shown.

        sampling_points : int or str, optional
            Number of sampling points for this plot. Use ``"figure_default"``
            to inherit from the figure setting.
        color : str or None, optional
            Line color. Common formats include named colors (e.g., ``"red"``),
            hex values (e.g., ``"#ff0000"``), and ``rgb(...)``/``rgba(...)``.
        thickness : int or float, optional
            Line width in pixels. ``1`` is thin; larger values produce thicker lines.
        width : int or float, optional
            Alias for ``thickness``.
        dash : str or None, optional
            Line pattern. Supported values: ``"solid"``, ``"dot"``, ``"dash"``,
            ``"longdash"``, ``"dashdot"``, ``"longdashdot"``.
        line : mapping or None, optional
            Extra per-line style fields as a mapping (advanced usage).
        opacity : int or float, optional
            Overall curve opacity between ``0.0`` (fully transparent) and
            ``1.0`` (fully opaque).
        alpha : int or float, optional
            Alias for ``opacity``.
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
        >>> x, a = sp.symbols("x a")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.parameter(a, min=-2, max=2)  # doctest: +SKIP
        >>> fig.plot(a * sp.sin(x), x, id="a_sin")  # doctest: +SKIP
        >>> fig.plot(sp.sin(x), x, id="sin")  # doctest: +SKIP

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
        :meth:`Figure.plot_style_options`.

        See Also
        --------
        parameter : Create sliders without plotting.
        plot_style_options : List supported style kwargs and meanings
            (`color`, `thickness`, `width`, `dash`, `opacity`, `alpha`, `line`, `trace`).
        """
        # ID Generation
        if id is None:
            for i in range(100):
                if f"f_{i}" not in self.plots:
                    id = f"f_{i}"
                    break
            if id is None: raise ValueError("Too many auto-generated IDs")

        normalized_var, normalized_func, normalized_numeric_fn, inferred_parameters = _normalize_plot_inputs(
            func,
            var,
            vars=vars,
            id_hint=id,
        )

        if isinstance(var, tuple) and len(var) == 3 and x_domain is not None:
            raise ValueError(
                "plot() cannot combine a range tuple with x_domain=. "
                "Use only one range source, e.g. plot(f, (x, -4, 4))."
            )

        if isinstance(var, tuple) and len(var) == 3:
            x_domain = (var[1], var[2])

        if parameters is not None:
            warnings.warn(
                "plot(..., parameters=...) is deprecated; use parameter()/parameters to register controls.",
                DeprecationWarning,
                stacklevel=2,
            )

        thickness, opacity = _resolve_style_aliases(
            thickness=thickness,
            width=width,
            opacity=opacity,
            alpha=alpha,
        )

        # Parameter Autodetection
        if parameters is None:
            parameters = list(inferred_parameters)

        # Ensure Parameters Exist (Delegate to Manager)
        if parameters:
            self.parameter(parameters)
        
        # Update UI visibility
        self._sync_sidebar_visibility()

        # Create or Update Plot
        if id in self.plots:
            update_dont_create = True
        else: 
            update_dont_create = False

        initial_func = normalized_var if normalized_numeric_fn is not None else normalized_func

        if update_dont_create:
            update_kwargs: Dict[str, Any] = dict(
                var=normalized_var,
                func=initial_func,
                parameters=parameters,
                visible=visible,
                x_domain=x_domain,
                sampling_points=sampling_points,
                color=color,
                thickness=thickness,
                dash=dash,
                line=line,
                opacity=opacity,
                trace=trace,
                view=view,
            )
            if label is not None:
                update_kwargs["label"] = label
            self.plots[id].update(**update_kwargs)
            plot = self.plots[id]    
            self._legend.on_plot_updated(plot)
            self._sync_sidebar_visibility()
        else: 
            view_ids = (view,) if isinstance(view, str) else (tuple(view) if view is not None else (self.active_view_id,))
            plot = Plot(
                var=normalized_var, func=initial_func, smart_figure=self, parameters=parameters,
                x_domain=x_domain, sampling_points=sampling_points,
                label=(id if label is None else label), visible=visible,
                color=color, thickness=thickness, dash=dash, line=line, opacity=opacity, trace=trace,
                plot_id=id, view_ids=view_ids,
            )
            self.plots[id] = plot
            self._legend.on_plot_added(plot)
            self._sync_sidebar_visibility()

        if normalized_numeric_fn is not None:
            plot.set_numeric_function(normalized_var, normalized_numeric_fn, parameters=parameters)
            plot.render()
        
        return plot

    def parameter(self, symbols: Union[Symbol, Sequence[Symbol]], *, control: Optional[Any] = None, **control_kwargs: Any):
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

        See Also
        --------
        add_param : Backward-compatible alias.
        """
        result = self._params.parameter(symbols, control=control, **control_kwargs)
        self._sync_sidebar_visibility()
        return result
        

    def render(self, reason: str = "manual", trigger: Optional[ParamEvent] = None) -> None:
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
        self._log_render(reason, trigger)
        
        # 1. Update active-view plots
        for plot in self.plots.values():
            plot.render(view_id=self.active_view_id)

        # 1b. Mark inactive memberships stale on parameter changes.
        if reason == "param_change":
            for plot in self.plots.values():
                for view_id in plot.views:
                    if view_id != self.active_view_id:
                        self._views[view_id].is_stale = True

        # 2. Run hooks (if triggered by parameter change)
        # Note: ParameterManager triggers this render, then we run hooks.
        if reason == "param_change" and trigger:
            hooks = self._params.get_hooks()
            for h_id, callback in list(hooks.items()):
                try:
                    callback(trigger)
                except Exception as e:
                    warnings.warn(f"Hook {h_id} failed: {e}")

        self._info.schedule_info_update(reason=reason, trigger=trigger)

    def add_param(self, symbol: Symbol, **kwargs: Any) -> ParamRef:
        """
        Add a parameter manually.

        Parameters
        ----------
        symbol : sympy.Symbol
            Parameter symbol to create a slider for.
        **kwargs : Any
            Slider configuration (min, max, value, step).

        Returns
        -------
        ParamRef
            The created or reused parameter reference.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> fig.add_param(a, min=-2, max=2)  # doctest: +SKIP

        See Also
        --------
        parameter : Preferred API for parameter creation.
        """
        return self.parameter(symbol, **kwargs)

    def snapshot(self) -> FigureSnapshot:
        """Return an immutable snapshot of the entire figure state.

        The snapshot captures figure-level settings, full parameter metadata,
        plot symbolic expressions with styling, and static info card content.

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
        return FigureSnapshot(
            x_range=self.x_range,
            y_range=self.y_range,
            sampling_points=self.sampling_points or 500,
            title=self.title or "",
            parameters=self._params.snapshot(full=True),
            plots={pid: p.snapshot(id=pid) for pid, p in self.plots.items()},
            info_cards=self._info.snapshot(),
            views=tuple(
                ViewSnapshot(
                    id=view.id,
                    title=view.title,
                    x_label=view.x_label,
                    y_label=view.y_label,
                    x_range=view.default_x_range,
                    y_range=view.default_y_range,
                    viewport_x_range=view.viewport_x_range,
                    viewport_y_range=view.viewport_y_range,
                )
                for view in self._views.values()
            ),
            active_view_id=self.active_view_id,
        )

    def to_code(self, *, options: "CodegenOptions | None" = None) -> str:
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

    def get_code(self, options: "CodegenOptions | None" = None) -> str:
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
        spec: Union[str, Callable[["Figure", Any], str], Sequence[Union[str, Callable[["Figure", Any], str]]]],
        id: Optional[Hashable] = None,
        *,
        view: Optional[str] = None,
    ) -> None:
        """Create or replace a simple info card in the Info sidebar."""
        self._info.set_simple_card(spec=spec, id=id, view=view)
        self._sync_sidebar_visibility()

    def add_hook(self, callback: Callable[[Optional[ParamEvent]], Any], *, run_now: bool = True) -> Hashable:
        """Alias for :meth:`add_param_change_hook`.

        Parameters
        ----------
        callback : callable
            Function with signature ``(event)``.
        run_now : bool, optional
            Whether to run once immediately with a ``None`` event.

        Returns
        -------
        hashable
            The hook identifier used for registration.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.add_hook(lambda *_: None)  # doctest: +SKIP

        See Also
        --------
        add_param_change_hook : Full API with explicit hook IDs.
        """
        return self.add_param_change_hook(callback, hook_id=None, run_now=run_now)

    def add_param_change_hook(
        self,
        callback: Callable[[Optional[ParamEvent]], Any],
        hook_id: Optional[Hashable] = None,
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
        def _wrapped(event: Optional[ParamEvent]) -> Any:
            with _use_figure(self):
                return callback(event)

        hook_id = self._params.add_hook(_wrapped, hook_id)

        if run_now:
            try:
                self.render(reason="manual", trigger=None)
                _wrapped(None)
            except Exception as e:
                warnings.warn(f"Hook failed on init: {e}")

        return hook_id

    # --- Internal / Plumbing ---

    def _throttled_relayout(self, view_id: Optional[str] = None, *args: Any) -> None:
        """Queue relayout events through the per-view debouncing wrapper.

        Parameters
        ----------
        view_id : str or None, optional
            Target view identifier. ``None`` falls back to the active view for
            backward compatibility with older direct test calls.
        """
        target_view = self.active_view_id if view_id is None else str(view_id)
        debouncer = self._relayout_debouncers.get(target_view)
        if debouncer is not None:
            debouncer(*args)

    def _run_relayout(self, *_, view_id: Optional[str] = None) -> None:
        """Execute one relayout render from the queued debouncer.

        Parameters
        ----------
        view_id : str or None, optional
            Target view identifier. ``None`` falls back to the active view for
            backward compatibility.
        """
        target_view = self.active_view_id if view_id is None else str(view_id)
        if target_view == self.active_view_id:
            self.render(reason="relayout")
        elif target_view in self._views:
            self._views[target_view].is_stale = True

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
        # Simple rate-limited logging implementation
        now = time.monotonic()
        if logger.isEnabledFor(logging.INFO) and (now - self._render_info_last_log_t) > 1.0:
            self._render_info_last_log_t = now
            logger.info(f"render(reason={reason}) plots={len(self.plots)}")
        
        if logger.isEnabledFor(logging.DEBUG) and (now - self._render_debug_last_log_t) > 0.5:
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
        """
        self._has_been_displayed = True
        display(self._layout.output_widget)

    def __enter__(self) -> "Figure":
        """Enter a context where this figure is the current target.

        Returns
        -------
        Figure
            The same instance, for use with ``with`` blocks.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> with fig:  # doctest: +SKIP
        ...     pass

        See Also
        --------
        plot : Module-level helper that uses the current figure if available.
        """
        _push_current_figure(self)
        if self._print_capture is None:
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
            if self._print_capture is not None:
                self._print_capture.close()
                self._print_capture = None


class _CurrentParametersProxy(Mapping):
    """Module-level proxy to the current figure's ParameterManager.

    Examples
    --------
    >>> x, a = sp.symbols("x a")  # doctest: +SKIP
    >>> fig = Figure()  # doctest: +SKIP
    >>> with fig:  # doctest: +SKIP
    ...     parameter(a, min=-10, max=10)  # doctest: +SKIP
    ...     fig.plot(a * sp.sin(x), x)  # doctest: +SKIP
    ...     params[a].value = 5  # doctest: +SKIP
    """

    def _fig(self) -> "Figure":
        """Return the current Figure from the module stack."""
        return _require_current_figure()

    def _mgr(self) -> "ParameterManager":
        """Return the current figure's ParameterManager."""
        return self._fig().parameters

    def __getitem__(self, key: Hashable) -> ParamRef:
        """Return the current figure's parameter reference for ``key``."""
        return self._mgr()[key]

    def __iter__(self) -> Iterator[Hashable]:
        """Iterate parameter symbols from the active figure manager."""
        return iter(self._mgr())

    def __len__(self) -> int:
        """Return number of parameters on the active figure."""
        return len(self._mgr())

    def __contains__(self, key: object) -> bool:
        """Return whether ``key`` is present on the active figure."""
        return key in self._mgr()

    def __setitem__(self, key: Hashable, value: Any) -> None:
        """Set the active figure parameter value via mapping syntax."""
        self[key].value = value

    def parameter(
        self,
        symbols: Union[Symbol, Sequence[Symbol]],
        *,
        control: Optional[str] = None,
        **kwargs: Any,
    ) -> Union[ParamRef, Dict[Symbol, ParamRef]]:
        """Proxy to the current figure's :meth:`ParameterManager.parameter`."""
        return self._mgr().parameter(symbols, control=control, **kwargs)

    def snapshot(self, *, full: bool = False) -> ParameterValueSnapshot | ParameterSnapshot:
        """Return current-figure parameter values or full snapshot metadata."""
        return self._mgr().snapshot(full=full)

    def __getattr__(self, name: str) -> Any:
        """Forward unknown attributes/methods to active figure parameters."""
        return getattr(self._mgr(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Forward attribute assignment to active figure parameters."""
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(self._mgr(), name, value)


class _CurrentPlotsProxy(Mapping):
    """Module-level proxy to the current figure's plots mapping."""

    def _fig(self) -> "Figure":
        return _require_current_figure()

    def __getitem__(self, key: Hashable) -> Plot:
        return self._fig().plots[key]

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self._fig().plots)

    def __len__(self) -> int:
        return len(self._fig().plots)

    def __contains__(self, key: object) -> bool:
        return key in self._fig().plots


parameters = _CurrentParametersProxy()
params = parameters
plots = _CurrentPlotsProxy()


def set_title(text: str) -> None:
    """Set the title of the current figure."""
    _require_current_figure().title = text


def get_title() -> str:
    """Get the title of the current figure."""
    return _require_current_figure().title

def render(reason: str = "manual", trigger: Optional[ParamEvent] = None) -> None:
    """Render the current figure.

    Parameters
    ----------
    reason : str, optional
        Render reason string for logging/debugging.
    trigger : ParamEvent or None, optional
        Optional event payload forwarded to :meth:`Figure.render`.
    """
    _require_current_figure().render(reason=reason, trigger=trigger)


def info(
    spec: Union[str, Callable[[Figure, Any], str], Sequence[Union[str, Callable[[Figure, Any], str]]]],
    id: Optional[Hashable] = None,
    *,
    view: Optional[str] = None,
) -> None:
    """Create or replace a simplified info card on the current figure."""
    _require_current_figure().info(spec=spec, id=id, view=view)


def set_x_range(value: RangeLike) -> None:
    """Set x-axis range on the current figure."""
    _require_current_figure().x_range = value


def get_x_range() -> Tuple[float, float]:
    """Get x-axis range from the current figure."""
    return _require_current_figure().x_range


def set_y_range(value: RangeLike) -> None:
    """Set y-axis range on the current figure."""
    _require_current_figure().y_range = value


def get_y_range() -> Tuple[float, float]:
    """Get y-axis range from the current figure."""
    return _require_current_figure().y_range


def set_sampling_points(value: Union[int, str, _FigureDefaultSentinel, None]) -> None:
    """Set default sampling points on the current figure."""
    _require_current_figure().sampling_points = value


def get_sampling_points() -> Optional[int]:
    """Get default sampling points from the current figure."""
    return _require_current_figure().sampling_points


def plot_style_options() -> Dict[str, str]:
    """Return discoverable Figure plot-style options.

    Returns
    -------
    dict[str, str]
        Mapping of style keyword names to descriptions.

    Notes
    -----
    Current supported shortcut keys are: ``color``, ``thickness``/``width``, ``dash``,
    ``opacity``/``alpha``, ``line``, and ``trace``.
    """
    return Figure.plot_style_options()



def parameter(
    symbols: Union[Symbol, Sequence[Symbol]],
    *,
    control: Optional[str] = None,
    **kwargs: Any,
) -> Union[ParamRef, Dict[Symbol, ParamRef]]:
    """Ensure parameter(s) exist on the current figure and return their refs.

    Parameters
    ----------
    symbols : sympy.Symbol or sequence[sympy.Symbol]
        Parameter symbol(s) to create or reuse.
    control : str or None, optional
        Optional control identifier passed to the underlying manager.
    **kwargs : Any
        Control configuration (min, max, value, step).

    Returns
    -------
    ParamRef or dict[Symbol, ParamRef]
        Parameter reference(s) for the requested symbol(s).

    Examples
    --------
    >>> import sympy as sp  # doctest: +SKIP
    >>> x, a = sp.symbols("x a")  # doctest: +SKIP
    >>> fig = Figure()  # doctest: +SKIP
    >>> with fig:  # doctest: +SKIP
    ...     parameter(a, min=-1, max=1)  # doctest: +SKIP

    Notes
    -----
    This helper requires an active figure context (see :meth:`Figure.__enter__`).

    See Also
    --------
    Figure.parameter : Instance method for parameter creation.
    """
    fig = _require_current_figure()
    return fig.parameters.parameter(symbols, control=control, **kwargs)


def plot(
    func: Any,
    var: Any,
    parameters: Optional[Sequence[Symbol]] = None,
    id: Optional[str] = None,
    label: Optional[str] = None,
    visible: VisibleSpec = True,
    x_domain: Optional[RangeLike] = None,
    sampling_points: Optional[Union[int, str]] = None,
    color: Optional[str] = None,
    thickness: Optional[Union[int, float]] = None,
    width: Optional[Union[int, float]] = None,
    dash: Optional[str] = None,
    opacity: Optional[Union[int, float]] = None,
    alpha: Optional[Union[int, float]] = None,
    line: Optional[Mapping[str, Any]] = None,
    trace: Optional[Mapping[str, Any]] = None,
    view: Optional[Union[str, Sequence[str]]] = None,
    vars: Optional[PlotVarsSpec] = None,
) -> Plot:
    """
    Plot an expression/callable on the current figure, or create a new figure per call.

    Parameters
    ----------
    func : callable or NumericFunction or sympy.Expr
        Function/expression to plot.
    var : sympy.Symbol or tuple
        Plot variable ``x`` or ``(x, min, max)`` range tuple.
    parameters : sequence[sympy.Symbol], optional
        Deprecated. Use :func:`parameter` / :data:`parameters` for explicit
        control registration. If omitted, symbols are inferred.
    id : str, optional
        Plot identifier for update or creation.
    label : str, optional
        Legend label for the trace. If omitted, new plots default to ``id``;
        existing plots keep their current label.
    visible : bool or "legendonly", optional
        Plotly visibility state for the trace. Hidden traces skip sampling
        until shown.
    x_domain : RangeLike or None, optional
        Explicit x-domain override.
    sampling_points : int or str, optional
        Number of samples, or ``"figure_default"`` to inherit from the figure.
    color : str or None, optional
        Line color. Common formats include named colors (e.g., ``"red"``),
        hex values (e.g., ``"#ff0000"``), and ``rgb(...)``/``rgba(...)``.
    thickness : int or float, optional
        Line width in pixels. ``1`` is thin; larger values produce thicker lines.
    width : int or float, optional
        Alias for ``thickness``.
    dash : str or None, optional
        Line pattern. Supported values: ``"solid"``, ``"dot"``, ``"dash"``,
        ``"longdash"``, ``"dashdot"``, ``"longdashdot"``.
    line : mapping or None, optional
        Extra per-line style fields as a mapping (advanced usage).
    opacity : int or float, optional
        Overall curve opacity between ``0.0`` (fully transparent) and
        ``1.0`` (fully opaque).
    alpha : int or float, optional
        Alias for ``opacity``.
    trace : mapping or None, optional
        Extra full-trace style fields as a mapping (advanced usage).

    Returns
    -------
    Plot
        The created or updated plot instance.

    Examples
    --------
    >>> x, a = sp.symbols("x a")  # doctest: +SKIP
    >>> parameter(a, min=-1, max=1)  # doctest: +SKIP
    >>> plot(a * sp.sin(x), x, id="a_sin")  # doctest: +SKIP
    >>> plot(sp.sin(x), x, id="sin")  # doctest: +SKIP

    Notes
    -----
    If no current figure is active, this function creates and displays a new
    :class:`Figure`.

    All supported style options for this helper are discoverable via
    :func:`plot_style_options`.

    See Also
    --------
    Figure.plot : Instance method with the same signature.
    plot_style_options : List supported style kwargs and meanings
        (`color`, `thickness`, `width`, `dash`, `opacity`, `alpha`, `line`, `trace`).
    """
    fig = _current_figure()
    if fig is None:
        fig = Figure()
        display(fig)
    return fig.plot(
        func,
        var,
        parameters=parameters,
        id=id,
        label=label,
        visible=visible,
        x_domain=x_domain,
        sampling_points=sampling_points,
        color=color,
        thickness=thickness,
        width=width,
        dash=dash,
        line=line,
        opacity=opacity,
        alpha=alpha,
        trace=trace,
        view=view,
        vars=vars,
    )
