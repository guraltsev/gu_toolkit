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
  :meth:`SmartFigure.get_info_output`. This design is deliberate: printing directly
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
- SmartFigure: The main coordinator/facade.
- SmartFigureLayout: Handles all UI/Widget construction, CSS/JS injection, and layout logic.
- ParameterManager: Handles slider creation, storage, and change hooks. Acts as a dict proxy.
- InfoPanelManager: Handles the info sidebar and component registry.
- SmartPlot: Handles the specific math-to-trace rendering logic.


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
import warnings
import logging
from contextlib import contextmanager
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
from .numpify import numpify_cached
from .PlotlyPane import PlotlyPane, PlotlyPaneStyle
from .SmartSlider import SmartFloatSlider


# Module logger
# - Uses a NullHandler so importing this module never configures global logging.
# - Callers can enable logs via standard logging configuration.
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

_FIGURE_STACK: List["SmartFigure"] = []


def _current_figure() -> Optional["SmartFigure"]:
    """Return the most recently pushed SmartFigure, if any.

    Returns
    -------
    SmartFigure or None
        The current figure on the stack, or ``None`` if no figure is active.
    """
    if not _FIGURE_STACK:
        return None
    return _FIGURE_STACK[-1]


def _push_current_figure(fig: "SmartFigure", display_on_enter: bool) -> None:
    """Push a SmartFigure onto the global stack and optionally display it.

    Parameters
    ----------
    fig : SmartFigure
        The figure to mark as current.
    display_on_enter : bool
        Whether to display the figure immediately (first time only).

    Returns
    -------
    None
    """
    _FIGURE_STACK.append(fig)
    if display_on_enter and not fig._has_been_displayed:
        display(fig)
        fig._has_been_displayed = True


def _pop_current_figure(fig: "SmartFigure") -> None:
    """Remove a specific SmartFigure from the global stack if present.

    Parameters
    ----------
    fig : SmartFigure
        The figure to remove.

    Returns
    -------
    None
    """
    if not _FIGURE_STACK:
        return
    if _FIGURE_STACK[-1] is fig:
        _FIGURE_STACK.pop()
        return
    for i in range(len(_FIGURE_STACK) - 1, -1, -1):
        if _FIGURE_STACK[i] is fig:
            del _FIGURE_STACK[i]
            break


@contextmanager
def _use_figure(fig: "SmartFigure", display_on_enter: bool) -> Iterator["SmartFigure"]:
    """Context manager that temporarily sets a SmartFigure as current.

    Parameters
    ----------
    fig : SmartFigure
        The figure to make current within the context.
    display_on_enter : bool
        Whether to display the figure when entering.

    Yields
    ------
    SmartFigure
        The same figure passed in.
    """
    _push_current_figure(fig, display_on_enter=display_on_enter)
    try:
        yield fig
    finally:
        _pop_current_figure(fig)


# -----------------------------
# Small type aliases
# -----------------------------
NumberLike = Union[int, float]
NumberLikeOrStr = Union[int, float, str]
RangeLike = Tuple[NumberLikeOrStr, NumberLikeOrStr]
VisibleSpec = Union[bool, str]  # Plotly uses True/False or the string "legendonly".


# =============================================================================
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
        """
        super().__init__()
        self._displayed = False

    def _repr_mimebundle_(self, include: Any = None, exclude: Any = None, **kwargs: Any) -> Any:
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
        This flag is only updated when the widget is actually displayed in Jupyter.

        See Also
        --------
        OneShotOutput.reset_display_state : Reset the display flag.
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

        Notes
        -----
        Use this sparingly; it re-enables multiple displays of the same widget
        which can be confusing in notebooks.

        See Also
        --------
        OneShotOutput.has_been_displayed : Check whether the widget was shown.
        """
        self._displayed = False


# =============================================================================
# SECTION: SmartFigureLayout (The View) [id: SmartFigureLayout]
# =============================================================================

class SmartFigureLayout:
    """
    Manages the visual structure and widget hierarchy of a SmartFigure.
    
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
        >>> layout = SmartFigureLayout(title="My Plot")  # doctest: +SKIP
        >>> layout.get_title()  # doctest: +SKIP
        'My Plot'

        Notes
        -----
        The plot container is given a concrete height (``60vh``) to ensure Plotly
        has a real size to render into.

        See Also
        --------
        SmartFigureLayout.set_plot_widget : Attach the plot widget.
        SmartFigureLayout.update_sidebar_visibility : Control sidebar visibility.
        """
        self._reflow_callback: Optional[Callable[[], None]] = None

        # 1. Title Bar
        #    We use HTMLMath for proper LaTeX title rendering.
        self.title_html = widgets.HTMLMath(value=title, layout=widgets.Layout(margin="0px"))
        self.full_width_checkbox = widgets.Checkbox(
            value=False,
            description="Full width plot",
            indent=False,
            layout=widgets.Layout(width="160px", margin="0px"),
        )
        self._titlebar = widgets.HBox(
            [self.title_html, self.full_width_checkbox],
            layout=widgets.Layout(
                width="100%", align_items="center", justify_content="space-between", margin="0 0 6px 0"
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

        # 3. Controls Sidebar (The "Right" Panel)
        #    Initially hidden (display="none") until parameters or info widgets are added.
        self.params_header = widgets.HTML("<b>Parameters</b>", layout=widgets.Layout(display="none", margin="0"))
        self.params_box = widgets.VBox(
            layout=widgets.Layout(
                width="100%",
                display="none",
                padding="8px",
                border="1px solid rgba(15,23,42,0.08)",
                border_radius="10px",
            )
        )

        self.info_header = widgets.HTML("<b>Info</b>", layout=widgets.Layout(display="none", margin="10px 0 0 0"))
        self.info_box = widgets.VBox(
            layout=widgets.Layout(
                width="100%",
                display="none",
                padding="8px",
                border="1px solid rgba(15,23,42,0.08)",
                border_radius="10px",
            )
        )

        self.sidebar_container = widgets.VBox(
            [self.params_header, self.params_box, self.info_header, self.info_box],
            layout=widgets.Layout(
                margin="0px", padding="0px 0px 0px 10px", flex="0 1 380px",
                min_width="300px", max_width="400px", display="none"
            ),
        )

        # 4. Main Content Wrapper (Flex)
        #    Uses flex-wrap so the sidebar drops below the plot on narrow screens.
        self.content_wrapper = widgets.Box(
            [self.plot_container, self.sidebar_container],
            layout=widgets.Layout(
                display="flex", flex_flow="row wrap", align_items="flex-start",
                width="100%", gap="8px"
            ),
        )

        # 5. Root Widget
        self.root_widget = widgets.VBox(
            [self._titlebar, self.content_wrapper],
            layout=widgets.Layout(width="100%")
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
        >>> layout = SmartFigureLayout()  # doctest: +SKIP
        >>> out = layout.output_widget  # doctest: +SKIP

        Notes
        -----
        ``OneShotOutput`` prevents accidental double-display of the same widget.

        See Also
        --------
        OneShotOutput : Output wrapper that enforces single display.
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
        >>> layout = SmartFigureLayout()  # doctest: +SKIP
        >>> layout.set_title("Demo")  # doctest: +SKIP

        Notes
        -----
        HTML/LaTeX rendering is handled by the underlying ``HTMLMath`` widget.

        See Also
        --------
        SmartFigureLayout.get_title : Read the current title.
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
        >>> layout = SmartFigureLayout(title="Demo")  # doctest: +SKIP
        >>> layout.get_title()  # doctest: +SKIP
        'Demo'

        Notes
        -----
        The title is stored on the underlying ``HTMLMath`` widget.

        See Also
        --------
        SmartFigureLayout.set_title : Update the title.
        """
        return self.title_html.value

    def update_sidebar_visibility(self, has_params: bool, has_info: bool) -> None:
        """
        Updates visibility of headers and the sidebar itself based on content.
        
        This prevents empty "Parameters" or "Info" headers from cluttering the UI.

        Parameters
        ----------
        has_params : bool
            Whether parameter sliders exist.
        has_info : bool
            Whether info outputs exist.

        Returns
        -------
        None

        Examples
        --------
        >>> layout = SmartFigureLayout()  # doctest: +SKIP
        >>> layout.update_sidebar_visibility(has_params=True, has_info=False)  # doctest: +SKIP

        Notes
        -----
        The sidebar container is hidden entirely when both sections are empty.

        See Also
        --------
        SmartFigureLayout.set_plot_widget : Attach the main plot widget.
        """
        self.params_header.layout.display = "block" if has_params else "none"
        self.params_box.layout.display = "flex" if has_params else "none"
        
        self.info_header.layout.display = "block" if has_info else "none"
        self.info_box.layout.display = "flex" if has_info else "none"

        show_sidebar = has_params or has_info
        self.sidebar_container.layout.display = "flex" if show_sidebar else "none"

    def set_plot_widget(
        self,
        widget: widgets.Widget,
        *,
        reflow_callback: Optional[Callable[[], None]] = None,
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
        >>> layout = SmartFigureLayout()  # doctest: +SKIP
        >>> dummy = widgets.Box()  # doctest: +SKIP
        >>> layout.set_plot_widget(dummy)  # doctest: +SKIP

        Notes
        -----
        The reflow callback is used to trigger Plotly resize logic when the
        layout changes (e.g., full-width toggle).

        See Also
        --------
        SmartFigureLayout._on_full_width_change : Layout toggle handler.
        """
        self.plot_container.children = (widget,)
        self._reflow_callback = reflow_callback

    def _on_full_width_change(self, change: Dict[str, Any]) -> None:
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
        plot_layout = self.plot_container.layout
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
        if self._reflow_callback is not None:
            self._reflow_callback()


# =============================================================================
# SECTION: ParameterManager (The Model for Parameters) [id: ParameterManager]
# =============================================================================

class ParameterManager:
    """
    Manages the collection of parameter sliders and change hooks.

    Responsibilities:
    - Creating and reusing SmartFloatSlider widgets.
    - Storing current parameter values.
    - Executing hooks when parameters change.
    - **Backward Compatibility:** Acts like a dictionary so `fig.params[sym]` works.

    Design Note:
    ------------
    By centralizing parameter logic here, we decouple the "state" of the math
    from the "rendering" of the figure.
    """

    def __init__(self, render_callback: Callable[[str, Any], None], layout_box: widgets.Box) -> None:
        """Initialize the manager with a render callback and layout container.

        Parameters
        ----------
        render_callback : callable
            Function invoked when parameters change. Signature: ``(reason, change)``.
        layout_box : ipywidgets.Box
            Container where slider widgets will be added.

        Returns
        -------
        None

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP

        Notes
        -----
        ``render_callback`` is invoked on slider changes with ``(reason, change)``.

        See Also
        --------
        ParameterManager.add_param : Create a slider for a symbol.
        SmartFigure.render : Render callback used by the figure.
        """
        self._sliders: Dict[Symbol, SmartFloatSlider] = {}
        self._hooks: Dict[Hashable, Callable[[Dict, Any], Any]] = {}
        self._hook_counter: int = 0
        self._render_callback = render_callback
        self._layout_box = layout_box # The VBox where sliders live

    def add_param(self, symbol: Symbol, **kwargs: Any) -> SmartFloatSlider:
        """
        Create or reuse a slider for the given symbol.

        Parameters
        ----------
        symbol : sympy.Symbol
            The parameter symbol.
        **kwargs :
            Options for the slider (min, max, value, step).

        Returns
        -------
        SmartFloatSlider
            The slider instance for the symbol.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> slider = mgr.add_param(a, min=-2, max=2)  # doctest: +SKIP

        Notes
        -----
        Existing sliders are reused, so calling ``add_param`` repeatedly is safe.

        See Also
        --------
        ParameterManager.get_value : Read the current parameter value.
        SmartFigure.add_param : Public facade for adding sliders.
        """
        if symbol in self._sliders:
            return self._sliders[symbol]

        defaults = {'value': 0.0, 'min': -1.0, 'max': 1.0, 'step': 0.01}
        config = {**defaults, **kwargs}
        
        slider = SmartFloatSlider(
            description=f"${sp.latex(symbol)}$",
            value=float(config['value']),
            min=float(config['min']),
            max=float(config['max']),
            step=float(config['step'])
        )
        
        # Observe changes
        slider.observe(self._on_slider_change, names="value")
        
        self._sliders[symbol] = slider
        self._layout_box.children += (slider,)
        return slider

    def get_value(self, symbol: Symbol) -> float:
        """Return the current float value of a parameter.

        Parameters
        ----------
        symbol : sympy.Symbol
            Parameter symbol to query.

        Returns
        -------
        float
            Current slider value, or ``0.0`` if no slider exists.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> mgr.get_value(a)
        0.0

        Notes
        -----
        Returns ``0.0`` when the symbol has not been added as a slider.

        See Also
        --------
        ParameterManager.add_param : Create a slider for a symbol.
        """
        return self._sliders[symbol].value if symbol in self._sliders else 0.0

    @property
    def has_params(self) -> bool:
        """Whether any parameters (sliders) have been created.

        Returns
        -------
        bool
            ``True`` if at least one slider exists.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> mgr.has_params
        False

        Notes
        -----
        This is used to toggle sidebar visibility in the layout.

        See Also
        --------
        SmartFigureLayout.update_sidebar_visibility : Sidebar toggling logic.
        """
        return len(self._sliders) > 0

    def add_hook(self, callback: Callable, hook_id: Optional[Hashable] = None, fig: Any = None) -> Hashable:
        """
        Register a parameter change hook. 
        The callback is run immediately on registration, with an empty change dict.
        
        Parameters
        ----------
        callback: Callable
            The function to call (signature: (change, fig)).
        hook_id: Hashable, optional
            Optional unique identifier.
        fig: SmartFigure
            The SmartFigure instance. Crucial for passing to the callback immediately
            so the hook can initialize.

        Returns
        -------
        Hashable
            The hook ID.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> hook_id = mgr.add_hook(lambda *_: None)  # doctest: +SKIP

        Notes
        -----
        The callback signature is ``(change, fig)``, where ``change`` is a
        traitlets change dictionary and ``fig`` may be ``None`` if not provided.

        See Also
        --------
        SmartFigure.add_param_change_hook : Public hook registration API.
        """
        if hook_id is None:
            self._hook_counter += 1
            hook_id = f"hook:{self._hook_counter}"
        self._hooks[hook_id] = callback
        
        # Run immediately on registration
        try:
            callback({}, fig) 
        except Exception as e:
            warnings.warn(f"Hook failed on init: {e}")
        return hook_id

    def _on_slider_change(self, change: Dict[str, Any]) -> None:
        """Handle slider changes by triggering the render callback.

        Parameters
        ----------
        change : dict
            Traitlets change dictionary emitted by the slider.

        Returns
        -------
        None
        """
        # 1. Trigger main render via the callback passed in __init__
        self._render_callback("param_change", change)
    
    def get_hooks(self) -> Dict[Hashable, Callable]:
        """Return a copy of the registered hook dictionary.

        Returns
        -------
        dict
            Mapping of hook IDs to callbacks.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> isinstance(mgr.get_hooks(), dict)
        True

        Notes
        -----
        The returned dictionary maps hook IDs to callbacks.

        See Also
        --------
        ParameterManager.add_hook : Register a hook.
        """
        return self._hooks

    # --- Dict-like Interface for Backward Compatibility ---
    # This allows `fig.params[symbol]` to work in user hooks.
    
    def __getitem__(self, key: Symbol) -> SmartFloatSlider:
        """Return the slider for the given symbol.

        Parameters
        ----------
        key : sympy.Symbol
            Parameter symbol.

        Returns
        -------
        SmartFloatSlider
            Slider associated with the symbol.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> mgr.add_param(a)  # doctest: +SKIP
        >>> mgr[a]  # doctest: +SKIP

        Notes
        -----
        This is provided for backwards compatibility with dict-like usage.

        See Also
        --------
        ParameterManager.get : Safe access with a default.
        """
        return self._sliders[key]
    
    def __contains__(self, key: Symbol) -> bool:
        """Check if a slider exists for a symbol.

        Parameters
        ----------
        key : sympy.Symbol
            Parameter symbol.

        Returns
        -------
        bool
            ``True`` if the symbol is present.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> a in mgr
        False

        Notes
        -----
        Use this to guard access with ``mgr[key]``.

        See Also
        --------
        ParameterManager.get : Safe access with a default.
        """
        return key in self._sliders
    
    def items(self) -> Iterator[Tuple[Symbol, SmartFloatSlider]]:
        """Iterate over ``(Symbol, SmartFloatSlider)`` pairs.

        Returns
        -------
        iterator
            Iterator over the internal slider mapping.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(mgr.items())
        []

        Notes
        -----
        Mirrors ``dict.items()`` for compatibility.

        See Also
        --------
        ParameterManager.keys : Iterate over symbols only.
        ParameterManager.values : Iterate over slider widgets only.
        """
        return self._sliders.items()
    
    def keys(self) -> Iterator[Symbol]:
        """Iterate over parameter symbols.

        Returns
        -------
        iterator
            Iterator over parameter symbols.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(mgr.keys())
        []

        Notes
        -----
        Mirrors ``dict.keys()`` for compatibility.

        See Also
        --------
        ParameterManager.items : Iterate over (symbol, slider) pairs.
        """
        return self._sliders.keys()
    
    def values(self) -> Iterator[SmartFloatSlider]:
        """Iterate over slider instances.

        Returns
        -------
        iterator
            Iterator over sliders.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(mgr.values())
        []

        Notes
        -----
        Mirrors ``dict.values()`` for compatibility.

        See Also
        --------
        ParameterManager.items : Iterate over (symbol, slider) pairs.
        """
        return self._sliders.values()
    
    def get(self, key: Symbol, default: Any = None) -> Any:
        """Return a slider if present; otherwise return a default.

        Parameters
        ----------
        key : sympy.Symbol
            Parameter symbol.
        default : Any, optional
            Default value returned if no slider exists.

        Returns
        -------
        Any
            Slider instance or the default value.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> mgr.get(a) is None
        True

        Notes
        -----
        This mirrors ``dict.get`` and avoids ``KeyError``.

        See Also
        --------
        ParameterManager.__getitem__ : Direct access that may raise ``KeyError``.
        """
        return self._sliders.get(key, default)


# =============================================================================
# SECTION: InfoPanelManager (The Model for Info) [id: InfoPanelManager]
# =============================================================================

class InfoPanelManager:
    """
    Manages the 'Info' section output widgets and interactive components.

    It allows adding "Output" widgets (where you can print text or display charts)
    and registering "Stateful Components" (classes that update when sliders move).
    """
    
    _ID_REGEX = re.compile(r"^info:(\d+)$")

    def __init__(self, layout_box: widgets.Box) -> None:
        """Initialize the info panel manager.

        Parameters
        ----------
        layout_box : ipywidgets.Box
            Container where info outputs will be added.

        Returns
        -------
        None

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP

        Notes
        -----
        Outputs are stored by ID so they can be reused and updated in place.

        See Also
        --------
        InfoPanelManager.get_output : Create or retrieve an output widget.
        """
        self._outputs: Dict[Hashable, widgets.Output] = {}
        self._components: Dict[Hashable, Any] = {}
        self._layout_box = layout_box
        self._counter = 0

    def get_output(self, id: Optional[Hashable] = None, **layout_kwargs: Any) -> widgets.Output:
        """
        Get or create an Info Output widget.

        Parameters
        ----------
        id : hashable, optional
            Unique identifier for the output. If omitted, a new ID is generated.
        **layout_kwargs : Any
            Keyword arguments forwarded to ``ipywidgets.Layout``.

        Returns
        -------
        ipywidgets.Output
            Output widget associated with the ID.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> out = panel.get_output("info:1")  # doctest: +SKIP

        Notes
        -----
        If ``id`` matches the ``info:<n>`` pattern, the internal counter is updated
        to avoid collisions with auto-generated IDs.

        See Also
        --------
        SmartFigure.get_info_output : Public facade for info outputs.
        """
        if id is None:
            self._counter += 1
            id = f"info:{self._counter}"
        
        if id in self._outputs:
            out = self._outputs[id]
            if layout_kwargs:
                out.layout = widgets.Layout(**layout_kwargs)
            return out
        
        # Validate ID if string (avoids collision with auto-generated IDs)
        if isinstance(id, str):
            m = self._ID_REGEX.match(id)
            if m:
                self._counter = max(self._counter, int(m.group(1)))

        out = widgets.Output(layout=widgets.Layout(**layout_kwargs))
        setattr(out, 'id', id)
        
        self._outputs[id] = out
        self._layout_box.children += (out,)
        return out

    def add_component(self, id: Hashable, component_inst: Any) -> None:
        """Register an info component instance.

        Parameters
        ----------
        id : hashable
            Unique identifier for the component.
        component_inst : Any
            Component instance to store.

        Returns
        -------
        None

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.add_component("demo", object())  # doctest: +SKIP

        Notes
        -----
        Components are stored by ID and can be retrieved later for updates.

        See Also
        --------
        InfoPanelManager.get_component : Retrieve a registered component.
        SmartFigure.add_info_component : Higher-level component registration.
        """
        self._components[id] = component_inst

    def get_component(self, id: Hashable) -> Any:
        """Retrieve a previously registered info component.

        Parameters
        ----------
        id : hashable
            Component identifier.

        Returns
        -------
        Any
            The registered component instance.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.add_component("demo", object())  # doctest: +SKIP
        >>> panel.get_component("demo")  # doctest: +SKIP

        Notes
        -----
        This raises ``KeyError`` if the component is not registered.

        See Also
        --------
        InfoPanelManager.add_component : Register a component instance.
        """
        return self._components[id]

    @property
    def has_info(self) -> bool:
        """Whether any info outputs exist.

        Returns
        -------
        bool
            ``True`` if at least one output has been created.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.has_info
        False

        Notes
        -----
        This is used to toggle sidebar visibility in the layout.

        See Also
        --------
        SmartFigureLayout.update_sidebar_visibility : Sidebar toggling logic.
        """
        return len(self._outputs) > 0


# =============================================================================
# SECTION: SmartPlot (The specific logic for one curve) [id: SmartPlot]
# =============================================================================

class SmartPlot:
    """
    A single plotted curve managed by a :class:`SmartFigure`.

    Conceptually, a ``SmartPlot`` is “one function on one set of axes”.
    It owns a single Plotly trace (a line plot) and knows how to:

    - compile the SymPy expression to a fast NumPy function (via ``numpify_cached``),
    - sample x-values on an appropriate domain,
    - evaluate y-values (including current slider parameter values),
    - push the sampled data into the Plotly trace.
    """

    def __init__(
        self,
        var: Symbol,
        func: Expr,
        smart_figure: "SmartFigure",
        parameters: Sequence[Symbol] = [],
        x_domain: Optional[RangeLike] = None,
        sampling_points: Optional[int,str] = None,
        label: str = "",
        visible: VisibleSpec = True,
    ) -> None:
        """
        Create a new SmartPlot instance. (Usually called by SmartFigure.plot)

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable for the function.
        func : sympy.Expr
            Symbolic expression to plot.
        smart_figure : SmartFigure
            Owning figure.
        parameters : sequence[sympy.Symbol], optional
            Parameter symbols used in the expression.
        x_domain : RangeLike or None, optional
            Optional domain override for this plot.
        sampling_points : int or str, optional
            Number of samples; use ``"figure_default"`` to inherit from the figure.
        label : str, optional
            Trace label shown in the legend.
        visible : bool or "legendonly", optional
            Plotly visibility setting.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP

        Notes
        -----
        ``SmartPlot`` instances are normally created via :meth:`SmartFigure.plot`.

        See Also
        --------
        SmartFigure.plot : Public API for creating plots.
        SmartPlot.update : Update plot attributes in place.
        """
        self._smart_figure = smart_figure
        
        # Add trace to figure
        self._smart_figure.figure_widget.add_scatter(x=[], y=[], mode="lines", name=label, visible=visible)
        self._plot_handle = self._smart_figure.figure_widget.data[-1]

        self._suspend_render = True
        self.set_func(var, func, parameters)
        self.x_domain = x_domain
        
        if sampling_points == "figure_default":
            sampling_points = None
        self.sampling_points = sampling_points

        self._suspend_render = False
        
        self.render()

    def set_func(self, var: Symbol, func: Expr, parameters: Sequence[Symbol] = []) -> None:
        """
        Set the independent variable and symbolic function for this plot.
        Triggers recompilation via ``numpify_cached``.

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable.
        func : sympy.Expr
            Symbolic expression to plot.
        parameters : sequence[sympy.Symbol], optional
            Parameter symbols used in the expression.

        Returns
        -------
        None

        Examples
        --------
        >>> x, a = sp.symbols("x a")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.set_func(x, a * sp.cos(x), parameters=[a])  # doctest: +SKIP

        Notes
        -----
        Changing the function updates the internal NumPy-compiled callable.

        See Also
        --------
        SmartPlot.update : Update multiple attributes in one call.
        """
        parameters = list(parameters) 
        # Compile
        self._f_numpy = numpify_cached(func, args=[var] + parameters)
        # Store
        self._var = var
        self._parameters = parameters
        self._func = func

    @property
    def label(self) -> str:
        """Return the legend label for this plot.

        Returns
        -------
        str
            The trace name.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig, label="sin")  # doctest: +SKIP
        >>> plot.label  # doctest: +SKIP
        'sin'

        Notes
        -----
        This maps to the Plotly trace ``name`` property.

        See Also
        --------
        SmartPlot.label : Setter to update the label.
        """
        return self._plot_handle.name

    @label.setter
    def label(self, value: str) -> None:
        """Set the legend label for this plot.

        Parameters
        ----------
        value : str
            New legend label.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.label = "sin(x)"  # doctest: +SKIP

        Notes
        -----
        The label appears in the Plotly legend.

        See Also
        --------
        SmartPlot.label : Getter for the current label.
        """
        self._plot_handle.name = value

    def figure(self) -> "SmartFigure":
        """Return the SmartFigure that owns this plot.

        Returns
        -------
        SmartFigure
            Owning figure instance.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.figure() is fig  # doctest: +SKIP
        True

        Notes
        -----
        Use this to access shared settings like ranges or parameter values.

        See Also
        --------
        SmartFigure.params : Parameter manager for the owning figure.
        """
        return self._smart_figure

    @property
    def x_domain(self) -> Optional[Tuple[float, float]]:
        """Return the explicit x-domain override for this plot.

        Returns
        -------
        tuple[float, float] or None
            Explicit domain override or ``None`` to use the figure range.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig, x_domain=(-2, 2))  # doctest: +SKIP
        >>> plot.x_domain  # doctest: +SKIP
        (-2.0, 2.0)

        Notes
        -----
        When set, the plot will extend sampling beyond the figure's viewport.

        See Also
        --------
        SmartPlot.x_domain : Setter for domain overrides.
        """
        return self._x_domain

    @x_domain.setter
    def x_domain(self, value: Optional[RangeLike]) -> None:
        """Set the explicit x-domain for this plot.

        Parameters
        ----------
        value : RangeLike or None
            Domain override or ``None`` to use the figure range.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.x_domain = (-1, 1)  # doctest: +SKIP

        Notes
        -----
        Setting to ``None`` or ``"figure_default"`` uses the figure's current range.

        See Also
        --------
        SmartFigure.x_range : Default figure range.
        """
        
        if value is None:
            self._x_domain = None
        elif value == "figure_default":
            self._x_domain = None
        else:
            raw_min, raw_max = value
            self._x_domain = (float(InputConvert(raw_min, float)), float(InputConvert(raw_max, float)))
            if self._x_domain[0] > self._x_domain[1]:
                raise ValueError("x_min must be <= x_max")
        self.render()

    @property
    def sampling_points(self) -> Optional[int]:
        """Return the number of sampling points for this plot.

        Returns
        -------
        int or None
            Number of samples, or ``None`` to use the figure default.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig, sampling_points=200)  # doctest: +SKIP
        >>> plot.sampling_points  # doctest: +SKIP
        200

        Notes
        -----
        ``None`` indicates the plot should inherit the figure default.

        See Also
        --------
        SmartFigure.sampling_points : Default sampling count for all plots.
        """
        return self._sampling_points

    @sampling_points.setter
    def sampling_points(self, value: Optional[int]) -> None:
        """Set the number of sampling points for this plot.

        Parameters
        ----------
        value : int or None
            Number of samples, or ``None`` to inherit from the figure.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.sampling_points = 400  # doctest: +SKIP

        Notes
        -----
        A higher sample count yields smoother curves at the cost of performance.

        See Also
        --------
        SmartPlot.render : Recompute samples after updates.
        """
        self._sampling_points = int(InputConvert(value, int)) if value is not None else None
        self.render()

    @property
    def visible(self) -> VisibleSpec:
        """Return Plotly's visibility state for the trace.

        Returns
        -------
        bool or str
            ``True``, ``False``, or ``"legendonly"``.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.visible  # doctest: +SKIP
        True

        Notes
        -----
        Plotly supports ``True``, ``False``, or ``"legendonly"``.

        See Also
        --------
        SmartPlot.visible : Setter to update visibility.
        """
        return self._plot_handle.visible

    @visible.setter
    def visible(self, value: VisibleSpec) -> None:
        """Set Plotly's visibility state for the trace.

        Parameters
        ----------
        value : bool or "legendonly"
            Visibility state.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.visible = "legendonly"  # doctest: +SKIP

        Notes
        -----
        If visibility is set to ``True``, the plot re-renders immediately.

        See Also
        --------
        SmartPlot.render : Manually trigger a render.
        """
        self._plot_handle.visible = value
        if value is True:
            self.render()

    def render(self) -> None:
        """
        Compute (x, y) samples and update the Plotly trace.
        Skips computation if the plot is hidden.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.render()  # doctest: +SKIP

        Notes
        -----
        Rendering is skipped when the trace is hidden or when render is suspended.

        See Also
        --------
        SmartFigure.render : Render all plots in the figure.
        """
        if self._suspend_render or self.visible is not True:
            return

        # 1. Determine Range
        fig = self._smart_figure
        viewport = fig.current_x_range or fig.x_range
        
        if self.x_domain is None:
            x_min, x_max = float(viewport[0]), float(viewport[1])
        else:
            x_min = min(float(viewport[0]), float(self.x_domain[0]))
            x_max = max(float(viewport[1]), float(self.x_domain[1]))

        # 2. Determine Sampling
        num = self.sampling_points or fig.sampling_points or 500
        
        # 3. Compute
        x_values = np.linspace(x_min, x_max, num=int(num))
        args = [x_values]
        if self._parameters:
            # Retrieve values from the manager
            for p in self._parameters:
                args.append(fig.params.get_value(p))
        
        y_values = np.asarray(self._f_numpy(*args))
        
        # 4. Update Trace
        with fig.figure_widget.batch_update():
            self._plot_handle.x = x_values
            self._plot_handle.y = y_values
    
    def update(self, **kwargs: Any) -> None:
        """Update multiple plot attributes at once.

        Parameters
        ----------
        **kwargs : Any
            Supported keys include ``label``, ``x_domain``, ``sampling_points``,
            ``var``, ``func``, and ``parameters``.

        Returns
        -------
        None

        Examples
        --------
        >>> x, a = sp.symbols("x a")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.update(label="sin", func=a * sp.sin(x), parameters=[a])  # doctest: +SKIP

        Notes
        -----
        ``update`` will call :meth:`set_func` if any function-related keys appear.

        See Also
        --------
        SmartPlot.set_func : Update the underlying symbolic function.
        """
        if 'label' in kwargs: 
            self.label = kwargs['label']
        
        if 'x_domain' in kwargs: 
            val = kwargs['x_domain']
            if val == "figure_default":
                self.x_domain = None
            else:
                x_min = InputConvert(val[0], float)
                x_max = InputConvert(val[1], float)
                self.x_domain = (x_min, x_max)
        
        if 'sampling_points' in kwargs:
            val = kwargs['sampling_points']
            if val == "figure_default":
                self.sampling_points = None
            else:
                self.sampling_points = InputConvert(val, int)
        
        # Function update
        if any(k in kwargs for k in ('var', 'func', 'parameters')):
            v = kwargs.get('var', self._var)
            f = kwargs.get('func', self._func)
            p = kwargs.get('parameters', self._parameters)
            self.set_func(v, f, p)
            self.render()


# =============================================================================
# SECTION: SmartFigure (The Coordinator) [id: SmartFigure]
# =============================================================================

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
    - Uses a right-side controls panel for parameter sliders.
    - Supports plotting multiple curves identified by an ``id``.
    - Re-renders curves on:
      - slider changes,
      - pan/zoom changes (throttled to at most once every 0.5 seconds).

    Examples
    --------
    >>> import sympy as sp
    >>> x, a = sp.symbols("x a")
    >>> fig = SmartFigure()
    >>> fig.plot(x, a*sp.sin(x), parameters=[a], id="a_sin")
    >>> fig
    """
    
    __slots__ = [
        "_layout", "_params", "_info", "_figure", "_pane", "plots",
        "_x_range", "_y_range", "_sampling_points", "_debug",
        "_last_relayout", "_render_info_last_log_t", "_render_debug_last_log_t",
        "_has_been_displayed"
    ]

    def __init__(
        self,
        sampling_points: int = 500,
        x_range: RangeLike = (-4, 4),
        y_range: RangeLike = (-3, 3),
        debug: bool = False,
    ) -> None:
        """Initialize a SmartFigure instance with default ranges and sampling.

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
        >>> fig = SmartFigure(x_range=(-6, 6), y_range=(-2, 2))  # doctest: +SKIP
        >>> fig.sampling_points  # doctest: +SKIP
        500

        Notes
        -----
        The underlying Plotly widget is wrapped in :class:`PlotlyPane` to ensure
        responsive sizing in Jupyter layouts.

        See Also
        --------
        SmartFigure.plot : Add curves to the figure.
        SmartFigureLayout : Layout manager for the widget tree.
        """
        self._debug = debug
        self._sampling_points = sampling_points
        self.plots: Dict[str, SmartPlot] = {}
        self._has_been_displayed = False

        # 1. Initialize Layout (View)
        self._layout = SmartFigureLayout()
        
        # 2. Initialize Managers
        # Note: we pass a callback for rendering so params can trigger updates
        self._params = ParameterManager(self.render, self._layout.params_box)
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
        self._last_relayout = time.monotonic()
        self._render_info_last_log_t = 0.0
        self._render_debug_last_log_t = 0.0
        self._figure.layout.on_change(self._throttled_relayout, "xaxis.range", "yaxis.range")

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
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.title = "Demo"  # doctest: +SKIP
        >>> fig.title  # doctest: +SKIP
        'Demo'

        Notes
        -----
        Title text is rendered by the underlying ``HTMLMath`` widget.

        See Also
        --------
        SmartFigure.title : Setter to update the title.
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
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.title = r"$y=\\sin(x)$"  # doctest: +SKIP

        Notes
        -----
        LaTeX is supported via ``HTMLMath``.

        See Also
        --------
        SmartFigure.title : Getter for the current title.
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
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> isinstance(fig.figure_widget, go.FigureWidget)  # doctest: +SKIP
        True

        Notes
        -----
        Use this for low-level Plotly configuration beyond SmartFigure's API.

        See Also
        --------
        SmartFigure.plot : High-level plotting API.
        """
        return self._figure
    
    @property
    def params(self) -> ParameterManager:
        """
        The ParameterManager instance.
        Acts like a dictionary of `{Symbol: Slider}` for backward compatibility.

        Returns
        -------
        ParameterManager
            Parameter manager for slider state and hooks.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.params.has_params  # doctest: +SKIP
        False

        Notes
        -----
        Use ``fig.params[symbol]`` to access the slider widget directly.

        See Also
        --------
        SmartFigure.add_param : Explicitly add a slider.
        ParameterManager.add_hook : Register parameter change hooks.
        """
        return self._params
    
    @property
    def info_output(self) -> Dict[Hashable, widgets.Output]:
        """Dictionary of Info Output widgets indexed by id.

        Returns
        -------
        dict
            Mapping of output IDs to ``ipywidgets.Output`` instances.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> isinstance(fig.info_output, dict)
        True

        Notes
        -----
        This is a direct view of the underlying mapping for advanced use cases.

        See Also
        --------
        SmartFigure.get_info_output : Preferred API for creating outputs.
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
        >>> fig = SmartFigure(x_range=(-2, 2))  # doctest: +SKIP
        >>> fig.x_range  # doctest: +SKIP
        (-2.0, 2.0)

        Notes
        -----
        This is the range restored on Plotly double-click reset.

        See Also
        --------
        SmartFigure.current_x_range : Current viewport range.
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
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.x_range = (-5, 5)  # doctest: +SKIP

        Notes
        -----
        Values are converted via :class:`InputConvert` to allow string inputs.

        See Also
        --------
        SmartFigure.y_range : Set the default y-axis range.
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
        >>> fig = SmartFigure(y_range=(-1, 1))  # doctest: +SKIP
        >>> fig.y_range  # doctest: +SKIP
        (-1.0, 1.0)

        Notes
        -----
        This is the range restored on Plotly double-click reset.

        See Also
        --------
        SmartFigure.current_y_range : Current viewport range.
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
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.y_range = (-2, 2)  # doctest: +SKIP

        Notes
        -----
        Values are converted via :class:`InputConvert` to allow string inputs.

        See Also
        --------
        SmartFigure.x_range : Set the default x-axis range.
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
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.current_x_range  # doctest: +SKIP

        Notes
        -----
        This reflects the live Plotly viewport and may be ``None`` until the
        figure has rendered.

        See Also
        --------
        SmartFigure.x_range : Default range used for resets.
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
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.current_y_range  # doctest: +SKIP

        Notes
        -----
        This reflects the live Plotly viewport and may be ``None`` until the
        figure has rendered.

        See Also
        --------
        SmartFigure.y_range : Default range used for resets.
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
        >>> fig = SmartFigure(sampling_points=300)  # doctest: +SKIP
        >>> fig.sampling_points  # doctest: +SKIP
        300

        Notes
        -----
        Individual plots can override this setting via ``SmartPlot.sampling_points``.

        See Also
        --------
        SmartPlot.sampling_points : Per-plot sampling override.
        """
        return self._sampling_points

    @sampling_points.setter
    def sampling_points(self, val: Union[int, str, None]) -> None:
        """Set the default number of sampling points per plot.

        Parameters
        ----------
        val : int, str, or None
            Sample count or ``"figure_default"`` to clear.

        Returns
        -------
        None

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.sampling_points = 200  # doctest: +SKIP

        Notes
        -----
        Use ``"figure_default"`` to clear the custom value and defer to Plotly.

        See Also
        --------
        SmartPlot.sampling_points : Per-plot sampling override.
        """
        self._sampling_points = int(InputConvert(val, int)) if isinstance(val, (int, float, str)) and val != "figure_default" else None

    # --- Public API ---

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
            SymPy expression (e.g. ``sin(x)``).
        parameters : list[sympy.Symbol] or None, optional
            Parameter symbols. If None, they are inferred from the expression.
            If [], that means explicitly no parameters.
        x_domain : RangeLike or None, optional
            Domain of the independent variable (e.g. ``(-10, 10)``).
            If "figure_default", the figure's range is used when plotting. 
            If None, it is the same as "figure_default" for new plots while no change for existing plots.
        id : str, optional
            Unique identifier. If exists, the existing plot is updated in-place.

        sampling_points : int or str, optional
            Number of sampling points for this plot. Use ``"figure_default"``
            to inherit from the figure setting.

        Returns
        -------
        SmartPlot
            The created or updated plot instance.

        Examples
        --------
        >>> x, a = sp.symbols("x a")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.plot(x, a * sp.sin(x), parameters=[a], id="a_sin")  # doctest: +SKIP

        Notes
        -----
        - Passing ``parameters=None`` enables auto-detection of free symbols.
        - Sliders are created (or reused) via :class:`ParameterManager`.

        See Also
        --------
        SmartFigure.add_param : Manually create a slider.
        SmartPlot.update : Update an existing plot by ID.
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

        # Ensure Sliders Exist (Delegate to Manager)
        for p in parameters:
            self._params.add_param(p)
        
        # Update UI visibility
        self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)

        # Create or Update Plot
        if id in self.plots:
            update_dont_create = True
        else: 
            update_dont_create = False

        if update_dont_create:
            self.plots[id].update(var=var, func=func, parameters=parameters, x_domain=x_domain, sampling_points=sampling_points)
            plot = self.plots[id]    
        else: 
            plot = SmartPlot(
                var=var, func=func, smart_figure=self, parameters=parameters,
                x_domain=x_domain, sampling_points=sampling_points, label=id
            )
            self.plots[id] = plot
        
        return plot
        

    def render(self, reason: str = "manual", trigger: Any = None) -> None:
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
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.render()  # doctest: +SKIP

        Notes
        -----
        Parameter-change hooks are executed after plot updates when
        ``reason == "param_change"``.

        See Also
        --------
        SmartFigure.add_param_change_hook : Register change hooks.
        SmartPlot.render : Per-plot rendering logic.
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
                     callback(trigger, self) # Pass self (SmartFigure) to hooks
                 except Exception as e:
                     warnings.warn(f"Hook {h_id} failed: {e}")

    def add_param(self, symbol: Symbol, **kwargs: Any) -> SmartFloatSlider:
        """
        Add a SmartFloatSlider parameter manually.

        Parameters
        ----------
        symbol : sympy.Symbol
            Parameter symbol to create a slider for.
        **kwargs : Any
            Slider configuration (min, max, value, step).

        Returns
        -------
        SmartFloatSlider
            The created or reused slider.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> fig.add_param(a, min=-2, max=2)  # doctest: +SKIP

        Notes
        -----
        This does not plot anything by itself; it only creates the slider.

        See Also
        --------
        SmartFigure.plot : Create plots that can consume parameters.
        ParameterManager.add_param : Internal slider creation logic.
        """
        slider = self._params.add_param(symbol, **kwargs)
        self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)
        return slider

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
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> out = fig.get_info_output("summary")  # doctest: +SKIP

        Notes
        -----
        The output widget can be reused by passing the same ``id``.

        See Also
        --------
        SmartFigure.add_info_component : Register components that update outputs.
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
        2. Implements an `update(change, fig, out)` method.

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
        ...     def update(self, change, fig, out):  # doctest: +SKIP
        ...         pass  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.add_info_component("example", ExampleComponent)  # doctest: +SKIP

        Notes
        -----
        The component's ``update`` method is wired to parameter-change hooks.

        See Also
        --------
        SmartFigure.add_param_change_hook : Register hook callbacks manually.
        SmartFigure.get_info_output : Access the underlying output widget.
        """
        out = self.get_info_output(id, **kwargs)
        inst = component_factory(out, self)
        
        if not hasattr(inst, 'update'):
            raise TypeError(f"Component {id} must have an 'update' method")
        
        self._info.add_component(id, inst)
        
        # Register hook to update component on param change
        if hook_id is None: hook_id = ("info_component", id)
        
        def _hook(change: Dict, fig: SmartFigure) -> None:
            inst.update(change, fig, out)
            
        self.add_param_change_hook(_hook, hook_id=hook_id)
        return inst

    def add_param_change_hook(self, callback: Callable[[Dict, SmartFigure], Any], hook_id: Optional[Hashable] = None) -> Hashable:
        """
        Register a callback to run when *any* parameter value changes.

        Parameters
        ----------
        callback : callable
            Function with signature ``(change, fig)``.
        hook_id : hashable, optional
            Unique identifier for the hook.

        Returns
        -------
        hashable
            The hook identifier used for registration.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.add_param_change_hook(lambda *_: None)  # doctest: +SKIP

        Notes
        -----
        ``change`` is the traitlets change dictionary for the underlying slider.
        The callback runs after plots have re-rendered.

        See Also
        --------
        ParameterManager.add_hook : Lower-level hook registration.
        """
        def _wrapped(change: Dict, fig: SmartFigure) -> Any:
            with _use_figure(self, display_on_enter=False):
                return callback(change, self)

        return self._params.add_hook(_wrapped, hook_id, fig=self)

    # --- Internal / Plumbing ---

    def _throttled_relayout(self, *args: Any) -> None:
        """Handle plot relayout events with throttling.

        Parameters
        ----------
        *args : Any
            Plotly relayout event payload (unused).

        Returns
        -------
        None
        """
        now = time.monotonic()
        if now - self._last_relayout > 0.5:
            self._last_relayout = now
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

    def __enter__(self) -> "SmartFigure":
        """Enter a context where this figure is the current target.

        Returns
        -------
        SmartFigure
            The same instance, for use with ``with`` blocks.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> with fig:  # doctest: +SKIP
        ...     pass

        Notes
        -----
        Calls to the module-level :func:`plot` inside the context target this figure.

        See Also
        --------
        SmartFigure.__exit__ : Exit the context.
        plot : Module-level plotting helper.
        """
        _push_current_figure(self, display_on_enter=True)
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
        The figure is removed from the global stack when exiting the context.

        See Also
        --------
        SmartFigure.__enter__ : Enter the figure context.
        """
        _pop_current_figure(self)


def plot(
    var: Symbol,
    func: Expr,
    parameters: Optional[Sequence[Symbol]] = None,
    id: Optional[str] = None,
    x_domain: Optional[RangeLike] = None,
    sampling_points: Optional[Union[int, str]] = None,
) -> SmartPlot:
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

    Returns
    -------
    SmartPlot
        The created or updated plot instance.

    Examples
    --------
    >>> x, a = sp.symbols("x a")  # doctest: +SKIP
    >>> plot(x, a * sp.sin(x), parameters=[a], id="a_sin")  # doctest: +SKIP

    Notes
    -----
    If no figure is active, this function creates a new ``SmartFigure`` and
    displays it automatically.

    See Also
    --------
    SmartFigure.plot : Equivalent instance method.
    SmartFigure.__enter__ : Context manager for routing plots.
    """
    fig = _current_figure()
    if fig is None:
        fig = SmartFigure()
        display(fig)
    return fig.plot(
        var,
        func,
        parameters=parameters,
        id=id,
        x_domain=x_domain,
        sampling_points=sampling_points,
    )
