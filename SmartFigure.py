"""
Widgets and interactive plotting helpers for math exploration in Jupyter.

This file defines two main ideas:

1) OneShotOutput
   A small safety wrapper around ``ipywidgets.Output`` that can only be displayed once.
   This prevents a common notebook confusion: accidentally displaying the *same* widget
   in multiple places and then wondering which one is “live”.

2) SmartFigure (+ SmartPlot)
   A thin, student-friendly wrapper around ``plotly.graph_objects.FigureWidget`` that:
   - plots SymPy expressions by compiling them to NumPy via ``numpify``,
   - supports interactive parameter sliders (via ``SmartFloatSlider``),
   - re-renders automatically when you pan/zoom (throttled) or move a slider.

The intended workflow is:

- define symbols with SymPy (e.g. ``x, a = sp.symbols("x a")``),
- create a ``SmartFigure``,
- add one or more plots with ``SmartFigure.plot(...)``,
- optionally add parameters (sliders) by passing ``parameters=[a, ...]``.

---------------------------------------------------------------------------
Quick start (in a Jupyter notebook)
---------------------------------------------------------------------------

>>> import sympy as sp
>>> from SmartFigure import SmartFigure  # wherever this file lives
>>>
>>> x, a = sp.symbols("x a")
>>> fig = SmartFigure(x_range=(-6, 6), y_range=(-3, 3))
>>> fig.plot(x, sp.sin(x), parameters=[], id="sin")
>>> fig.plot(x, a*sp.cos(x), parameters=[a], id="a_cos")  # adds a slider for a
>>> fig.title = "Sine and a·Cosine"
>>> fig  # display in the output cell (or use display(fig))

Notes for students
------------------
- SymPy expressions are symbolic. They are like *formulas*.
- Plotly needs numerical values (arrays of numbers).
- ``numpify`` bridges the two: it turns a SymPy expression into a NumPy-callable function.
- Sliders provide the numeric values of parameters like ``a`` in real time.
"""

# === SECTION: OneShotOutput [id: OneShotOutput]===
import sympy as sp
from typing import Any, Type, TypeVar
import time
from .numpify import numpify
from .NamedFunction import NamedFunction
import plotly.graph_objects as go
from typing import Any
from sympy import Symbol
import numpy as np
import ipywidgets as widgets
from IPython.display import display


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

    def __init__(self):
        """Initialize a new OneShotOutput widget."""
        super().__init__()
        self._displayed = False

    def _repr_mimebundle_(self, include=None, exclude=None, **kwargs):
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
from .InputConvert import InputConvert


class SmartPlot:
    """
    A single plotted curve managed by a :class:`SmartFigure`.

    Conceptually, a ``SmartPlot`` is “one function on one set of axes”.
    It owns a single Plotly trace (a line plot) and knows how to:

    - compile the SymPy expression to a fast NumPy function (via ``numpify``),
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
    - ``set_var_func``
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
        var,
        func,
        smart_figure,
        parameters=None,
        x_domain=None,
        sampling_points=None,
        label="",
        visible=True,
    ):
        self._smart_figure = smart_figure
        self._smart_figure.add_scatter(x=[], y=[], mode="lines")
        self._plot_handle = self._smart_figure._figure.data[-1]

        self._suspend_render = True

        self.set_func(var, func, parameters)  # Private method

        self.x_domain = x_domain

        self.sampling_points = sampling_points
        self.label = label
        self.visible = visible

        self._suspend_render = False

        self.render()

        # raise NotImplementedError("SmartPlot is not implemented yet.")

    def set_func(self, var, func, parameters=None):
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
        Triggers recompilation via ``numpify`` and a re-render.

        Examples
        --------
        >>> import sympy as sp
        >>> x = sp.Symbol("x")
        >>> fig = SmartFigure()
        >>> p = fig.plot(x, sp.sin(x), parameters=[], id="f")
        >>> p.set_var_func(x, sp.cos(x), parameters=[])

        However, since SmartFigure supports updating via calling plot again with the same `id`, this is not necessary. It is easier to do:
          >>> import sympy as sp
        >>> x = sp.Symbol("x")
        >>> fig = SmartFigure()
        >>> fig.plot(x, sp.sin(x), parameters=[], id="f")
        >>> fig.plot(t, sp.cos(t), parameters=[], id="f")
        """

        self._var = var
        self._parameters = parameters
        self._func = func
        self._f_numpy = numpify(
            func,
            args=[
                self._var,
            ]
            + (self._parameters or []),
        )

    @property
    def var(self):
        return self._var

    @property
    def parameters(self):
        return self._parameters

    @property
    def func(self):
        return self._func

    @property
    def label(self):
        return self._plot_handle.name

    @label.setter
    def label(self, value):
        self._plot_handle.name = value

    @property
    def x_domain(self):
        return self._x_domain

    @x_domain.setter
    def x_domain(self, value):
        if value is not None:  # Value normalization
            x_min, x_max = value
            value = (
                InputConvert(x_min, dest_type=float),
                InputConvert(x_max, dest_type=float),
            )
            if x_min > x_max:
                raise ValueError(f"x_min ({x_min}) must be less than x_max ({x_max})")

        self._x_domain = value
        self.render()

    @property
    def sampling_points(self):
        return self._sampling_points

    @sampling_points.setter
    def sampling_points(self, value):
        if value is not None:
            value = InputConvert(value, dest_type=int)
        self._sampling_points = value
        self.render()

    @property
    def visible(self):
        return self._plot_handle.visible

    @visible.setter
    def visible(self, value):
        self._plot_handle.visible = value
        if value == True:
            self.render()

    def compute_data(self):
        viewport_x_range = self._smart_figure.current_x_range
        if self.x_domain is None:
            x_min = viewport_x_range[0]
            x_max = viewport_x_range[1]
        else:
            x_min = min(viewport_x_range[0], self.x_domain[0])
            x_max = max(viewport_x_range[1], self.x_domain[1])

        if self.sampling_points is None:
            num = self._smart_figure.sampling_points
        else:
            num = self.sampling_points

        x_values = np.linspace(x_min, x_max, num=num)

        args = [x_values]
        if self._parameters is not None:
            for param in self._parameters:
                args.append(self._smart_figure._params[param].value)

        y_values = self._f_numpy(*args)
        return x_values, y_values

    def render(self):
        if self._suspend_render:
            return
        if not self.visible == True:
            return
        x_values, y_values = self.compute_data()
        self._plot_handle.x = x_values
        self._plot_handle.y = y_values

    def update(
        self,
        var,
        func,
        parameters=None,
        label=None,
        x_domain=None,
        sampling_points=None,
    ):
        if label is not None:
            self.label = label
        if x_domain is not None:
            if x_domain == "figure_default":
                self.x_domain = None
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
            self.sampling_points = sampling_points


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
    - ``add_scatter`` (advanced)
    - ``update_layout`` (advanced)
    Properties:
    - ``title`` Title of the figure
    - ``x_range``, ``y_range``, "home" ranges of the viewport
    - ``sampling_points`` number of sampling points for plots
    - ``current_x_range``, ``current_y_range``, read-only ranges of the current viewport position
    - ``plots`` a dictionary of ``SmartPlot`` objects indexed by ``id`` specified at creation with ``plot(...)``

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
        "_sampling_points",
        "_x_range",
        "_y_range",
        "_current_x_range",
        "_current_y_range",
        "_debug",
        "_last_relayout",
        "panels",
        "_params",
    ]

    # ------------
    # API
    # ------------
    _figure: go.FigureWidget  # the plotly figure widget
    _output: OneShotOutput  # the output widget to display the figure
    plots: dict  # dictionary to store plots by name

    _sampling_points: int  # default number of sampling points
    _x_range: tuple  # default x-axis range
    _y_range: tuple  # default y-axis range
    _panels: dict  # dictionary to store panels by name

    def __init__(
        self,
        sampling_points: int = 500,
        x_range: tuple = (-4, 4),
        y_range: tuple = (-3, 3),
        debug: bool = False,
    ):
        self._debug = debug

        # --- Figure layout setup ---
        self._output = OneShotOutput()
        self._layout_init()

        # Create the FigureWidget
        # Put the figure in the left panel
        with self._output:
            self._figure = go.FigureWidget()
            self.panels["plot"].children = (self._figure,)

        # Removed fixed width, added autosize=True so it fills the left panel
        self._figure.update_layout(
            height=600,
            autosize=True,
            template="plotly_white",
            showlegend=True,
            xaxis=dict(
                #title="x",
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor="black",
                showline=True,
                ticks="outside",
            ),
            yaxis=dict(
                #title="y",
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor="black",
                showline=True,
                ticks="outside",
            ),
            title=dict(x=0.5, y=0.95, xanchor="center"),
        )

        # --- End of figure layout setup ---

        if sampling_points == "figure_default":
            self.sampling_points = None
        else:
            self.sampling_points = sampling_points

        self.x_range = x_range
        self.y_range = y_range

        self.plots = {}

        self._params = {}

        self._last_relayout = time.monotonic()
        self._figure.layout.on_change(
            self._throttled_axis_range_callback, "xaxis.range", "yaxis.range"
        )

    def _layout_init(self):
        """
        Initialize the layout of the figure.
        """
        self.panels = {}
        # Right Panel: Sidebar with a title
        self.panels["controls"] = widgets.VBox(
            [widgets.HTML(value="<b>Parameters</b>")],
            layout=widgets.Layout(width="400px", padding="0px 0px 0px 10px"),
        )

        # Left Panel: Plot area
        self.panels["plot"] = widgets.VBox(layout=widgets.Layout(flex="1"))

        # Main Container: Combines Left and Right
        self.panels["main_layout"] = widgets.HBox(
            [self.panels["plot"], self.panels["controls"]],  
            layout=widgets.Layout(width="100%", align_items="flex-start"),
        )

        # Display the layout once
        with self._output:
            display(self.panels["main_layout"])

    def _throttled_axis_range_callback(self, attr, old, new):
        if time.monotonic() - self._last_relayout < 0.5:
            return
        self._last_relayout = time.monotonic()

        if self._debug:
            with self._output:
                # print(f"Relayout event detected: from {old} to {new}")
                pass
        self.render()

    def add_param(self, parameter_id, value=0.0, min=-1, max=1, step=0.01):
        """
        Add a SmartFloatSlider parameter to the controls panel.

        Parameters
        ----------
        name : str
            The name of the parameter.
        slider : SmartFloatSlider
            The slider widget to add.
        """

        description = f"${sp.latex(parameter_id)}$"  # Can be enriched later
        if parameter_id in self._params:
            if self._debug:
                with self._output:
                    print(f"Parameter {parameter_id} already exists. Skipping.")
            return

        slider = SmartFloatSlider(
            description=description, value=value, min=min, max=max, step=step
        )
        self.panels["controls"].children += (slider,)
        self._params[parameter_id] = slider

        def rerender_on_param_change(change):
            self.render()

        slider.observe(rerender_on_param_change, names="value")
        return

    @property
    def title(self):
        return self._figure.layout.title.text

    @title.setter
    def title(self, value):
        self.update_layout(
            title=dict(
                text=value,  # Your title text here
            )
        )

    @property
    def x_range(self):
        return self._x_range

    @x_range.setter
    def x_range(self, value):
        x_min, x_max = value
        value = (
            InputConvert(x_min, dest_type=float),
            InputConvert(x_max, dest_type=float),
        )
        if x_min > x_max:
            raise ValueError(f"x_min ({x_min}) must be less than x_max ({x_max})")
        self._figure.update_xaxes(range=value)
        self._x_range = value

    @property
    def y_range(self):
        return self._y_range

    @y_range.setter
    def y_range(self, value):
        y_min, y_max = value
        value = (
            InputConvert(y_min, dest_type=float),
            InputConvert(y_max, dest_type=float),
        )
        if y_min > y_max:
            raise ValueError(f"y_min ({y_min}) must be less than y_max ({y_max})")
        self._figure.update_yaxes(range=value)
        self._y_range = value

    @property
    def current_x_range(self):
        return self._figure.layout.xaxis.range

    @property
    def current_y_range(self):
        return self._figure.layout.yaxis.range

    @property
    def sampling_points(self):
        return self._sampling_points

    @sampling_points.setter
    def sampling_points(self, value):
        self._sampling_points = value

    def add_scatter(self, **scatter_kwargs):
        """
        Add a scatter trace to the figure.

        Parameters
        ----------
        scatter_kwargs : dict
            Keyword arguments for the scatter trace.
        """
        self._figure.add_scatter(**scatter_kwargs)

    def _ipython_display_(self, **kwargs):
        """
        IPython display hook to show the figure in Jupyter notebooks.
        """
        display(self._output)
        return self._output

    def update_layout(self, **layout_kwargs):
        """
        Update the layout of the figure.

        Parameters
        ----------
        layout_kwargs : dict
            Keyword arguments for updating the figure layout.
        """
        self._figure.update_layout(**layout_kwargs)

    def plot(
        self, var, func, parameters=None, id=None, x_domain=None, sampling_points=None
    ):
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
            **Important:** In this version, pass ``[]`` when there are no parameters.
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

        Choose a wider computation domain than the visible window:

        >>> fig.plot(x, sp.sin(x), parameters=[], id="sin", x_domain=(-20, 20))

        Increase resolution:

        >>> fig.plot(x, sp.sin(x), parameters=[], id="sin", sampling_points=5000)
        """
        if id is None:
            for n in range(101):  # 0 to 100 inclusive
                if id not in self.plots:
                    id = f"f_{n}"
                    break
            if id is None:
                raise ValueError("No available f_n identifiers (max 100 reached)")

        if self._debug:
            with self._output:
                print(f"Plotting {sp.latex(func)}, var={sp.latex(var)}")
            if parameters is not None:
                print(f"Parameters: {parameters}")

        if parameters is None:
            parameters = []

        for p in parameters:
            self.add_param(p)

        if id in self.plots:
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

    def render(self):
        """
        Render all plots on the figure.
        """
        with self._figure.batch_update():
            for plot in self.plots.values():
                plot.render()


# === END SECTION: SmartFigure [id: SmartFigure]===
