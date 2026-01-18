from __future__ import annotations

# NOTE: This file is SmartFigure.py with the Info Components API implemented.
#       It is intended as a drop-in replacement.

"""Widgets and interactive plotting helpers for math exploration in Jupyter.

This file defines two main ideas:

1) OneShotOutput
   A small safety wrapper around ``ipywidgets.Output`` that can only be displayed once.
   This prevents a common notebook confusion: accidentally displaying the *same* widget
   in multiple places and then wondering which one is “live”.

2) SmartFigure (+ SmartPlot)
   A thin, student-friendly wrapper around ``plotly.graph_objects.FigureWidget`` that:
   - plots SymPy expressions by compiling them to NumPy via ``numpify_cached``,
   - supports interactive parameter sliders (via ``SmartFloatSlider``),
   - optionally provides an *Info* area (a stack of ``ipywidgets.Output`` widgets),
   - re-renders automatically when you pan/zoom (throttled) or move a slider.

The intended workflow is:

- define symbols with SymPy (e.g. ``x, a = sp.symbols("x a")``),
- create a ``SmartFigure``,
- add one or more plots with ``SmartFigure.plot(...)``,
- optionally add parameters (sliders) explicitly by passing ``parameters=[a, ...]``.
- otherwise, parameters are autodetected from the expression (all free symbols that are not the plot variable) and added automatically.

---------------------------------------------------------------------------
Quick start (in a Jupyter notebook)
---------------------------------------------------------------------------

>>> import sympy as sp
>>> from SmartFigure import SmartFigure  # wherever this file lives
>>>
>>> x, a = sp.symbols("x a")
>>> fig = SmartFigure(x_range=(-6, 6), y_range=(-3, 3))
>>> fig.plot(x, sp.sin(x), id="sin")
>>> fig.plot(x, a*sp.cos(x), id="a_cos")  # adds a slider for a
>>> fig.title = "Sine and a·Cosine"
>>> fig  # display in the output cell (or use display(fig))

Tip: if you omit ``parameters`` when calling ``plot``, SmartFigure will infer them
from the expression and create sliders automatically. Pass ``[]`` to disable that.

Info panel
----------
The sidebar has two sections:

- **Parameters**: auto-created sliders for SymPy symbols.
- **Info**: a container that holds *Output widgets* created by
  :meth:`SmartFigure.new_info_output`. This design is deliberate: printing directly
  into a container widget is ambiguous in Jupyter, but printing into an
  ``Output`` widget is well-defined.
  Info outputs are keyed by id, so you can retrieve them via
  ``fig.info_output[id]`` or create/reuse them via ``fig.new_info_output(id)``.

Notes for students
------------------
- SymPy expressions are symbolic. They are like *formulas*.
- Plotly needs numerical values (arrays of numbers).
- ``numpify_cached`` bridges the two: it turns a SymPy expression into a NumPy-callable function.
- Sliders provide the numeric values of parameters like ``a`` in real time.

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

# === SECTION: OneShotOutput [id: OneShotOutput]===

import re
import time
import warnings
import logging
from typing import Any, Callable, Hashable, Optional, Sequence, Tuple, Union

import ipywidgets as widgets
import numpy as np
import plotly.graph_objects as go
import sympy as sp
from IPython.display import Javascript, display
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

from .InputConvert import InputConvert
from .numpify import numpify_cached


# Module logger
# - Uses a NullHandler so importing this module never configures global logging.
# - Callers can enable logs via standard logging configuration.
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


# -----------------------------
# Small type aliases
# -----------------------------
NumberLike = Union[int, float]
NumberLikeOrStr = Union[int, float, str]
RangeLike = Tuple[NumberLikeOrStr, NumberLikeOrStr]
VisibleSpec = Union[bool, str]  # Plotly uses True/False or the string "legendonly".

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

    Notes
    -----
    - Inherits from ``ipywidgets.Output``.
    - Uses ``__slots__`` for a tiny memory optimization.
    - Designed for Jupyter Notebook / JupyterLab.

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
        """Initialize a new OneShotOutput widget."""
        super().__init__()
        self._displayed = False

    def _repr_mimebundle_(
        self,
        include: Any = None,
        exclude: Any = None,
        **kwargs: Any,
    ) -> Any:
        """
        IPython rich display hook used by ipywidgets.

        This is what gets called when the widget is displayed (including via
        `display(self)` or by being the last expression in a cell).
        """
        if self._displayed:
            raise RuntimeError(
                "OneShotOutput has already been displayed. "
                "This widget supports only one-time display."
            )
        self._displayed = True
        bundle = super()._repr_mimebundle_(include=include, exclude=exclude, **kwargs)
        return bundle

    @property
    def has_been_displayed(self) -> bool:
        """
        Check if the widget has been displayed.

        Returns
        -------
        bool
            True if the widget has been displayed, False otherwise.
        """
        return self._displayed

    def reset_display_state(self) -> None:
        """
        Reset the display state to allow re-display.

        Warning
        -------
        This method should be used with caution as it bypasses the
        one-time display protection.
        """
        self._displayed = False


# === END SECTION: OneShotOutput [id: OneShotOutput]===


# === SECTION: SmartFigure [id: SmartFigure]===

# Architecture note:
# - SmartFigure is the coordinator: it owns the Plotly FigureWidget, UI panels, and
#   the parameter widgets. It renders all plots in response to UI changes.
# - SmartPlot is the leaf unit: one curve + one Plotly trace. It compiles SymPy
#   to NumPy via numpify_cached and asks SmartFigure for current parameter values.
# This separation keeps UI concerns in SmartFigure and math/rendering in SmartPlot.


class SmartPlot:
    """
    A single plotted curve managed by a :class:`SmartFigure`.

    Conceptually, a ``SmartPlot`` is “one function on one set of axes”.
    It owns a single Plotly trace (a line plot) and knows how to:

    - compile the SymPy expression to a fast NumPy function (via ``numpify_cached``),
    - sample x-values on an appropriate domain,
    - evaluate y-values (including current slider parameter values),
    - push the sampled data into the Plotly trace.

    Notes for students
    ------------------
    - ``var`` is the independent variable (a SymPy symbol like ``x``).
    - ``func`` is a SymPy expression like ``sin(x)`` or ``a*x**2``.
    - Parameters (like ``a``) are SymPy symbols whose values come from sliders.

    Important behavior
    ------------------
    ``render()`` will **not** compute anything if the plot is not visibly drawn.
    In this code, that means:
    - if ``self.visible`` is exactly ``True``, it renders;
    - if ``self.visible`` is ``False`` or ``"legendonly"``, it skips computation.

    This is useful for performance in interactive notebooks.

    Public API
    ----------
    The following are “public” (no leading underscore):
    - constructor ``__init__``
    - ``set_func``
    - properties ``var``, ``parameters``, ``func`` are read-only
        To change them, use ``set_func``
    - properties ``label``
        Read/write, changes the label in the legend
    - ``x_domain``
        Sets the domain of the x-axis, no data will be rendered outside of this range, whatever the viewport is.
        To make it unlimited, use ``None``.
    ``sampling_points`` are read/write
        Number of sampling points for the plot.
        Set to ``None`` to use the default number of samples of the figure.
        Useful mainly if the function is expensive to evaluate or (set it smaller than the default), or
        if the function changes significantly (set it larger than the default).
        Changing the parameter triggers a re-render
    - ``visible``
        Read/write, changes the visibility of the plot. Possible values are:
            - True (visible),
            - False (hidden in plot and legend),
            - "legendonly" (not drawn, but shown in legend).
        Clicking on the legend entry will toggle the visibility between "visible" and "legendonly".
    - ``compute_data``
        Recomputes the data (x-values and y-values)
    - ``render``
        Pushes the data into the Plotly trace
    - ``update``
        Updates all aspects of the plot

    Examples
    --------
    Typically you do not create ``SmartPlot`` directly; you call ``SmartFigure.plot``.

    >>> import sympy as sp
    >>> x = sp.Symbol("x")
    >>> fig = SmartFigure()
    >>> display(fig)  # display Figure in the output cell
    >>> p = fig.plot(x, sp.sin(x), parameters=[], id="sin")
    >>> p.label
    'sin'


    Limit the evaluation domain:

    >>> p.x_domain = (-10, 10)  # compute on a wider domain than the current viewport

    Change sampling density for this plot only:

    >>> p.sampling_points = 2000
    """

    def __init__(
        self,
        var: Symbol,
        func: Expr,
        smart_figure: SmartFigure,
        parameters: Optional[Sequence[Symbol]] = None,
        x_domain: Optional[RangeLike] = None,
        sampling_points: Optional[int] = None,
        label: str = "",
        visible: VisibleSpec = True,
    ) -> None:
        """
        Create a new SmartPlot instance.

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable.
        func : sympy.Expr
            SymPy expression to plot.
        smart_figure : SmartFigure
            Parent SmartFigure that owns this plot.
        parameters : list[sympy.Symbol] or None, optional
            Parameter symbols used in ``func``.
        x_domain : tuple (x_min, x_max), optional
            Optional domain override for evaluation.
        sampling_points : int or None, optional
            Per-plot sampling point override.
        label : str, optional
            Legend label for the plot.
        visible : bool or "legendonly", optional
            Visibility of the plot.

        Examples
        --------
        Most users create plots via SmartFigure:

        >>> import sympy as sp
        >>> x = sp.Symbol("x")
        >>> fig = SmartFigure()
        >>> fig.plot(x, sp.sin(x), id="sin")
        """
        # Parent/owner. SmartPlot asks it for viewport ranges and parameter values.
        self._smart_figure: SmartFigure = smart_figure

        # We always attach exactly one Plotly trace per SmartPlot.
        self._smart_figure.add_plot_trace(x=[], y=[], mode="lines")
        self._plot_handle = self._smart_figure._figure.data[-1]

        # During initialization we may set several properties that would each trigger
        # a render; suspend until we're fully configured.
        self._suspend_render: bool = True

        # Compile SymPy -> NumPy callable and store parameter list.
        self.set_func(var, func, parameters)

        self.x_domain = x_domain

        self.sampling_points = sampling_points
        self.label = label
        self.visible = visible

        self._suspend_render = False

        self.render()

        # raise NotImplementedError("SmartPlot is not implemented yet.")

    def set_func(
        self,
        var: Symbol,
        func: Expr,
        parameters: Optional[Sequence[Symbol]] = None,
    ) -> None:
        """
        Set the independent variable and symbolic function for this plot.

        Parameters
        ----------
        var : sympy.Symbol
            The independent variable.
        func : sympy.Expr
            The SymPy expression to plot.
        parameters : list[sympy.Symbol] or None, optional
            Parameter symbols used by ``func`` whose numeric values come from sliders.

        Notes
        -----
        Triggers recompilation via ``numpify_cached`` and a re-render.

        No autodetection of parameters is done here.
        If you want autodetection, use :meth:`SmartFigure.plot` with ``parameters=None``.

        Examples
        --------
        >>> import sympy as sp
        >>> x = sp.Symbol("x")
        >>> fig = SmartFigure()
        >>> p = fig.plot(x, sp.sin(x), id="f")
        >>> p.set_func(x, sp.cos(x))

        However, since SmartFigure supports updating via calling plot again with the same `id`, this is not necessary. It is easier to do:
        >>> import sympy as sp
        >>> x = sp.Symbol("x")
        >>> fig = SmartFigure()
        >>> fig.plot(x, sp.sin(x), id="f")
        >>> fig.plot(x, sp.cos(x), id="f")
        """

        self._var: Symbol = var
        self._parameters: Optional[Tuple[Symbol, ...]] = (
            tuple(parameters) if parameters is not None else None
        )
        self._func: Expr = func
        # numpify_cached expects an ordered list of arguments: (var, *parameters)
        self._f_numpy: Callable[..., Any] = numpify_cached(
            func,
            args=[
                self._var,
            ]
            + (list(self._parameters) or []),
        )

    @property
    def var(self) -> Symbol:
        return self._var

    @property
    def parameters(self) -> Optional[Tuple[Symbol, ...]]:
        return self._parameters

    @property
    def func(self) -> Expr:
        return self._func

    @property
    def label(self) -> str:
        return self._plot_handle.name

    @label.setter
    def label(self, value: str) -> None:
        self._plot_handle.name = value

    @property
    def x_domain(self) -> Optional[Tuple[float, float]]:
        return self._x_domain

    @x_domain.setter
    def x_domain(self, value: Optional[RangeLike]) -> None:
        """Optional evaluation-domain override.

        If set to ``None``, the plot is evaluated on the current viewport range.
        If set to a range, the plot is evaluated on the *union* of the viewport
        and this domain, so the curve remains stable as you pan.
        """
        if value is not None:
            x_min_raw, x_max_raw = value
            x_min = float(InputConvert(x_min_raw, dest_type=float))
            x_max = float(InputConvert(x_max_raw, dest_type=float))
            if x_min > x_max:
                raise ValueError(f"x_min ({x_min}) must be <= x_max ({x_max})")
            self._x_domain = (x_min, x_max)
        else:
            self._x_domain = None
        self.render()

    @property
    def sampling_points(self) -> Optional[int]:
        return self._sampling_points

    @sampling_points.setter
    def sampling_points(self, value: Optional[int]) -> None:
        """Per-plot sampling override.

        If ``None``, the plot uses the parent figure's ``sampling_points``.
        """
        self._sampling_points = int(InputConvert(value, dest_type=int)) if value is not None else None
        self.render()

    @property
    def visible(self) -> VisibleSpec:
        return self._plot_handle.visible

    @visible.setter
    def visible(self, value: VisibleSpec) -> None:
        self._plot_handle.visible = value
        if value is True:
            self.render()

    def compute_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Compute (x, y) samples for the current viewport / domain.

        Role
        ----
        This is the *numerical* heart of SmartPlot:
        - choose an x-interval,
        - build the argument list (x plus current parameter values),
        - evaluate the compiled NumPy function.
        """
        viewport_x_range = self._smart_figure.current_x_range
        if viewport_x_range is None:
            # Plotly can report None before ranges are initialized. Fall back to defaults.
            viewport_x_range = self._smart_figure.x_range

        # If an evaluation domain override exists, evaluate on the union of domains.
        if self.x_domain is None:
            x_min, x_max = float(viewport_x_range[0]), float(viewport_x_range[1])
        else:
            x_min = min(float(viewport_x_range[0]), float(self.x_domain[0]))
            x_max = max(float(viewport_x_range[1]), float(self.x_domain[1]))

        # Sampling density: per-plot override wins; otherwise use figure default.
        num = self._smart_figure.sampling_points if self.sampling_points is None else self.sampling_points
        if num is None:
            num = 500

        x_values = np.linspace(x_min, x_max, num=int(num))

        args: list[Any] = [x_values]
        if self._parameters is not None:
            for param in self._parameters:
                args.append(self._smart_figure._params[param].value)

        y_values = np.asarray(self._f_numpy(*args))
        return x_values, y_values

    def render(self) -> None:
        if self._suspend_render:
            return
        # Skip expensive computations if the trace is not visible.
        if self.visible is not True:
            return
        x_values, y_values = self.compute_data()
        self._plot_handle.x = x_values
        self._plot_handle.y = y_values

    def update(
        self,
        var: Optional[Symbol],
        func: Optional[Expr],
        parameters: Optional[Sequence[Symbol]] = None,
        label: Optional[str] = None,
        x_domain: Optional[Union[RangeLike, str]] = None,
        sampling_points: Optional[Union[int, str]] = None,
    ) -> None:
        """Update one or more aspects of this plot.

        This method is called by :meth:`SmartFigure.plot` when reusing an existing
        plot id.
        """
        if label is not None:
            self.label = label

        if x_domain is not None:
            if x_domain == "figure_default":
                self.x_domain = None
            else:
                self.x_domain = x_domain

        if func is not None or var is not None or parameters is not None:
            if var is None:
                var = self.var
            if parameters is None:
                parameters = self.parameters
            if func is None:
                func = self.func
            self.set_func(var, func, parameters=parameters)

        if sampling_points is not None:
            if sampling_points == "figure_default":
                self.sampling_points = None
            else:
                self.sampling_points = int(InputConvert(sampling_points, dest_type=int))


from .SmartSlider import SmartFloatSlider


class SmartFigure:
    """
    An interactive Plotly figure for plotting SymPy functions with slider parameters.

    What problem does this solve?
    -----------------------------
    We often want to:
    - type a symbolic function like ``sin(x)`` or ``a*x**2 + b`` (SymPy),
    - *see* it immediately (Plotly),
    - and then explore “What happens if I change a parameter?”

    ``SmartFigure`` provides a simple API that encourages experimentation.

    Key features
    ------------
    - Uses Plotly ``FigureWidget`` so it is interactive inside notebooks.
    - Uses a right-side controls panel (a ``VBox``) for parameter sliders.
    - Supports plotting multiple curves identified by an ``id``.
    - Re-renders curves on:
      - slider changes,
      - pan/zoom changes (throttled to at most once every 0.5 seconds).

    Public API
    ----------
    Methods:
    - ``__init__``
    - ``plot``  Creates a new plot
    - ``render`` Re-renders all plots
    - ``add_param`` (advanced) Creates a slider for a parameter (automatically done when ``plot`` is called)
    - ``add_plot_trace`` (advanced) Creates a plot trace - a graphical line connecting data points
    - ``update_layout`` (advanced)
    - ``new_info_output`` Creates or reuses an info Output widget
    Properties:
    - ``title`` Title of the figure
    - ``x_range``, ``y_range``, "home" ranges of the viewport
    - ``sampling_points`` number of sampling points for plots
    - ``current_x_range``, ``current_y_range``, read-only ranges of the current viewport position
    - ``plots`` a dictionary of ``SmartPlot`` objects indexed by ``id`` specified at creation with ``plot(...)``
    - ``info_output`` a dictionary of info Output widgets indexed by id

    Advanced Usage
    -------------
    The underlying Plotly's ``FigureWidget`` can be accessed via ``_figure``.
    The right-side controls panel can be accessed via ``_controls_panel``.


    A note about parameters
    -----------------------
    Parameters are SymPy symbols like ``a`` and ``b`` that get a slider each.
    You pass them to ``plot(..., parameters=[a, b])`` and the sliders appear
    automatically (via ``add_param``).


    Examples
    --------
    1) Plot a simple function:

    >>> import sympy as sp
    >>> x = sp.Symbol("x")
    >>> fig = SmartFigure()
    >>> fig.plot(x, sp.sin(x), parameters=[], id="sin")
    >>> fig.title = "y = sin(x)"
    >>> fig  # display in notebook

    2) Add a parameter slider:

    >>> import sympy as sp
    >>> x, a = sp.symbols("x a")
    >>> fig = SmartFigure(x_range=(-6, 6), y_range=(-3, 3))
    >>> fig.plot(x, a*sp.sin(x), parameters=[a], id="a_sin")
    >>> fig.title = "Explore: y = a·sin(x)"
    >>> fig

    3) Multiple curves:

    >>> import sympy as sp
    >>> x, a = sp.symbols("x a")
    >>> fig = SmartFigure()
    >>> fig.plot(x, sp.sin(x), parameters=[], id="sin")
    >>> fig.plot(x, sp.cos(x), parameters=[], id="cos")
    >>> fig.plot(x, a*sp.sin(x), parameters=[a], id="a_sin")
    >>> fig.title = "Sine, Cosine, and a·Sine"
    >>> fig

    4) Update an existing plot by reusing its id:

    >>> import sympy as sp
    >>> x = sp.Symbol("x")
    >>> fig = SmartFigure()
    >>> fig.plot(x, x**2, parameters=[], id="f")
    >>> fig.plot(x, x**3, parameters=[], id="f")  # updates curve "f" in-place

    5) Control the sampling density:

    >>> fig = SmartFigure(sampling_points=2000)  # global default for the figure

    or per plot:
    >>> fig.plot(x, sp.sin(x), parameters=[], id="sin", sampling_points=5000)
    """

    __slots__ = [
        "_figure",
        "_output",
        "plots",
        "info_output",
        "info_components",  # registry of stateful Info panel components
        "_sampling_points",
        "_x_range",
        "_y_range",
        "_current_x_range",
        "_current_y_range",
        "_debug",
        "_last_relayout",
        "panels",
        "_params",
        "_param_change_hooks", # dictionary of user-supplied hooks to call when a parameter changes
        "_hook_counter", # counter for auto-incrementing hook IDs if user doesn't supply one.
        "_info_output_counter",
        # Rate-limited logging timestamps (monotonic seconds).
        "_render_info_last_log_t",  # INFO: at most once / 1s
        "_render_debug_last_log_t",  # DEBUG: at most once / 0.5s
    ]

    # ------------
    # API
    # ------------
    _figure: go.FigureWidget  # the plotly figure widget
    _output: OneShotOutput  # the output widget to display the figure
    plots: dict[str, SmartPlot]  # curves indexed by a user-supplied id
    info_output: dict[Hashable, widgets.Output]  # info Output widgets indexed by id


    info_components: dict[Hashable, Any]  # stateful info components indexed by id
    _sampling_points: Optional[int]  # default number of sampling points
    _x_range: Tuple[float, float]  # default x-axis range
    _y_range: Tuple[float, float]  # default y-axis range
    panels: dict[str, widgets.Widget]  # named widget containers/panels

     
    _HOOK_ID_RE = re.compile(r"^hook:(\d+)$")  # regex to match automatic string hook IDs
    _INFO_OUTPUT_ID_RE = re.compile(r"^info:(\d+)$")  # regex to match automatic info output IDs

    def __init__(
        self,
        sampling_points: int = 500,
        x_range: RangeLike = (-4, 4),
        y_range: RangeLike = (-3, 3),
        debug: bool = False,
    ) -> None:
        """
        Create a SmartFigure with a Plotly FigureWidget and UI controls.

        Parameters
        ----------
        sampling_points : int, optional
            Default number of samples per plot.
        x_range : tuple (x_min, x_max), optional
            Default x-axis viewport range.
        y_range : tuple (y_min, y_max), optional
            Default y-axis viewport range.
        debug : bool, optional
            If True, print debug information to the output widget.

        Examples
        --------
        >>> import sympy as sp
        >>> x = sp.Symbol("x")
        >>> fig = SmartFigure(sampling_points=800, x_range=(-6, 6), y_range=(-4, 4))
        >>> fig.plot(x, sp.sin(x), id="sin")
        >>> fig
        """
        self._debug: bool = debug

        # --- Figure layout setup ---
        self._output: OneShotOutput = OneShotOutput()
        self._layout_init()

        # Create the FigureWidget
        # Put the figure in the left panel
        with self._output:
            # Plotly figure widget lives inside the aspect-ratio host box.
            self._figure: go.FigureWidget = go.FigureWidget()
            self.panels["plot"].children = (self._figure,)

        # Removed fixed width, added autosize=True so it fills the left panel
        self._figure.update_layout(
            autosize=True,
            template="plotly_white",
            showlegend=True,
            xaxis=dict(
                # title="x",
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor="black",
                showline=True,
                ticks="outside",
            ),
            yaxis=dict(
                # title="y",
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor="black",
                showline=True,
                ticks="outside",
            ),
        )

        # --- End of figure layout setup ---

        self.sampling_points = sampling_points

        self.x_range = x_range
        self.y_range = y_range

        self.plots = {}
        self.info_output = {}


        # Registry of stateful Info panel components (see add_info_component).
        self.info_components: dict[Hashable, Any] = {}
        # Slider registry: SymPy Symbol -> slider widget.
        self._params: dict[Symbol, SmartFloatSlider] = {}
        # --- NEW: parameter-change hooks ---
        # Maps hook_id -> callable(change, fig) run after a parameter slider changes.
        self._param_change_hooks: dict[Hashable, Callable[[dict[str, Any], SmartFigure], Any]] = {}
        # Monotone counter for autogenerated ids "hook:1", "hook:2", ...
        self._hook_counter: int = 0
        # Monotone counter for autogenerated info output ids "info:1", "info:2", ...
        self._info_output_counter: int = 0


        self._last_relayout: float = time.monotonic()

        # Rate-limited logging timestamps. Keep on the instance because SmartFigure uses __slots__.
        # Initialize to 0 so the first render can log immediately.
        self._render_info_last_log_t: float = 0.0
        self._render_debug_last_log_t: float = 0.0
        self._figure.layout.on_change(
            self._throttled_axis_range_callback, "xaxis.range", "yaxis.range"
        )

    def _layout_init(self) -> None:
        """
        Responsive layout with vertically-resizable plot that preserves aspect ratio on reflow.

        Strategy:
        - Plot container uses CSS aspect-ratio: var(--sf-ar) where --sf-ar = width/height
        - A JS drag handle updates --sf-ar during vertical resizing
        - No native resize: vertical (it writes pixel height and breaks aspect-ratio on reflow)
        """
        # Panels is the UI registry used throughout SmartFigure.
        # Everything that needs to be manipulated later lives here.
        self.panels = {}

        # --- Invisible output that runs CSS/JS bootstrap ---
        self.panels["js_bootstrap"] = widgets.Output(
            layout=widgets.Layout(
                width="1px",
                height="1px",
                overflow="hidden",
                opacity="0.0",
                margin="0px",
                padding="0px",
            )
        )

        # --- CSS (aspect ratio + drag handle) ---
        self.panels["css"] = widgets.HTML(
            value=r"""
    <style>
    /* Host plot panel: height governed by aspect-ratio. */
    .sf-plot-aspect {
    position: relative;
    width: 100%;
    /* width/height ratio */
    aspect-ratio: var(--sf-ar, 1.3333333333);
    min-height: 260px;
    box-sizing: border-box;
    }

    /* Make widget + plotly fill the host height */
    .sf-plot-aspect > .jupyter-widgets,
    .sf-plot-aspect .jupyter-widgets,
    .sf-plot-aspect .widget-subarea,
    .sf-plot-aspect .js-plotly-plot,
    .sf-plot-aspect .plotly-graph-div {
    width: 100% !important;
    height: 100% !important;
    }

    /* Drag handle (bottom grip) */
    .sf-aspect-handle {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 14px;
    cursor: ns-resize;
    user-select: none;
    touch-action: none;
    /* Let plot interactions through except right on the grip */
    background: transparent;
    z-index: 10;
    }
    .sf-aspect-handle::after {
    content: "";
    display: block;
    width: 56px;
    height: 4px;
    margin: 5px auto 0 auto;
    border-radius: 999px;
    background: rgba(0,0,0,0.25);
    }

    /* Slightly emphasize grip on hover */
    .sf-aspect-handle:hover::after {
    background: rgba(0,0,0,0.40);
    }
    </style>
    """
        )

        # --- Title (LaTeX) ---
        self.panels["title"] = widgets.HTMLMath(
            value=r"",
            layout=widgets.Layout(margin="0px"),
        )

        self.panels["full_width"] = widgets.Checkbox(
            value=False,
            description="Full width plot",
            indent=False,
            layout=widgets.Layout(width="160px", margin="0px"),
        )

        self.panels["titlebar"] = widgets.HBox(
            [self.panels["title"], self.panels["full_width"]],
            layout=widgets.Layout(
                width="100%",
                align_items="center",
                justify_content="space-between",
                margin="0px 0px 6px 0px",
                padding="0px",
            ),
        )

        # --- Plot panel (aspect ratio host) ---
        self.panels["plot"] = widgets.Box(
            children=(),
            layout=widgets.Layout(
                width="100%",
                min_width="320px",
                margin="0px",
                padding="0px",
                flex="1 1 560px",
                # IMPORTANT: do NOT set a fixed height/min_height here; CSS aspect-ratio controls it.
            ),
        )
        self.panels["plot"].add_class("sf-plot-aspect")
        # Optional: set initial ratio to 4/3
        # (you can change this to 16/9 etc)
        self.panels["plot"].layout._css = ""  # harmless no-op for some widget managers

         # --- Controls / sidebar panel (parameters + info) ---
        self.panels["params_header"] = widgets.HTML(
            value="<div style='margin:0; padding:0;'><b>Parameters</b></div>"
        )

        # Container that will hold the sliders
        self.panels["params"] = widgets.VBox(
            children=(),
            layout=widgets.Layout(width="100%", margin="0px", padding="0px"),
        )

        self.panels["info_header"] = widgets.HTML(
            value="<div style='margin:10px 0 0 0; padding:0;'><b>Info</b></div>"
        )

        # IMPORTANT: this is a *container* for Output widgets (so you can't "print into it" directly)
        self.panels["info"] = widgets.VBox(
            children=(),
            layout=widgets.Layout(width="100%", margin="0px", padding="0px"),
        )

        # Entire sidebar hidden unless params or info outputs exist
        self.panels["controls"] = widgets.VBox(
            [
                self.panels["params_header"],
                self.panels["params"],
                self.panels["info_header"],
                self.panels["info"],
            ],
            layout=widgets.Layout(
                margin="0px",
                padding="0px 0px 0px 10px",
                flex="0 1 380px",
                min_width="300px",
                max_width="400px",
                height="auto",
                display="none",  # <-- key: start hidden
            ),
        )


        # --- Content area (flex + wrap) ---
        self.panels["content"] = widgets.Box(
            [self.panels["plot"], self.panels["controls"]],
            layout=widgets.Layout(
                display="flex",
                flex_flow="row wrap",
                align_items="flex-start",
                align_content="flex-start",
                justify_content="flex-start",
                width="100%",
                margin="0px",
                padding="0px",
                gap="8px",
                height="auto",
            ),
        )

        self.panels["main_layout"] = widgets.VBox(
            [
                self.panels["css"],
                self.panels["js_bootstrap"],
                self.panels["titlebar"],
                self.panels["content"],
            ],
            layout=widgets.Layout(width="100%", margin="0px", padding="0px"),
        )

        # --- JS: Plotly ResizeObserver + aspect-ratio drag handle ---
        with self.panels["js_bootstrap"]:
            display(
                Javascript(
                    r"""
    (function () {
    if (window.__smartfigure_plotly_aspect_resizer_installed) return;
    window.__smartfigure_plotly_aspect_resizer_installed = true;

    function safeResizePlotly(gd) {
        try {
        if (window.Plotly && Plotly.Plots) Plotly.Plots.resize(gd);
        } catch (e) {}
    }

    function ensureHandle(host) {
        if (host.__sf_handle_installed) return;
        host.__sf_handle_installed = true;

        // Default aspect ratio if none set
        const cur = host.style.getPropertyValue('--sf-ar');
        if (!cur) host.style.setProperty('--sf-ar', '1.3333333333'); // 4/3 default

        const handle = document.createElement('div');
        handle.className = 'sf-aspect-handle';
        host.appendChild(handle);

        let dragging = false;
        let startY = 0;
        let startH = 0;

        const MIN_H = 180;
        const MAX_H = 2200;

        function onMove(ev) {
        if (!dragging) return;

        const dy = ev.clientY - startY;
        let newH = startH + dy;
        newH = Math.max(MIN_H, Math.min(MAX_H, newH));

        const rect = host.getBoundingClientRect();
        const w = rect.width || 1;
        const newAR = w / newH; // width/height

        host.style.setProperty('--sf-ar', String(newAR));

        // Resize the plotly graph inside this host immediately
        const gd = host.querySelector('.js-plotly-plot');
        if (gd) safeResizePlotly(gd);
        }

        function onUp(ev) {
        if (!dragging) return;
        dragging = false;
        try { handle.releasePointerCapture(ev.pointerId); } catch (e) {}
        window.removeEventListener('pointermove', onMove, true);
        window.removeEventListener('pointerup', onUp, true);
        window.removeEventListener('pointercancel', onUp, true);
        }

        handle.addEventListener('pointerdown', (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        dragging = true;
        startY = ev.clientY;
        startH = host.getBoundingClientRect().height || 1;
        try { handle.setPointerCapture(ev.pointerId); } catch (e) {}

        window.addEventListener('pointermove', onMove, true);
        window.addEventListener('pointerup', onUp, true);
        window.addEventListener('pointercancel', onUp, true);
        }, { passive: false });
    }

    function attachPlotlyResizeObservers() {
        if (!(window.Plotly && Plotly.Plots && window.ResizeObserver)) return false;

        function attachToGraph(gd) {
        if (gd.__smartfigure_ro) return;

        const ro = new ResizeObserver(() => safeResizePlotly(gd));
        ro.observe(gd);
        gd.__smartfigure_ro = ro;

        requestAnimationFrame(() => safeResizePlotly(gd));
        setTimeout(() => safeResizePlotly(gd), 50);
        setTimeout(() => safeResizePlotly(gd), 250);
        }

        document.querySelectorAll('.js-plotly-plot').forEach(attachToGraph);
        return true;
    }

    function attachAspectHandles() {
        document.querySelectorAll('.sf-plot-aspect').forEach(ensureHandle);
    }

    function attachAll() {
        attachAspectHandles();
        attachPlotlyResizeObservers();
    }

    // Initial + mutation observer
    attachAll();

    const mo = new MutationObserver(() => attachAll());
    mo.observe(document.body, { childList: true, subtree: true });

    // Retry until Plotly exists (JupyterLab timing)
    let n = 0;
    const t = setInterval(() => {
        n += 1;
        attachAll();
        if ((window.Plotly && Plotly.Plots) || n > 50) clearInterval(t);
    }, 100);
    })();
    """
                )
            )

        def _apply_full_width(on: bool) -> None:
            if on:
                self.panels["content"].layout.flex_flow = "column"
                self.panels["content"].layout.gap = "8px"

                self.panels["plot"].layout.flex = "0 0 auto"
                self.panels["controls"].layout.flex = "0 0 auto"

                self.panels["controls"].layout.max_width = ""
                self.panels["controls"].layout.padding = "0px"
                self.panels["controls"].layout.width = "100%"
            else:
                self.panels["content"].layout.flex_flow = "row wrap"
                self.panels["content"].layout.gap = "8px"

                self.panels["plot"].layout.flex = "1 1 560px"
                self.panels["controls"].layout.flex = "0 1 380px"

                self.panels["controls"].layout.max_width = "400px"
                self.panels["controls"].layout.padding = "0px 0px 0px 10px"
                self.panels["controls"].layout.width = "auto"

        def _on_full_width(change: dict[str, Any]) -> None:
            if change["name"] == "value":
                _apply_full_width(change["new"])

        self.panels["full_width"].observe(_on_full_width, names="value")
        _apply_full_width(self.panels["full_width"].value)

        with self._output:
            display(self.panels["main_layout"])

    def _throttled_axis_range_callback(self, attr: str, old: Any, new: Any) -> None:
        if time.monotonic() - self._last_relayout < 0.5:
            return
        self._last_relayout = time.monotonic()

        if self._debug:
            with self._output:
                # print(f"Relayout event detected: from {old} to {new}")
                pass
        self.render(reason="relayout")

    def _ensure_controls_visible(self) -> None:
        """
        Sync sidebar + section visibility.

        Role
        ----
        The sidebar is entirely hidden unless there's something meaningful to show.
        Concretely, we show/hide based on whether we have:
        - any parameter widgets in self.panels["params"]
        - any info output widgets in self.panels["info"]
        """
        has_params = len(self.panels["params"].children) > 0
        has_info = len(self.panels["info"].children) > 0

        # Hide empty sections
        self.panels["params_header"].layout.display = "block" if has_params else "none"
        self.panels["params"].layout.display = "flex" if has_params else "none"

        self.panels["info_header"].layout.display = "block" if has_info else "none"
        self.panels["info"].layout.display = "flex" if has_info else "none"

        # Hide the whole sidebar if there's nothing to show
        self.panels["controls"].layout.display = (
            "flex" if (has_params or has_info) else "none"
        )

    # Backwards-compatible alias (older drafts used this name).
    def _set_controls_visible(self) -> None:
        self._ensure_controls_visible()

    def add_param(
        self,
        parameter_id: Symbol,
        value: NumberLike = 0.0,
        min: NumberLike = -1,
        max: NumberLike = 1,
        step: NumberLike = 0.01,
    ) -> SmartFloatSlider:
        """
        Add a SmartFloatSlider parameter to the controls panel.

        Parameters
        ----------
        parameter_id : sympy.Symbol
            The parameter symbol (e.g. ``a``).
        value : float, optional
            Initial slider value.
        min : float, optional
            Minimum slider value.
        max : float, optional
            Maximum slider value.
        step : float, optional
            Slider step size.

        Examples
        --------
        >>> import sympy as sp
        >>> a = sp.Symbol("a")
        >>> fig = SmartFigure()
        >>> fig.add_param(a, value=2.0, min=-5, max=5, step=0.5)
        """

        description = f"${sp.latex(parameter_id)}$"  # Can be enriched later
        if parameter_id in self._params:
            # Reuse existing slider. This keeps callbacks stable and avoids UI duplication.
            return self._params[parameter_id]

        slider = SmartFloatSlider(
            description=description,
            value=float(value),
            min=float(min),
            max=float(max),
            step=float(step),
        )
        
        # Add slider to the Parameters section.
        self.panels["params"].children += (slider,)
        self._ensure_controls_visible()
        self._params[parameter_id] = slider

        
        # Centralized callback: rerender once, then run user hooks.
        slider.observe(self._on_param_change, names="value")

        return slider
    
    def _on_param_change(self, change: dict[str, Any]) -> None:
        """
        Internal ipywidgets observer for *any* parameter slider change.

        This centralizes the behavior so:
        - we render once per change event, and
        - we can reliably run user hooks after rendering.

        Parameters
        ----------
        change : dict
            The standard traitlets/ipywidgets change dictionary. Common keys include:
            - "owner": the widget whose trait changed (here: a SmartFloatSlider)
            - "name":  the trait name (here: "value")
            - "old":   previous value
            - "new":   new value
        """
        # First update the figure so the user sees the new curve immediately.
        # Rendering is a hot path during slider drags; render() has rate-limited logging.
        self.render(reason="param_change", trigger=change)

        # Then notify any user hooks (kept separate so hook failures don't kill interactivity).
        self._run_param_change_hooks(change)

    def _run_param_change_hooks(self, change: dict[str, Any]) -> None:
        """
        Run all registered parameter-change hooks.

        Notes
        -----
        - Hooks are called in insertion/replacement order as stored in the dict.
        - Hook exceptions are caught and reported as warnings so the notebook
          remains interactive.
        """
        # Iterate over a snapshot in case hooks modify the hook registry.
        for hook_id, callback in list(self._param_change_hooks.items()):
            try:
                callback(change,self)
            except Exception as exc:
                warnings.warn(
                    f"SmartFigure param-change hook {hook_id!r} raised {type(exc).__name__}: {exc}"
                )
    def add_param_change_hook(
        self,
        callback: Callable[[dict[str, Any], SmartFigure], Any],
        hook_id: Optional[Hashable] = None,
    ) -> Hashable:
        """
        Register (or replace) a callback to run when *any* parameter value changes.

        Behavior    
        --------
        - If `hook_id` is provided and already exists, it is **replaced**.
        - If `hook_id` is provided and does not exist, it is **created**.
        - If `hook_id` is None, an id is auto-assigned as "hook:1", "hook:2", ...

        Additional rule (collision safety)
        ---------------------------------
        If the user provides a string hook id of the form "hook:N", then the internal
        counter is bumped so that later autogenerated ids won't collide. Concretely,
        we ensure `self._hook_counter >= N`.

        Parameters
        ----------
        callback:
            Callable invoked as `callback(change, fig)` after the figure re-renders.
            The `change` dict is the standard traitlets/ipywidgets change payload.
        hook_id:
            Any **hashable** key usable in a dict (e.g. str, int, tuple, Enum, etc.).
            If None, a fresh id is autogenerated.

        Returns
        -------
        Hashable
            The hook id used to store the callback (provided or autogenerated).

        Examples
        --------
        Autogenerated ids:
        >>> hid1 = fig.add_param_change_hook(lambda ch, fig: print("changed"))
        >>> hid1
        'hook:1'

        User-specified ids (any hashable key):
        >>> fig.add_param_change_hook(lambda ch, fig: None, hook_id=("analysis", 1))
        ('analysis', 1)

        Collision-safe bump:
        >>> fig.add_param_change_hook(lambda ch, fig: None, hook_id="hook:10")
        'hook:10'
        >>> fig.add_param_change_hook(lambda ch, fig: None)
        'hook:11'

        Use with a simple logger:
        >>> def log_change(change, fig):
        ...     print(change["name"], change["old"], "->", change["new"])
        >>> fig.add_param_change_hook(log_change, hook_id="logger")
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")

        if hook_id is None:
            # Generate monotonically increasing ids: "hook:1", "hook:2", ...
            self._hook_counter += 1
            hook_id = f"hook:{self._hook_counter}"
        else:
            # Dict keys must be hashable; check early for a clearer error.
            try:
                hash(hook_id)
            except Exception as exc:
                raise TypeError(
                    f"hook_id must be hashable (usable as a dict key), got {type(hook_id)}"
                ) from exc

            # If the user picked an id in our "hook:N" namespace, bump the counter
            # so future auto-ids don't accidentally collide.
            self._maybe_bump_hook_counter_from_id(hook_id)

        # Insert or replace (dict assignment naturally replaces if key exists).
        self._param_change_hooks[hook_id] = callback
        
        callback({}, self)
        
        return hook_id
       
    def _maybe_bump_hook_counter_from_id(self, hook_id: Hashable) -> None:
        """
        If `hook_id` matches the autogenerated scheme "hook:N", bump the internal
        counter so future autogenerated ids don't collide.

        Notes
        -----
        We bump using `max(current, N)` rather than setting it unconditionally.
        This prevents moving the counter backwards (which could reintroduce
        collisions if we already generated higher ids earlier).
        """
        if isinstance(hook_id, str):
            m = self._HOOK_ID_RE.match(hook_id)
            if m is None:
                return

            n = int(m.group(1))
            if n < 1:
                raise ValueError(
                    f"Invalid hook id {hook_id!r}: N must be >= 1 for ids of the form 'hook:N'."
                )

            # Ensure future auto ids start at least after this N.
            # Example: user inserts "hook:7" early, then auto ids begin at "hook:8".
            self._hook_counter = max(self._hook_counter, n)

    def get_info_output(
        self,
        id: Optional[Hashable] = None,
        **layout_kwargs: Any,
    ) -> widgets.Output:
        """
        Create an Output widget inside the Info area and return it.
        Usage:
            out = fig.get_info_output()
            with out:
                print("hello")
        Or reuse/create by id:
            out = fig.get_info_output("info:1")
            out = fig.info_output["info:1"]

        Parameters
        ----------
        id : hashable, optional
            If provided, this id is used as the key in ``fig.info_output``.
            If not provided, a new id is auto-assigned as "info:1", "info:2", ...
            Reusing an existing id returns the existing Output widget.
        **layout_kwargs : dict
            Optional layout parameters for the Output widget.

        Returns
        -------
        widgets.Output
            The created or reused Output widget. The widget has a readable ``id``
            attribute matching the key used in ``fig.info_output``.

        Examples
        --------
        >>> fig = SmartFigure()
        >>> out = fig.get_info_output()
        >>> with out:
        ...     print("f(x) = sin(x)")
        """
        if id is None:
            # Generate monotonically increasing ids: "info:1", "info:2", ...
            self._info_output_counter += 1
            id = f"info:{self._info_output_counter}"
        else:
            # Dict keys must be hashable; check early for a clearer error.
            try:
                hash(id)
            except Exception as exc:
                raise TypeError(
                    f"info output id must be hashable (usable as a dict key), got {type(id)}"
                ) from exc

            # If the user picked an id in our "info:N" namespace, bump the counter
            # so future auto-ids don't accidentally collide.
            if isinstance(id, str):
                m = self._INFO_OUTPUT_ID_RE.match(id)
                if m is not None:
                    n = int(m.group(1))
                    if n < 1:
                        raise ValueError(
                            f"Invalid info output id {id!r}: N must be >= 1 for ids of the form 'info:N'."
                        )
                    self._info_output_counter = max(self._info_output_counter, n)

        if id in self.info_output:
            out = self.info_output[id]
            if layout_kwargs:
                out.layout = widgets.Layout(**layout_kwargs)
            return out

        # Info panel intentionally holds Output widgets so the user can "print into" them.
        out = widgets.Output(layout=widgets.Layout(**layout_kwargs))
        setattr(out, "id", id)
        self.info_output[id] = out
        self.panels["info"].children += (out,)
        self._ensure_controls_visible()
        return out

    # Backwards-compatible alias (older docs used this name).
    def new_info_output(
        self,
        id: Optional[Hashable] = None,
        **layout_kwargs: Any,
    ) -> widgets.Output:
        """Alias for :meth:`get_info_output`.

        The public API uses :meth:`get_info_output`. This alias exists only so that
        older notebooks (and older docs) keep working.
        """
        return self.get_info_output(id=id, **layout_kwargs)

    # ---------------------------------------------------------------------
    # Info components
    # ---------------------------------------------------------------------

    def add_info_component(
        self,
        id: Hashable,
        component: Callable[[widgets.Output, "SmartFigure"], Any],
        *,
        hook_id: Optional[Hashable] = None,
        **out_layout: Any,
    ) -> Any:
        """Register (or replace) a stateful *info component*.

        An *info component* is a small object that owns both:

        1) its UI living inside an Info :class:`ipywidgets.Output` widget, and
        2) its update logic, run automatically after any parameter slider changes.

        This method is deliberately explicit (no decorators) and rerun-safe:
        calling it again with the same ``id`` will reuse the same Output widget and
        replace the stored component instance and its hook.

        Parameters
        ----------
        id:
            Stable identifier for the component and its Info Output widget.
            Reusing ``id`` across notebook reruns is the intended workflow.
        component:
            Either a class or a factory callable invoked as ``component(out, fig)``.
            The returned object **must** provide an ``update(change, fig, out)`` method.
        hook_id:
            Optional explicit hook identifier. If omitted, a deterministic default
            is used: ``("info_component", id)``.
        **out_layout:
            Optional layout kwargs forwarded to :meth:`get_info_output`.

        Returns
        -------
        object
            The created component instance.

        Notes
        -----
        - Registration does **not** call ``update``. This keeps behavior explicit and
          avoids surprising side effects at registration time.
        - The registered hook uses the existing parameter-change hook pipeline:
          it is called with the standard hook signature ``(change, fig)`` and
          forwards to the component's richer signature ``update(change, fig, out)``.

        Examples
        --------
        >>> class CounterCard:
        ...     def __init__(self, out, fig):
        ...         import ipywidgets as widgets
        ...         from IPython.display import clear_output, display
        ...         self.n = 0
        ...         self._label = widgets.HTML(value="<code>0</code>")
        ...         with out:
        ...             clear_output()
        ...             display(self._label)
        ...     def update(self, change, fig, out):
        ...         self.n += 1
        ...         self._label.value = f"<code>{self.n}</code>"
        ...
        >>> fig = SmartFigure()
        >>> card = fig.add_info_component("info:counter", CounterCard)
        """
        # Ensure we have (and reuse) the Info Output widget.
        out = self.get_info_output(id, **out_layout)

        # Create the component instance (classes are callables, so one path suffices).
        inst = component(out, self)

        update = getattr(inst, "update", None)
        if update is None or not callable(update):
            raise TypeError(
                "Info component must define an 'update(change, fig, out)' method. "
                f"Got {type(inst).__name__} without a callable .update."
            )

        # Store/replace instance by id (rerun-safe).
        self.info_components[id] = inst

        # Deterministic default hook id so reruns replace instead of duplicating.
        if hook_id is None:
            hook_id = ("info_component", id)

        # Hook signature stays general: (change, fig). Forward to richer update signature.
        def _cb(change: dict[str, Any], fig: "SmartFigure") -> Any:
            return inst.update(change, fig, out)

        self.add_param_change_hook(_cb, hook_id=hook_id)

        return inst

    def get_info_component(self, id: Hashable) -> Any:
        """Return a previously registered info component instance.

        Parameters
        ----------
        id:
            The id used in :meth:`add_info_component`.

        Returns
        -------
        object
            The registered component instance.

        Raises
        ------
        KeyError
            If no component is registered under ``id``.
        """
        return self.info_components[id]

    def remove_info_component(self, id: Hashable, *, hook_id: Optional[Hashable] = None) -> None:
        """Remove an info component instance and its associated param-change hook.

        This is a minimal cleanup helper.

        Notes
        -----
        - The Info Output widget is **not** removed from the UI.
          You can clear it manually via ``with out: clear_output()``.
        - If you registered with a custom ``hook_id``, pass the same ``hook_id`` here.

        Parameters
        ----------
        id:
            Component id used in :meth:`add_info_component`.
        hook_id:
            Hook id to remove. If omitted, uses the default ``("info_component", id)``.
        """
        self.info_components.pop(id, None)
        if hook_id is None:
            hook_id = ("info_component", id)
        self._param_change_hooks.pop(hook_id, None)

    @property
    def title(self) -> str:
        """Title text shown above the figure.

        Notes
        -----
        We use an ``HTMLMath`` title panel rather than Plotly's native title so
        LaTeX rendering is reliable in Jupyter.
        """
        return str(self.panels["title"].value or "")

    @title.setter
    def title(self, value: str) -> None:
        self.panels["title"].value = value

    @property
    def x_range(self) -> Tuple[float, float]:
        return self._x_range

    @x_range.setter
    def x_range(self, value: RangeLike) -> None:
        x_min_raw, x_max_raw = value
        x_min = float(InputConvert(x_min_raw, dest_type=float))
        x_max = float(InputConvert(x_max_raw, dest_type=float))
        if x_min > x_max:
            raise ValueError(f"x_min ({x_min}) must be <= x_max ({x_max})")
        self._figure.update_xaxes(range=(x_min, x_max))
        self._x_range = (x_min, x_max)

    @property
    def y_range(self) -> Tuple[float, float]:
        return self._y_range

    @y_range.setter
    def y_range(self, value: RangeLike) -> None:
        y_min_raw, y_max_raw = value
        y_min = float(InputConvert(y_min_raw, dest_type=float))
        y_max = float(InputConvert(y_max_raw, dest_type=float))
        if y_min > y_max:
            raise ValueError(f"y_min ({y_min}) must be <= y_max ({y_max})")
        self._figure.update_yaxes(range=(y_min, y_max))
        self._y_range = (y_min, y_max)

    @property
    def current_x_range(self) -> Optional[Tuple[float, float]]:
        return self._figure.layout.xaxis.range

    @property
    def current_y_range(self) -> Optional[Tuple[float, float]]:
        return self._figure.layout.yaxis.range

    @property
    def sampling_points(self) -> Optional[int]:
        return self._sampling_points

    @sampling_points.setter
    def sampling_points(self, value: Union[int, str, None]) -> None:
        # Accept the historical sentinel "figure_default".
        if value == "figure_default":
            self._sampling_points = None
        elif value is None:
            self._sampling_points = None
        else:
            self._sampling_points = int(InputConvert(value, dest_type=int))

    def add_scatter(self, **scatter_kwargs: Any) -> None:
        """
        DEPRECATED: use add_plot_trace instead.
        Add a scatter trace to the figure.

        Parameters
        ----------
        scatter_kwargs : dict
            Keyword arguments for the scatter trace.

        Examples
        --------
        >>> fig = SmartFigure()
        >>> fig.add_scatter(x=[0, 1], y=[0, 1], mode="markers")
        """
        warnings.warn("add_scatter is deprecated, use add_plot_trace instead.", DeprecationWarning)
        self.add_plot_trace(**scatter_kwargs)

    def add_plot_trace(self, **plot_kwargs: Any) -> None:
        """
        Add a plot trace to the figure.

        Parameters
        ----------
        plot_kwargs : dict
            Keyword arguments for the plot trace.

        Examples
        --------
        >>> fig = SmartFigure()
        >>> fig.add_plot_trace(x=[0, 1], y=[1, 0], mode="lines", name="diag")
        """
        self._figure.add_scatter(**plot_kwargs)

    def _ipython_display_(self, **kwargs: Any) -> OneShotOutput:
        """
        IPython display hook to show the figure in Jupyter notebooks.
        """
        display(self._output)
        return self._output

    def update_layout(self, **layout_kwargs: Any) -> None:
        """
        Update the layout of the figure.

        Parameters
        ----------
        layout_kwargs : dict
            Keyword arguments for updating the figure layout.

        Examples
        --------
        >>> fig = SmartFigure()
        >>> fig.update_layout(title="My Plot", height=400, width=600)
        """
        self._figure.update_layout(**layout_kwargs)

    def plot(
        self,
        var: Symbol,
        func: Expr,
        parameters: Optional[Sequence[Symbol]] = None,
        id: Optional[str] = None,
        x_domain: Optional[RangeLike] = None,
        sampling_points: Optional[Union[int, str]] = None,
    ) -> SmartPlot:
        """
        Plot a SymPy expression on the figure (and keep it “live”).

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable (e.g. ``x``).
        func : sympy.Expr
            SymPy expression (e.g. ``sin(x)``, ``a*x**2 + b``).
        parameters : list[sympy.Symbol] or None, optional
            Parameter symbols whose numeric values come from sliders.
            If ``None``, parameters are autodetected from ``func.free_symbols`` (excluding ``var``).
            **Important:** In this version, pass ``[]`` when there are no parameters and you want to
            explicitly disable autodetection.
        id : str, optional
            Unique identifier for the plot.
            - If ``id`` is new: creates a new plot.
            - If ``id`` already exists: updates the existing plot in-place.
            If not provided, the method tries to choose ``"f_0"``, ``"f_1"``, ...
        x_domain : tuple (x_min, x_max), optional
            Optional domain override for the plot. See ``SmartPlot.x_domain``.
        sampling_points : int or "figure_default", optional
            Number of sampling points for this plot.
            - If not provided: use existing plot setting or figure default.
            - If "figure_default": reset plot override to use figure default.

        Returns
        -------
        SmartPlot
            The created or updated plot object.

        Notes for students
        ------------------
        Think of this as:
        - “add a curve to the figure”
        - and “keep it updated when sliders or viewport changes”.
        If you omit ``parameters``, SmartFigure will infer them from the expression.
        This is a convenience for quick exploration, but pass ``[]`` if you want no sliders.

        Examples
        --------
        Basic plot:

        >>> import sympy as sp
        >>> x = sp.Symbol("x")
        >>> fig = SmartFigure()
        >>> fig.plot(x, sp.sin(x), parameters=[], id="sin")
        >>> fig

        Add a parameter slider:

        >>> import sympy as sp
        >>> x, a = sp.symbols("x a")
        >>> fig = SmartFigure()
        >>> fig.plot(x, a*sp.sin(x), parameters=[a], id="a_sin")
        >>> fig

        Update an existing plot:

        >>> import sympy as sp
        >>> x = sp.Symbol("x")
        >>> fig = SmartFigure()
        >>> fig.plot(x, x**2, parameters=[], id="f")
        >>> fig.plot(x, x**3, parameters=[], id="f")  # same id => update curve

        Autodetect parameters from the expression:

        >>> import sympy as sp
        >>> x, a, b = sp.symbols("x a b")
        >>> fig = SmartFigure()
        >>> fig.plot(x, a*x**2 + b, id="poly")  # parameters inferred as [a, b]

        Choose a wider computation domain than the visible window:

        >>> fig.plot(x, sp.sin(x), parameters=[], id="sin", x_domain=(-20, 20))

        Increase resolution:

        >>> fig.plot(x, sp.sin(x), parameters=[], id="sin", sampling_points=5000)
        """
        id_was_none = id is None #Used mainly for debugging
        if id is None:
            # Choose the first free id among f_0, f_1, ...
            for n in range(101):  # 0 to 100 inclusive
                candidate = f"f_{n}"
                if candidate not in self.plots:
                    id = candidate
                    break
            if id is None:
                raise ValueError("No available f_n identifiers (max 100 reached)")

        is_update = id in self.plots 

        if self._debug:
            with self._output:
                print(f"Plotting {sp.latex(func)}, var={sp.latex(var)}")
            if parameters is not None:
                with self._output:
                    print(f"Parameters: {parameters}")

        autodetected = parameters is None #Used mainly for debugging
        if parameters is None:
            # Autodetect parameters (all free symbols except the plot variable).
            # Use a stable order so logs and slider ordering are deterministic.
            syms = func.free_symbols
            parameters = sorted([s for s in syms if s != var], key=lambda s: s.sort_key())
            if self._debug:
                with self._output:
                    print(f"Detected parameters: {parameters}")
        else:
            # Normalize to a plain list (callers may pass tuples/generators).
            parameters = list(parameters)

        # Track which sliders were newly created during this call.
        _before_syms = set(self._params.keys()) # Used mainly for debugging
        for p in parameters:
            self.add_param(p)
        _after_syms = set(self._params.keys()) # Used mainly for debugging 
        _new_syms = sorted(list(_after_syms - _before_syms), key=lambda s: s.sort_key()) # Used mainly for debugging

        # INFO: summary of plot creation/update and parameter inference.
        # This is not a hot path (plot() is called by the user), so a single log is fine.
        if logger.isEnabledFor(logging.INFO):
            expr_s = str(func)
            if len(expr_s) > 140:
                expr_s = expr_s[:137] + "..."
            params_s = [str(s) for s in parameters]
            new_s = [str(s) for s in _new_syms]
            logger.info(
                "plot(%s id=%s auto_id=%s var=%s expr=%s params_mode=%s params=%s new_sliders=%s x_domain=%s sampling_points=%s)",
                "update" if is_update else "create",
                id,
                id_was_none,
                str(var),
                expr_s,
                "autodetect" if autodetected else "explicit",
                params_s,
                new_s,
                x_domain,
                sampling_points,
            )

        if is_update:
            plot = self.plots[id]
            plot.update(
                var,
                func,
                parameters,
                label=None,
                x_domain=x_domain,
                sampling_points=sampling_points,
            )
        else:
            plot = SmartPlot(
                var=var,
                func=func,
                smart_figure=self,
                parameters=parameters,
                x_domain=None,
                label=str(id),
                sampling_points=sampling_points,
            )
            self.plots[id] = plot

        return plot

    def render(self, *, reason: str = "manual", trigger: Any = None) -> None:
        """Render all plots on the figure.

        This is a *hot* method: it is called during slider drags and (throttled)
        pan/zoom relayout events.

        Logging policy
        --------------
        - INFO logs are rate-limited to at most once every 1 second.
        - DEBUG logs for ranges are rate-limited to at most once every 0.5 seconds.
        - Messages are emitted **before** the expensive render loop.

        Parameters
        ----------
        reason:
            Short string explaining why a render is being requested.
            Examples: "param_change", "relayout", "manual".
        trigger:
            Optional event payload used only for logging.
            For slider changes this is typically an ipywidgets change dict.

        Examples
        --------
        >>> fig = SmartFigure()
        >>> fig.render()  # force a redraw after external changes
        """
        now = time.monotonic()

        # --- INFO (once / 1s) ---
        if logger.isEnabledFor(logging.INFO) and (now - self._render_info_last_log_t) >= 1.0:
            self._render_info_last_log_t = now

            sym_name: Optional[str] = None
            old_val: Any = None
            new_val: Any = None

            # Extract a small, informative summary for slider-triggered renders.
            if isinstance(trigger, dict) and trigger.get("name") == "value":
                old_val = trigger.get("old")
                new_val = trigger.get("new")
                owner = trigger.get("owner", None)
                if owner is not None:
                    # Do NOT attach attributes to the slider (it may use __slots__).
                    # This scan is done only once per second (rate-limited).
                    for s, sl in self._params.items():
                        if sl is owner:
                            sym_name = str(s)
                            break

                logger.info(
                    "render(reason=%s sym=%s old=%s new=%s) plots=%d",
                    reason,
                    sym_name,
                    old_val,
                    new_val,
                    len(self.plots),
                )
            else:
                logger.info("render(reason=%s) plots=%d", reason, len(self.plots))

        # --- DEBUG (once / 0.5s): ranges ---
        if logger.isEnabledFor(logging.DEBUG) and (now - self._render_debug_last_log_t) >= 0.5:
            self._render_debug_last_log_t = now

            cx = self.current_x_range
            cy = self.current_y_range
            cx_t = tuple(cx) if cx is not None else None
            cy_t = tuple(cy) if cy is not None else None

            logger.debug(
                "ranges(reason=%s) x_range=%s y_range=%s current_x_range=%s current_y_range=%s",
                reason,
                tuple(self.x_range),
                tuple(self.y_range),
                cx_t,
                cy_t,
            )

        with self._figure.batch_update():
            for plot in self.plots.values():
                plot.render()


# === END SECTION: SmartFigure [id: SmartFigure]===
