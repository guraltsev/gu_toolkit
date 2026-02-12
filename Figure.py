"""Core Figure plotting system for interactive symbolic exploration.

The module hosts the coordinator class, plot abstraction, layout/parameter/info
managers, and notebook helper functions used to build responsive, parameterized
Plotly visualizations from SymPy expressions.
"""

from __future__ import annotations

# NOTE: This file is Figure.py with the Info Components API implemented.
#       It is intended as a drop-in replacement.

"""Widgets and interactive plotting helpers for math exploration in Jupyter.

This file defines two main ideas:

1) OneShotOutput
   A small safety wrapper around ``ipywidgets.Output`` that can only be displayed once.
   This prevents a common notebook confusion: accidentally displaying the *same* widget
   in multiple places and then wondering which one is “live”.

2) Figure (+ Plot)
   A thin, student-friendly wrapper around ``plotly.graph_objects.FigureWidget`` that:
   - plots SymPy expressions by compiling them to NumPy via ``numpify_cached``,
   - supports interactive parameter sliders (via ``FloatSlider``),
   - optionally provides an *Info* area (a stack of ``ipywidgets.Output`` widgets),
   - re-renders automatically when you pan/zoom (throttled) or move a slider.

The intended workflow is:

- define symbols with SymPy (e.g. ``x, a = sp.symbols("x a")``),
- create a ``Figure``,
- add one or more plots with ``Figure.plot(...)``,
- optionally add parameters (sliders) explicitly by passing ``parameters=[a, ...]``.
- otherwise, parameters are autodetected from the expression (all free symbols that are not the plot variable) and added automatically.

---------------------------------------------------------------------------
Quick start (in a Jupyter notebook)
---------------------------------------------------------------------------

>>> import sympy as sp
>>> from Figure import Figure  # wherever this file lives
>>>
>>> x, a = sp.symbols("x a")
>>> fig = Figure(x_range=(-6, 6), y_range=(-3, 3))
>>> fig.plot(x, sp.sin(x), id="sin")
>>> fig.plot(x, a*sp.cos(x), id="a_cos")  # adds a slider for a
>>> fig.title = "Sine and a·Cosine"
>>> fig  # display in the output cell (or use display(fig))

Tip: if you omit ``parameters`` when calling ``plot``, Figure will infer them
from the expression and create sliders automatically. Pass ``[]`` to disable that.

Info panel
----------
The sidebar has two sections:

- **Parameters**: auto-created sliders for SymPy symbols.
- **Info**: a container that holds *Output widgets* created by
  :meth:`Figure.get_info_output`. This design is deliberate: printing directly
  into a container widget is ambiguous in Jupyter, but printing into an
  ``Output`` widget is well-defined.
  Info outputs are keyed by id, so you can retrieve them via
  ``fig.info_output[id]`` or create/reuse them via ``fig.get_info_output(id)``.

Notes for students
------------------
- SymPy expressions are symbolic. They are like *formulas*.
- Plotly needs numerical values (arrays of numbers).
- ``numpify_cached`` bridges the two: it turns a SymPy expression into a NumPy-callable function.
- Sliders provide the numeric values of parameters like ``a`` in real time.

Architecture Note (For Developers)
----------------------------------
To avoid a "God Object," responsibilities are split via composition:
- Figure: The main coordinator/facade.
- FigureLayout: Handles all UI/Widget construction, CSS/JS injection, and layout logic.
- ParameterManager: Handles slider creation, storage, and change hooks. Acts as a dict proxy.
- InfoPanelManager: Handles the info sidebar and component registry.
- Plot: Handles the specific math-to-trace rendering logic.


Logging / debugging
-------------------
This module uses the standard Python ``logging`` framework (no prints). By default it installs a
``NullHandler``, so you will see nothing unless you configure logging.

In a Jupyter/JupyterLab notebook, enable logs like this:

    import logging
    logging.basicConfig(level=logging.INFO)   # or logging.DEBUG

To limit output to just this module, set its logger level instead:

    import logging
    logging.getLogger(__name__).setLevel(logging.DEBUG)

Notes:
- INFO render messages are rate-limited to ~1.0s.
- DEBUG range messages (x_range/y_range) are rate-limited to ~0.5s.
"""

import re
import time
import asyncio
import threading
import warnings
import logging
from contextlib import ExitStack, contextmanager
from collections.abc import Mapping
from typing import Any, Callable, Hashable, Optional, Sequence, Tuple, Union, Dict, Iterator, List

import ipywidgets as widgets
import numpy as np
import plotly.graph_objects as go
import sympy as sp
from IPython.display import display
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

# Internal imports (assumed to exist in the same package)
from .InputConvert import InputConvert
from .numpify import NumpifiedFunction, numpify_cached
from .PlotlyPane import PlotlyPane, PlotlyPaneStyle
from .Slider import FloatSlider
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .ParameterSnapshot import ParameterSnapshot
from .NumericExpression import PlotView


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
from .figure_plot import Plot

# -----------------------------
# Small type aliases
# -----------------------------
NumberLike = Union[int, float]
NumberLikeOrStr = Union[int, float, str]
RangeLike = Tuple[NumberLikeOrStr, NumberLikeOrStr]
VisibleSpec = Union[bool, str]  # Plotly uses True/False or the string "legendonly".

PLOT_STYLE_OPTIONS: Dict[str, str] = {
    "color": "Line color. Accepts CSS-like names (e.g., red), hex (#RRGGBB), or rgb()/rgba() strings.",
    "thickness": "Line width in pixels. Larger values draw thicker lines.",
    "dash": "Line pattern. Supported values: solid, dot, dash, longdash, dashdot, longdashdot.",
    "opacity": "Overall trace opacity from 0.0 (fully transparent) to 1.0 (fully opaque).",
    "line": "Extra line-style fields as a mapping (for advanced per-line styling).",
    "trace": "Extra trace fields as a mapping (for advanced full-trace styling).",
}

# SECTION: Figure (The Coordinator) [id: Figure]
# =============================================================================

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
    >>> fig.plot(x, a*sp.sin(x), parameters=[a], id="a_sin")
    >>> fig
    """
    
    __slots__ = [
        "_layout", "_params", "_info", "_figure", "_pane", "plots",
        "_x_range", "_y_range", "_sampling_points", "_debug",
        "_last_relayout", "_render_info_last_log_t", "_render_debug_last_log_t",
        "_relayout_pending", "_relayout_timer", "_relayout_lock", "_relayout_deadline",
        "_has_been_displayed", "_print_capture"
    ]

    def __init__(
        self,
        sampling_points: int = 500,
        x_range: RangeLike = (-4, 4),
        y_range: RangeLike = (-3, 3),
        debug: bool = False,
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

        # 3. Initialize Plotly Figure
        self._figure = go.FigureWidget()
        self._figure.update_layout(
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
        self._pane = PlotlyPane(
            self._figure,
            style=PlotlyPaneStyle(
                padding_px=8,
                border="1px solid rgba(15,23,42,0.08)",
                border_radius_px=10,
                overflow="hidden",
            ),
            autorange_mode="none",
            defer_reveal=True,
        )
        self._layout.set_plot_widget(self._pane.widget, reflow_callback=self._pane.reflow)

        # 4. Set Initial State
        self.x_range = x_range
        self.y_range = y_range
        
        # 5. Bind Events
        self._last_relayout = time.monotonic() - 0.5
        self._render_info_last_log_t = 0.0
        self._render_debug_last_log_t = 0.0
        self._relayout_pending = False
        self._relayout_timer = None
        self._relayout_deadline = 0.0
        self._relayout_lock = threading.Lock()
        self._figure.layout.on_change(
            self._throttled_relayout,
            "xaxis.range", "xaxis.range[0]", "xaxis.range[1]",
            "yaxis.range", "yaxis.range[0]", "yaxis.range[1]",
        )

    # --- Properties ---

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
        """Access the underlying Plotly FigureWidget.

        Returns
        -------
        plotly.graph_objects.FigureWidget
            The interactive Plotly widget.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> isinstance(fig.figure_widget, go.FigureWidget)  # doctest: +SKIP
        True

        Notes
        -----
        Directly mutating the widget is supported, but changes may bypass
        Figure's helper methods.
        """
        return self._figure
    
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

        See Also
        --------
        get_info_output : Create or fetch an info output widget.
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
        return self._x_range
    
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
        This updates the Plotly axis range immediately.
        """
        self._x_range = (float(InputConvert(value[0], float)), float(InputConvert(value[1], float)))
        self._figure.update_xaxes(range=self._x_range)

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
        return self._y_range
    
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
        This updates the Plotly axis range immediately.
        """
        self._y_range = (float(InputConvert(value[0], float)), float(InputConvert(value[1], float)))
        self._figure.update_yaxes(range=self._y_range)

    @property
    def current_x_range(self) -> Optional[Tuple[float, float]]:
        """Return the current viewport x-range (read-only).

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
        return self._figure.layout.xaxis.range

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
        return self._figure.layout.yaxis.range
    
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
        Current supported shortcut keys are: ``color``, ``thickness``,
        ``dash``, ``opacity``, ``line``, and ``trace``.
        """
        return dict(PLOT_STYLE_OPTIONS)

    def plot(
        self,
        var: Symbol,
        func: Expr,
        parameters: Optional[Sequence[Symbol]] = None,
        id: Optional[str] = None,
        x_domain: Optional[RangeLike] = None,
        sampling_points: Optional[Union[int, str]] = None,
        color: Optional[str] = None,
        thickness: Optional[Union[int, float]] = None,
        dash: Optional[str] = None,
        line: Optional[Mapping[str, Any]] = None,
        opacity: Optional[Union[int, float]] = None,
        trace: Optional[Mapping[str, Any]] = None,
    ) -> Plot:
        """
        Plot a SymPy expression on the figure (and keep it “live”).

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable (e.g. ``x``).
        func : sympy.Expr
            SymPy expression (e.g. ``sin(x)``).
        parameters : list[sympy.Symbol] or None, optional
            Parameter symbols. If None, they are inferred from the expression.
            If [], that means explicitly no parameters. Parameter creation and
            updates are delegated to :class:`ParameterManager` (refactored API).
        x_domain : RangeLike or None, optional
            Domain of the independent variable (e.g. ``(-10, 10)``).
            If "figure_default", the figure's range is used when plotting. 
            If None, it is the same as "figure_default" for new plots while no change for existing plots.
        id : str, optional
            Unique identifier. If exists, the existing plot is updated in-place.

        sampling_points : int or str, optional
            Number of sampling points for this plot. Use ``"figure_default"``
            to inherit from the figure setting.
        color : str or None, optional
            Line color. Common formats include named colors (e.g., ``"red"``),
            hex values (e.g., ``"#ff0000"``), and ``rgb(...)``/``rgba(...)``.
        thickness : int or float, optional
            Line width in pixels. ``1`` is thin; larger values produce thicker lines.
        dash : str or None, optional
            Line pattern. Supported values: ``"solid"``, ``"dot"``, ``"dash"``,
            ``"longdash"``, ``"dashdot"``, ``"longdashdot"``.
        line : mapping or None, optional
            Extra per-line style fields as a mapping (advanced usage).
        opacity : int or float, optional
            Overall curve opacity between ``0.0`` (fully transparent) and
            ``1.0`` (fully opaque).
        trace : mapping or None, optional
            Extra full-trace style fields as a mapping (advanced usage).

        Returns
        -------
        Plot
            The created or updated plot instance.

        Examples
        --------
        >>> x, a = sp.symbols("x a")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.plot(x, a * sp.sin(x), parameters=[a], id="a_sin")  # doctest: +SKIP

        Notes
        -----
        Passing ``parameters=[]`` disables automatic parameter creation even if
        the expression has free symbols other than ``var``.

        All supported style options for this method are discoverable via
        :meth:`Figure.plot_style_options`.

        See Also
        --------
        parameter : Create sliders without plotting.
        plot_style_options : List supported style kwargs and meanings
            (`color`, `thickness`, `dash`, `opacity`, `line`, `trace`).
        """
        # ID Generation
        if id is None:
            for i in range(100):
                if f"f_{i}" not in self.plots:
                    id = f"f_{i}"
                    break
            if id is None: raise ValueError("Too many auto-generated IDs")

        # Parameter Autodetection
        if parameters is None:
            parameters = sorted([s for s in func.free_symbols if s != var], key=lambda s: s.sort_key())

        # Ensure Parameters Exist (Delegate to Manager)
        if parameters:
            self.parameter(parameters)
        
        # Update UI visibility
        self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)

        # Create or Update Plot
        if id in self.plots:
            update_dont_create = True
        else: 
            update_dont_create = False

        if update_dont_create:
            self.plots[id].update(
                var=var,
                func=func,
                parameters=parameters,
                x_domain=x_domain,
                sampling_points=sampling_points,
                color=color,
                thickness=thickness,
                dash=dash,
                line=line,
                opacity=opacity,
                trace=trace,
            )
            plot = self.plots[id]    
        else: 
            plot = Plot(
                var=var, func=func, smart_figure=self, parameters=parameters,
                x_domain=x_domain, sampling_points=sampling_points, label=id,
                color=color, thickness=thickness, dash=dash, line=line, opacity=opacity, trace=trace
            )
            self.plots[id] = plot
        
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
        self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)
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
        
        # 1. Update all plots
        for plot in self.plots.values():
            plot.render()
        
        # 2. Run hooks (if triggered by parameter change)
        # Note: ParameterManager triggers this render, then we run hooks.
        if reason == "param_change" and trigger:
            hooks = self._params.get_hooks()
            for h_id, callback in list(hooks.items()):
                try:
                    callback(trigger)
                except Exception as e:
                    warnings.warn(f"Hook {h_id} failed: {e}")

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

    def get_info_output(self, id: Optional[Hashable] = None, **kwargs: Any) -> widgets.Output:
        """
        Create (or retrieve) an Output widget in the Info sidebar.

        Parameters
        ----------
        id : hashable, optional
            Unique identifier for the output. If omitted, a new ID is generated.
        **kwargs : Any
            Layout keyword arguments for ``ipywidgets.Layout``.

        Returns
        -------
        ipywidgets.Output
            Output widget for the info panel.

        Examples
        --------
        >>> fig = Figure()  # doctest: +SKIP
        >>> out = fig.get_info_output("summary")  # doctest: +SKIP

        Notes
        -----
        Output widgets are added to the sidebar in the order they are created.
        """
        out = self._info.get_output(id, **kwargs)
        self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)
        return out

    # Alias for backward compatibility
    new_info_output = get_info_output

    def add_info_component(self, id: Hashable, component_factory: Callable, hook_id: Optional[Hashable] = None, **kwargs: Any) -> Any:
        """
        Register (or replace) a stateful *info component*.

        An info component is a class/function that:
        1. Draws into an Info Output widget.
        2. Implements an `update(event, fig, out)` method.

        Parameters
        ----------
        id : hashable
            Unique identifier for the component.
        component_factory : callable
            Callable that accepts ``(out, fig)`` and returns a component instance.
        hook_id : hashable, optional
            Hook identifier for updates; defaults to ``("info_component", id)``.
        **kwargs : Any
            Layout keyword arguments forwarded to the output widget.

        Returns
        -------
        Any
            The created component instance.

        Examples
        --------
        >>> class ExampleComponent:  # doctest: +SKIP
        ...     def __init__(self, out, fig):  # doctest: +SKIP
        ...         self.out = out  # doctest: +SKIP
        ...     def update(self, event, fig, out):  # doctest: +SKIP
        ...         pass  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> fig.add_info_component("example", ExampleComponent)  # doctest: +SKIP

        Notes
        -----
        Components are updated via hooks registered in
        :meth:`add_param_change_hook`.
        """
        out = self.get_info_output(id, **kwargs)
        inst = component_factory(out, self)
        
        if not hasattr(inst, 'update'):
            raise TypeError(f"Component {id} must have an 'update' method")
        
        self._info.add_component(id, inst)
        
        # Register hook to update component on param change
        if hook_id is None: hook_id = ("info_component", id)
        
        def _hook(event: Optional[ParamEvent]) -> None:
            inst.update(event, self, out)
            
        self.add_param_change_hook(_hook, hook_id=hook_id)
        return inst

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

    def _throttled_relayout(self, *args: Any) -> None:
        """Handle relayout events with leading+trailing throttling.

        The first event outside the throttle window renders immediately
        (leading edge). Events that arrive inside the 0.5s window are
        coalesced and schedule at most one deferred render at the end of
        that window (trailing edge).

        Parameters
        ----------
        *args : Any
            Plotly relayout event payload (unused).

        Returns
        -------
        None
        """
        now = time.monotonic()
        should_render_now = False

        with self._relayout_lock:
            elapsed = now - self._last_relayout
            if elapsed > 0.5:
                self._last_relayout = now
                self._relayout_pending = False

                if self._relayout_timer is not None:
                    self._relayout_timer.cancel()
                    self._relayout_timer = None

                self._relayout_deadline = 0.0
                should_render_now = True
            else:
                self._relayout_pending = True
                if self._relayout_timer is None:
                    remaining = max(0.0, 0.5 - elapsed)
                    self._relayout_deadline = now + remaining
                    self._schedule_trailing_relayout(remaining)

        if should_render_now:
            self.render(reason="relayout")

    def _schedule_trailing_relayout(self, delay_s: float) -> None:
        """Schedule one trailing relayout callback on the active event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            timer = threading.Timer(delay_s, self._trailing_relayout)
            timer.daemon = True
            self._relayout_timer = timer
            timer.start()
            return

        self._relayout_timer = loop.call_later(delay_s, self._trailing_relayout)

    def _trailing_relayout(self) -> None:
        """Run one deferred relayout render when burst activity occurred."""
        with self._relayout_lock:
            self._relayout_timer = None
            self._relayout_deadline = 0.0
            if not self._relayout_pending:
                return

            self._relayout_pending = False
            self._last_relayout = time.monotonic()

        self.render(reason="relayout")

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
    ...     fig.plot(x, a * sp.sin(x), parameters=[a])  # doctest: +SKIP
    ...     params[a].value = 5  # doctest: +SKIP
    ...     parameter(a, min=-10, max=10)  # doctest: +SKIP
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

    def snapshot(self, *, full: bool = False) -> Dict[Symbol, Any] | ParameterSnapshot:
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


def get_info_output(id: Optional[Hashable] = None, **kwargs: Any) -> widgets.Output:
    """Return or create an output widget in the current figure's info panel."""
    return _require_current_figure().get_info_output(id=id, **kwargs)


def add_info_component(
    id: Hashable,
    component_factory: Callable,
    hook_id: Optional[Hashable] = None,
    **kwargs: Any,
) -> Any:
    """Register an info component on the current figure and return it."""
    return _require_current_figure().add_info_component(
        id,
        component_factory,
        hook_id=hook_id,
        **kwargs,
    )


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
    Current supported shortcut keys are: ``color``, ``thickness``, ``dash``,
    ``opacity``, ``line``, and ``trace``.
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
    var: Symbol,
    func: Expr,
    parameters: Optional[Sequence[Symbol]] = None,
    id: Optional[str] = None,
    x_domain: Optional[RangeLike] = None,
    sampling_points: Optional[Union[int, str]] = None,
    color: Optional[str] = None,
    thickness: Optional[Union[int, float]] = None,
    dash: Optional[str] = None,
    opacity: Optional[Union[int, float]] = None,
    line: Optional[Mapping[str, Any]] = None,
    trace: Optional[Mapping[str, Any]] = None,
) -> Plot:
    """
    Plot a SymPy expression on the current figure, or create a new figure per call.

    Parameters
    ----------
    var : sympy.Symbol
        Independent variable for the expression.
    func : sympy.Expr
        SymPy expression to plot.
    parameters : sequence[sympy.Symbol], optional
        Parameter symbols used in the expression. If ``None``, they are inferred.
    id : str, optional
        Plot identifier for update or creation.
    x_domain : RangeLike or None, optional
        Explicit x-domain override.
    sampling_points : int or str, optional
        Number of samples, or ``"figure_default"`` to inherit from the figure.
    color : str or None, optional
        Line color. Common formats include named colors (e.g., ``"red"``),
        hex values (e.g., ``"#ff0000"``), and ``rgb(...)``/``rgba(...)``.
    thickness : int or float, optional
        Line width in pixels. ``1`` is thin; larger values produce thicker lines.
    dash : str or None, optional
        Line pattern. Supported values: ``"solid"``, ``"dot"``, ``"dash"``,
        ``"longdash"``, ``"dashdot"``, ``"longdashdot"``.
    line : mapping or None, optional
        Extra per-line style fields as a mapping (advanced usage).
    opacity : int or float, optional
        Overall curve opacity between ``0.0`` (fully transparent) and
        ``1.0`` (fully opaque).
    trace : mapping or None, optional
        Extra full-trace style fields as a mapping (advanced usage).

    Returns
    -------
    Plot
        The created or updated plot instance.

    Examples
    --------
    >>> x, a = sp.symbols("x a")  # doctest: +SKIP
    >>> plot(x, a * sp.sin(x), parameters=[a], id="a_sin")  # doctest: +SKIP

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
        (`color`, `thickness`, `dash`, `opacity`, `line`, `trace`).
    """
    fig = _current_figure()
    if fig is None:
        fig = Figure()
        display(fig)
    return fig.plot(
        var,
        func,
        parameters=parameters,
        id=id,
        x_domain=x_domain,
        sampling_points=sampling_points,
        color=color,
        thickness=thickness,
        dash=dash,
        line=line,
        opacity=opacity,
        trace=trace,
    )

