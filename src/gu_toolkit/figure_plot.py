"""Per-curve plotting model used by :mod:`gu_toolkit.Figure`.

Purpose
-------
Defines ``Plot``, the unit that turns one symbolic expression into one Plotly
trace. The class handles expression compilation, domain sampling, numeric
execution, and trace updates.

Concepts and structure
----------------------
Each ``Plot`` instance owns:

- symbolic state (variable/expression/parameters),
- compiled numeric callable state (via ``numpify_cached``),
- rendering state (sampled x/y arrays and trace handle),
- style state (line/trace overrides).

Architecture notes
------------------
``Plot`` is intentionally scoped to curve-level concerns and is orchestrated by
``Figure``. Figure-level concerns (layout, parameter registry, batching,
context management) are outside this module.

Important gotchas
-----------------
- ``parameters`` defaults are immutable tuples to avoid cross-instance leakage.
- ``sampling_points`` can be ``None`` to inherit figure defaults.
- ``render()`` updates an existing trace in-place; consumers should not assume
  a new trace object is created on each render.

Examples
--------
>>> import sympy as sp
>>> from gu_toolkit.Figure import Figure
>>> x = sp.symbols("x")
>>> fig = Figure()
>>> p = fig.plot(x, sp.sin(x), id="sin")  # doctest: +SKIP
>>> p.sampling_points = 800  # doctest: +SKIP

Discoverability
---------------
See next:

- ``Figure.py`` for orchestration and public API.
- ``numpify.py`` for symbolic→numeric compilation.
- ``PlotSnapshot.py`` for serialization/reproducibility support.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .Figure import Figure

import numpy as np
import plotly.graph_objects as go
import sympy as sp
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

from .figure_context import _FigureDefaultSentinel, _is_figure_default
from .figure_plot_style import validate_style_kwargs
from .figure_types import NumberLike, NumberLikeOrStr, RangeLike, VisibleSpec
from .InputConvert import InputConvert
from .numpify import DYNAMIC_PARAMETER, NumericFunction, numpify_cached
from .PlotSnapshot import PlotSnapshot


@dataclass
class PlotHandle:
    """Per-view runtime handle for a plot trace binding."""

    plot_id: str
    view_id: str
    trace_handle: go.Scatter | None
    cached_x: np.ndarray | None = None
    cached_y: np.ndarray | None = None


# SECTION: Plot (The specific logic for one curve) [id: Plot]
# =============================================================================


class Plot:
    """
    A single plotted curve managed by a :class:`Figure`.

    Conceptually, a ``Plot`` is “one function on one set of axes”.
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
        smart_figure: Figure,
        parameters: Sequence[Symbol] = (),
        x_domain: RangeLike | None = None,
        sampling_points: int | str | _FigureDefaultSentinel | None = None,
        label: str = "",
        visible: VisibleSpec = True,
        color: str | None = None,
        thickness: int | float | None = None,
        dash: str | None = None,
        line: Mapping[str, Any] | None = None,
        opacity: int | float | None = None,
        trace: Mapping[str, Any] | None = None,
        plot_id: str = "",
        view_ids: Sequence[str] | None = None,
        *,
        numeric_function: NumericFunction | None = None,
        samples: int | str | _FigureDefaultSentinel | None = None,
    ) -> None:
        """
        Create a new Plot instance. (Usually called by Figure.plot)

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable for the function.
        func : sympy.Expr
            Symbolic expression to plot.
        smart_figure : Figure
            Owning figure.
        parameters : sequence[sympy.Symbol], optional
            Parameter symbols used in the expression.
        x_domain : RangeLike or None, optional
            Optional domain override for this plot.
        sampling_points : int or str, optional
            Number of samples; use ``"figure_default"`` to inherit from the figure.
        label : str, optional
            Trace label shown in the legend.
        visible : bool, optional
            Plot visibility setting.
        color : str or None, optional
            Line color. Common formats include named colors (e.g., ``"red"``),
            hex values (e.g., ``"#ff0000"``), and ``rgb(...)``/``rgba(...)``.
        thickness : int or float, optional
            Line width in pixels. ``1`` is thin; larger values produce thicker lines.
        dash : str or None, optional
            Line pattern. Supported values: ``"solid"``, ``"dot"``, ``"dash"``,
            ``"longdash"``, ``"dashdot"``, ``"longdashdot"``.
        opacity : int or float, optional
            Overall curve opacity between ``0.0`` (fully transparent) and
            ``1.0`` (fully opaque).
        line : mapping or None, optional
            Extra per-line style fields as a mapping (advanced usage).
        trace : mapping or None, optional
            Extra full-trace style fields as a mapping (advanced usage).

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig)  # doctest: +SKIP

        Notes
        -----
        End users typically call :meth:`Figure.plot` instead of instantiating
        ``Plot`` directly.
        """
        self._smart_figure = smart_figure
        self.id = plot_id or label or "plot"
        self._x_data: np.ndarray | None = None
        self._y_data: np.ndarray | None = None
        self._handles: dict[str, PlotHandle] = {}
        self._view_ids = set(view_ids or (self._smart_figure.views.current_id,))
        self._visible: VisibleSpec = visible

        for view_id in sorted(self._view_ids):
            self._create_trace_handle(view_id=view_id, label=label)

        self._suspend_render = True
        self._update_line_style(color=color, thickness=thickness, dash=dash, line=line)
        self.opacity = opacity
        if trace:
            trace_update = dict(trace)
            for trace_handle in self._iter_trace_handles():
                trace_handle.update(**trace_update)

        # Symbolic compilation is the default path. When a precompiled
        # NumericFunction is supplied (callable-first plotting), skip the
        # symbolic compilation step and bind the numeric backend directly.
        if numeric_function is None:
            self.set_func(var, func, parameters)
        else:
            self.set_numeric_function(
                var,
                numeric_function,
                parameters=parameters,
                symbolic_expression=func,
            )
        self.x_domain = x_domain

        if samples is not None and sampling_points is not None:
            lhs = None if _is_figure_default(samples) else int(InputConvert(samples, int))
            rhs = (
                None
                if _is_figure_default(sampling_points)
                else int(InputConvert(sampling_points, int))
            )
            if lhs != rhs:
                raise ValueError(
                    "Plot() received both samples= and sampling_points= with different values; use only one samples keyword."
                )

        resolved_samples = samples if samples is not None else sampling_points
        self.samples = resolved_samples

        self._suspend_render = False

        self.render()

    def _create_trace_handle(self, *, view_id: str, label: str) -> PlotHandle:
        """Create and register a per-view Plotly trace handle."""
        figure_widget = self._smart_figure.views[view_id].figure_widget
        figure_widget.add_scatter(
            x=[],
            y=[],
            mode="lines",
            name=label,
            visible=self._visible,
        )
        trace_handle = figure_widget.data[-1]
        handle = PlotHandle(plot_id=self.id, view_id=view_id, trace_handle=trace_handle)
        self._handles[view_id] = handle
        return handle

    def _iter_trace_handles(self) -> Sequence[go.Scatter]:
        """Return all live Plotly trace handles for this plot."""
        return tuple(
            handle.trace_handle
            for handle in self._handles.values()
            if handle.trace_handle is not None
        )

    def _reference_trace_handle(self) -> go.Scatter | None:
        """Return a representative trace handle for style/property reads."""
        active = self._handles.get(self._smart_figure.views.current_id)
        if active is not None and active.trace_handle is not None:
            return active.trace_handle
        for trace_handle in self._iter_trace_handles():
            return trace_handle
        return None

    def _set_visibility_for_target_view(self, target_view: str) -> None:
        """Apply visibility updates to the requested view trace only."""
        handle = self._handles.get(target_view)
        if handle is not None and handle.trace_handle is not None:
            handle.trace_handle.visible = self._visible

    def _remove_trace_handle(self, *, view_id: str) -> None:
        """Remove and detach the trace mapped to ``view_id`` if present."""
        handle = self._handles.get(view_id)
        if handle is None or handle.trace_handle is None:
            return
        figure_widget = self._smart_figure.views[view_id].figure_widget
        figure_widget.data = tuple(
            trace for trace in figure_widget.data if trace is not handle.trace_handle
        )
        handle.trace_handle = None

    def set_func(
        self, var: Symbol, func: Expr, parameters: Sequence[Symbol] = ()
    ) -> None:
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
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.set_func(x, a * sp.cos(x), parameters=[a])  # doctest: +SKIP

        See Also
        --------
        update : Update multiple plot attributes at once.
        """
        parameters = list(parameters)
        # Compile
        self._numpified = numpify_cached(func, vars=[var] + parameters)
        # Store
        self._var = var
        self._func = func

    def set_numeric_function(
        self,
        var: Symbol,
        numeric_function: NumericFunction,
        parameters: Sequence[Symbol] = (),
        *,
        symbolic_expression: Expr | None = None,
    ) -> None:
        """Set a precompiled :class:`NumericFunction` backend for this plot.

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable used as x-axis samples.
        numeric_function : NumericFunction
            Numeric callable to evaluate during rendering.
        parameters : sequence[sympy.Symbol], optional
            Symbols to bind as dynamic figure parameters.

        Returns
        -------
        None
        """
        self._numpified = numeric_function
        self._var = var
        if numeric_function.symbolic is not None:
            self._func = sp.sympify(numeric_function.symbolic)
        elif symbolic_expression is not None:
            # Preserve meaningful labeling/snapshotting for callable-backed
            # plots even when the NumericFunction doesn't carry a symbolic form.
            self._func = sp.sympify(symbolic_expression)
        elif isinstance(getattr(self, "_func", None), sp.Expr):
            self._func = self._func
        else:
            self._func = sp.Symbol("f_numeric")

    @property
    def symbolic_expression(self) -> Expr:
        """Return the current symbolic expression used by this plot."""
        return self._func

    @property
    def parameters(self) -> tuple[Symbol, ...]:
        """Return parameter symbols in deterministic numeric-argument order."""
        return tuple(sym for sym in self._numpified.all_vars if sym != self._var)

    @property
    def views(self) -> tuple[str, ...]:
        """Return sorted view memberships for this plot."""
        return tuple(sorted(self._view_ids))

    def add_to_view(self, view_id: str) -> None:
        """Add this plot to a view membership set."""
        if view_id in self._view_ids:
            return
        self._view_ids.add(view_id)
        self._create_trace_handle(view_id=view_id, label=self.label)
        if view_id == self._smart_figure.views.current_id and self._visible is True:
            self.render(view_id=view_id)

    def remove_from_view(self, view_id: str) -> None:
        """Remove this plot from a view membership set."""
        if view_id not in self._view_ids:
            return
        self._view_ids.remove(view_id)
        self._remove_trace_handle(view_id=view_id)
        self._handles.pop(view_id, None)

    def add_views(self, views: str | Sequence[str]) -> None:
        """Add one or more views to this plot."""
        if isinstance(views, str):
            self.add_to_view(views)
            return
        for view_id in views:
            self.add_to_view(view_id)

    def remove_views(self, views: str | Sequence[str]) -> None:
        """Remove one or more views from this plot."""
        if isinstance(views, str):
            self.remove_from_view(views)
            return
        for view_id in views:
            self.remove_from_view(view_id)

    def snapshot(self, *, id: str = "") -> PlotSnapshot:
        """Return an immutable snapshot of this plot's reproducible state.

        Parameters
        ----------
        id : str, optional
            Plot identifier to store in the snapshot.  When called from
            :meth:`Figure.snapshot`, the figure passes the dict key.

        Returns
        -------
        PlotSnapshot
        """
        return PlotSnapshot(
            id=id,
            var=self._var,
            func=self._func,
            parameters=tuple(self.parameters),
            label=self.label,
            visible=self.visible,
            x_domain=self.x_domain,
            sampling_points=self.samples,
            color=self.color,
            thickness=self.thickness,
            dash=self.dash,
            opacity=self.opacity,
            views=self.views,
        )

    @property
    def numeric_expression(self) -> NumericFunction:
        """Return a live :class:`NumericFunction` bound to the figure parameter context."""
        return self._numpified.set_parameter_context(
            self._smart_figure.parameters.parameter_context
        ).freeze(
            {
                sym: DYNAMIC_PARAMETER
                for sym in self._numpified.all_vars
                if sym != self._var
            }
        )

    @property
    def x_data(self) -> np.ndarray | None:
        """
        Return the last rendered x samples.

        Returns
        -------
        numpy.ndarray or None
            A read-only NumPy array of sampled x-values from the most recent
            successful :meth:`render` call. Returns ``None`` if this plot has
            not rendered yet.
        """
        if self._x_data is None:
            return None
        x_values = self._x_data.copy()
        x_values.flags.writeable = False
        return x_values

    @property
    def y_data(self) -> np.ndarray | None:
        """
        Return the last rendered y samples.

        Returns
        -------
        numpy.ndarray or None
            A read-only NumPy array of sampled y-values from the most recent
            successful :meth:`render` call. Returns ``None`` if this plot has
            not rendered yet.
        """
        if self._y_data is None:
            return None
        y_values = self._y_data.copy()
        y_values.flags.writeable = False
        return y_values

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
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig, label="sin")  # doctest: +SKIP
        >>> plot.label  # doctest: +SKIP
        'sin'

        See Also
        --------
        update : Update the label alongside other plot attributes.
        """
        ref = self._reference_trace_handle()
        return ref.name if ref is not None else ""

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
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.label = "sin(x)"  # doctest: +SKIP

        See Also
        --------
        label : Read the current legend label.
        """
        for trace_handle in self._iter_trace_handles():
            trace_handle.name = value

    @property
    def color(self) -> str | None:
        """Return the current line color for this plot."""
        ref = self._reference_trace_handle()
        if ref is None or ref.line is None:
            return None
        return ref.line.color

    @color.setter
    def color(self, value: str | None) -> None:
        """Set the line color for this plot."""
        self._update_line_style(color=value)

    @property
    def thickness(self) -> float | None:
        """Return the current line thickness for this plot."""
        ref = self._reference_trace_handle()
        if ref is None or ref.line is None:
            return None
        return ref.line.width

    @thickness.setter
    def thickness(self, value: int | float | None) -> None:
        """Set the line thickness for this plot."""
        self._update_line_style(thickness=value)

    @property
    def dash(self) -> str | None:
        """Return the current line dash style for this plot."""
        ref = self._reference_trace_handle()
        if ref is None or ref.line is None:
            return None
        return ref.line.dash

    @dash.setter
    def dash(self, value: str | None) -> None:
        """Set the line dash style for this plot."""
        self._update_line_style(dash=value)

    @property
    def opacity(self) -> float | None:
        """Return the current trace opacity for this plot."""
        ref = self._reference_trace_handle()
        return None if ref is None else ref.opacity

    @opacity.setter
    def opacity(self, value: int | float | None) -> None:
        """Set the trace opacity for this plot (0.0 to 1.0)."""
        if value is None:
            for trace_handle in self._iter_trace_handles():
                trace_handle.opacity = None
            return
        opacity = float(InputConvert(value, float))
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0")
        for trace_handle in self._iter_trace_handles():
            trace_handle.opacity = opacity

    @property
    def figure(self) -> Figure:
        """Return the Figure that owns this plot.

        Returns
        -------
        Figure
            Owning figure instance.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.figure is fig  # doctest: +SKIP
        True

        See Also
        --------
        Figure.plot : Create or update plots on a figure.
        """
        return self._smart_figure

    @property
    def x_domain(self) -> tuple[float, float] | None:
        """Return the explicit x-domain override for this plot.

        Returns
        -------
        tuple[float, float] or None
            Explicit domain override or ``None`` to use the figure range.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig, x_domain=(-2, 2))  # doctest: +SKIP
        >>> plot.x_domain  # doctest: +SKIP
        (-2.0, 2.0)

        Notes
        -----
        When set, the plot may extend beyond the current viewport to ensure the
        full domain is drawn.
        """
        return self._x_domain

    @x_domain.setter
    def x_domain(self, value: RangeLike | None) -> None:
        """Set the explicit x-domain for this plot.

        Parameters
        ----------
        value : RangeLike or None
            Domain override or ``None``/``"figure_default"``/``"FIGURE_DEFAULT"``/``FIGURE_DEFAULT``
            to use the figure range.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.x_domain = (-1, 1)  # doctest: +SKIP

        See Also
        --------
        Figure.x_range : Update the figure-wide x-axis range.
        """

        if value is None or _is_figure_default(value):
            self._x_domain = None
        else:
            raw_min, raw_max = value
            self._x_domain = (
                float(InputConvert(raw_min, float)),
                float(InputConvert(raw_max, float)),
            )
            if self._x_domain[0] > self._x_domain[1]:
                raise ValueError("x_min must be <= x_max")
        self.render()

    @property
    def samples(self) -> int | None:
        """Return the number of samples for this plot."""
        return self._sampling_points

    @samples.setter
    def samples(self, value: int | str | _FigureDefaultSentinel | None) -> None:
        """Set the number of samples for this plot."""
        self._sampling_points = (
            int(InputConvert(value, int))
            if value is not None and not _is_figure_default(value)
            else None
        )
        self.render()

    @property
    def sampling_points(self) -> int | None:
        """Compatibility alias for :attr:`samples`."""
        return self.samples

    @sampling_points.setter
    def sampling_points(self, value: int | str | _FigureDefaultSentinel | None) -> None:
        self.samples = value

    @property
    def visible(self) -> VisibleSpec:
        """Return Plotly's visibility state for the trace.

        Returns
        -------
        bool
            ``True`` or ``False``.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.visible  # doctest: +SKIP
        True
        """
        return self._visible

    @visible.setter
    def visible(self, value: VisibleSpec) -> None:
        """Set Plotly's visibility state for the trace.

        Parameters
        ----------
        value : bool
            Visibility state.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.visible = False  # doctest: +SKIP

        See Also
        --------
        render : Recompute samples when a plot becomes visible.
        """
        self._visible = value
        for view_id in self._view_ids:
            self._set_visibility_for_target_view(view_id)
        if value is True:
            self.render()

    def render(self, view_id: str | None = None) -> None:
        """
        Compute (x, y) samples and update the Plotly trace.
        Skips computation if the plot is hidden.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.render()  # doctest: +SKIP

        Notes
        -----
        Rendering uses the figure's current viewport if it has been panned or
        zoomed.
        """
        target_view = view_id or self._smart_figure.views.current_id
        self._set_visibility_for_target_view(target_view)
        if target_view not in self._view_ids:
            return
        if self._suspend_render or self._visible is not True:
            return

        # Phase 2 keeps concrete rendering pinned to active view only.
        fig = self._smart_figure
        if target_view != fig.views.current_id:
            fig.views[target_view].is_stale = True
            return

        # 1. Determine Range
        viewport = fig.current_x_range or fig.x_range

        if self.x_domain is None:
            x_min, x_max = float(viewport[0]), float(viewport[1])
        else:
            x_min = min(float(viewport[0]), float(self.x_domain[0]))
            x_max = max(float(viewport[1]), float(self.x_domain[1]))

        # 2. Determine Sampling
        num = self.samples or fig.samples or 500

        # 3. Compute
        x_values = np.linspace(x_min, x_max, num=int(num))
        y_values = np.asarray(self.numeric_expression(x_values))
        self._x_data = x_values.copy()
        self._y_data = y_values.copy()

        # 4. Update Trace
        target_handle = self._handles[target_view].trace_handle
        if target_handle is None:
            return
        with fig.views[target_view].figure_widget.batch_update():
            target_handle.x = x_values
            target_handle.y = y_values

    def _update_line_style(
        self,
        *,
        color: str | None = None,
        thickness: int | float | None = None,
        dash: str | None = None,
        line: Mapping[str, Any] | None = None,
    ) -> None:
        """Apply incremental line-style updates to the backing Plotly trace."""

        def _coerce_line_value(value: Any) -> dict[str, Any]:
            """Normalize Plotly line-like structures to mutable dictionaries."""
            if not value:
                return {}
            if isinstance(value, Mapping):
                return dict(value)
            if hasattr(value, "to_plotly_json"):
                return value.to_plotly_json()
            try:
                return dict(value)
            except (TypeError, ValueError):
                return {}

        line_updates: dict[str, Any] = {}
        if line:
            line_updates.update(_coerce_line_value(line))
        if color is not None:
            line_updates["color"] = color
        if thickness is not None:
            line_updates["width"] = float(InputConvert(thickness, float))
        if dash is not None:
            line_updates["dash"] = dash
        if line_updates:
            for trace_handle in self._iter_trace_handles():
                current_line = _coerce_line_value(trace_handle.line)
                current_line.update(line_updates)
                trace_handle.line = current_line

    def update(self, **kwargs: Any) -> None:
        """Update multiple plot attributes at once.

        Parameters
        ----------
        **kwargs : Any
            Supported keys include ``label``, ``x_domain``, ``sampling_points``,
            ``visible``, ``var``, ``func``, ``parameters``, ``color``, ``thickness``/``width``, ``dash``,
            ``opacity``/``alpha``, ``line``, and ``trace``.

        Returns
        -------
        None

        Examples
        --------
        >>> x, a = sp.symbols("x a")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.update(label="sin", func=a * sp.sin(x), parameters=[a])  # doctest: +SKIP

        Notes
        -----
        This method is used internally by :meth:`Figure.plot` when
        updating an existing plot.
        """
        if "label" in kwargs:
            self.label = kwargs["label"]

        if "visible" in kwargs:
            self.visible = kwargs["visible"]

        if "x_domain" in kwargs:
            val = kwargs["x_domain"]
            if val is None:
                # None means "no change" during in-place updates.
                pass
            elif _is_figure_default(val):
                self.x_domain = None
            else:
                x_min = InputConvert(val[0], float)
                x_max = InputConvert(val[1], float)
                self.x_domain = (x_min, x_max)

        samples_key_present = "samples" in kwargs
        sampling_points_key_present = "sampling_points" in kwargs
        if samples_key_present and sampling_points_key_present:
            left = kwargs["samples"]
            right = kwargs["sampling_points"]
            lhs = None if _is_figure_default(left) else (
                None if left is None else int(InputConvert(left, int))
            )
            rhs = None if _is_figure_default(right) else (
                None if right is None else int(InputConvert(right, int))
            )
            if lhs != rhs:
                raise ValueError(
                    "Plot.update() received both samples= and sampling_points= with different values; use only one samples keyword."
                )

        if samples_key_present or sampling_points_key_present:
            val = kwargs["samples"] if samples_key_present else kwargs["sampling_points"]
            if val is None:
                # None means "no change" during in-place updates.
                pass
            elif _is_figure_default(val):
                self.samples = None
            else:
                self.samples = InputConvert(val, int)

        if "view" in kwargs:
            requested = kwargs["view"]
            if requested is not None:
                requested_views = (
                    {requested} if isinstance(requested, str) else set(requested)
                )
                for view_id in tuple(self._view_ids):
                    if view_id not in requested_views:
                        self.remove_from_view(view_id)
                for view_id in requested_views:
                    self.add_to_view(view_id)

        style_kwargs = validate_style_kwargs(
            {
                "color": kwargs.get("color"),
                "thickness": kwargs.get("thickness"),
                "width": kwargs.get("width"),
                "dash": kwargs.get("dash"),
                "line": kwargs.get("line"),
                "opacity": kwargs.get("opacity"),
                "alpha": kwargs.get("alpha"),
                "trace": kwargs.get("trace"),
            },
            caller="Plot.update()",
        )

        self._update_line_style(
            color=style_kwargs.get("color"),
            thickness=style_kwargs.get("thickness"),
            dash=style_kwargs.get("dash"),
            line=style_kwargs.get("line"),
        )
        if "opacity" in kwargs or "alpha" in kwargs:
            self.opacity = style_kwargs.get("opacity")
        if style_kwargs.get("trace"):
            trace_update = dict(style_kwargs["trace"])
            for trace_handle in self._iter_trace_handles():
                trace_handle.update(**trace_update)

        # Function update
        if any(k in kwargs for k in ("var", "func", "parameters", "numeric_function")):
            v = kwargs.get("var", self._var)
            f = kwargs.get("func", self._func)
            p = kwargs.get("parameters", self.parameters)
            numeric_fn = kwargs.get("numeric_function")
            if numeric_fn is not None:
                self.set_numeric_function(
                    v,
                    numeric_fn,
                    parameters=p,
                    symbolic_expression=f,
                )
            else:
                self.set_func(v, f, p)
            self.render()


# =============================================================================
