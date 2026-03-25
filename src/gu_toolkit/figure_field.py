"""Scalar-field runtime model for contour, density, and temperature plots.

This module introduces :class:`ScalarFieldPlot`, a sibling runtime type to the
existing 1D :class:`gu_toolkit.figure_plot.Plot`. Scalar fields render one
symbolic or callable expression ``z = f(x, y)`` over a rectangular 2D grid and
own either a Plotly ``Contour`` or ``Heatmap`` trace per view.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import plotly.graph_objects as go
import sympy as sp
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

from .FieldPlotSnapshot import FieldPlotSnapshot
from .InputConvert import InputConvert
from .figure_context import _is_figure_default
from .figure_field_normalization import normalize_field_inputs
from .figure_field_style import field_style_option_docs, validate_field_style_kwargs
from .figure_plot_helpers import normalize_view_ids, remove_plot_from_figure, resolve_plot_id
from .figure_types import RangeLike, VisibleSpec
from .numpify import DYNAMIC_PARAMETER, NumericFunction, numpify_cached
from .parameter_keys import ParameterKeyOrKeys, expand_parameter_keys_to_symbols

if TYPE_CHECKING:
    from .Figure import Figure

FieldRenderMode = Literal["contour", "heatmap"]
FieldGrid = tuple[int, int]


@dataclass
class FieldPlotHandle:
    """Per-view runtime handle for a scalar-field trace binding."""

    plot_id: str
    view_id: str
    trace_handle: go.Contour | go.Heatmap | None


class ScalarFieldPlot:
    """A 2D scalar field rendered as a contour or heatmap trace."""

    DEFAULT_GRID: FieldGrid = (120, 120)
    supports_style_dialog: bool = False

    def __init__(
        self,
        x_var: Symbol,
        y_var: Symbol,
        func: Expr,
        smart_figure: Figure,
        parameters: Sequence[Symbol] = (),
        x_domain: RangeLike | None = None,
        y_domain: RangeLike | None = None,
        grid: tuple[int | str, int | str] | None = None,
        label: str = "",
        visible: VisibleSpec = True,
        render_mode: FieldRenderMode = "heatmap",
        preset: str | None = None,
        colorscale: Any | None = None,
        z_range: RangeLike | None = None,
        show_colorbar: bool | None = None,
        opacity: int | float | None = None,
        reversescale: bool | None = None,
        colorbar: Mapping[str, Any] | None = None,
        trace: Mapping[str, Any] | None = None,
        levels: int | None = None,
        filled: bool | None = None,
        show_labels: bool | None = None,
        line_color: str | None = None,
        line_width: int | float | None = None,
        smoothing: str | bool | None = None,
        connectgaps: bool | None = None,
        plot_id: str = "",
        view_ids: Sequence[str] | None = None,
        *,
        numeric_function: NumericFunction | None = None,
    ) -> None:
        self._smart_figure = smart_figure
        self.id = plot_id or label or "field"
        self._label = str(label)
        self._handles: dict[str, FieldPlotHandle] = {}
        self._view_ids = set(view_ids or (self._smart_figure.views.current_id,))
        self._visible: VisibleSpec = visible
        self._x_axis_values: np.ndarray | None = None
        self._y_axis_values: np.ndarray | None = None
        self._z_data: np.ndarray | None = None
        self._suspend_render = True

        self._render_mode: FieldRenderMode = self._coerce_render_mode(render_mode)
        self._preset = self._coerce_preset(preset, render_mode=self._render_mode)
        self._colorscale: Any | None = None
        self._z_range: tuple[float, float] | None = None
        self._show_colorbar: bool = self._default_show_colorbar(self._render_mode)
        self._opacity: float | None = None
        self._reversescale: bool = False
        self._colorbar: dict[str, Any] | None = None
        self._trace_overrides: dict[str, Any] | None = None
        self._levels: int | None = None
        self._filled: bool = self._default_filled(self._render_mode)
        self._show_labels: bool = False
        self._line_color: str | None = None
        self._line_width: float | None = None
        self._smoothing: str | bool | None = None
        self._connectgaps: bool | None = None
        self._apply_creation_defaults(
            colorscale=colorscale,
            z_range=z_range,
            show_colorbar=show_colorbar,
            opacity=opacity,
            reversescale=reversescale,
            colorbar=colorbar,
            trace=trace,
            levels=levels,
            filled=filled,
            show_labels=show_labels,
            line_color=line_color,
            line_width=line_width,
            smoothing=smoothing,
            connectgaps=connectgaps,
        )

        for view_id in sorted(self._view_ids):
            self._create_trace_handle(view_id=view_id, label=label)

        if numeric_function is None:
            self.set_func(x_var, y_var, func, parameters)
        else:
            self.set_numeric_function(
                x_var,
                y_var,
                numeric_function,
                parameters=parameters,
                symbolic_expression=func,
            )

        self.x_domain = x_domain
        self.y_domain = y_domain
        self.grid = grid
        self._suspend_render = False
        self.render()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_render_mode(value: Any) -> FieldRenderMode:
        raw = str(value or "heatmap").strip().lower()
        if raw not in {"contour", "heatmap"}:
            raise ValueError(
                "scalar_field() render_mode must be 'contour' or 'heatmap'."
            )
        return raw  # type: ignore[return-value]

    @staticmethod
    def _coerce_preset(value: str | None, *, render_mode: FieldRenderMode) -> str | None:
        if value is None:
            return None
        raw = str(value).strip().lower()
        if raw == "temperature":
            if render_mode != "heatmap":
                raise ValueError("temperature preset requires render_mode='heatmap'.")
            return raw
        raise ValueError(f"Unknown scalar-field preset: {value!r}")

    @staticmethod
    def _default_show_colorbar(render_mode: FieldRenderMode) -> bool:
        return render_mode == "heatmap"

    @staticmethod
    def _default_filled(render_mode: FieldRenderMode) -> bool:
        return render_mode == "heatmap"

    @staticmethod
    def _coerce_optional_mapping(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return dict(value)

    @staticmethod
    def _coerce_optional_range(value: RangeLike | None, *, axis_name: str) -> tuple[float, float] | None:
        if value is None:
            return None
        lower = float(InputConvert(value[0], float))
        upper = float(InputConvert(value[1], float))
        if lower > upper:
            raise ValueError(f"{axis_name}_min must be <= {axis_name}_max")
        return (lower, upper)

    @staticmethod
    def _coerce_grid(value: tuple[int | str, int | str] | None) -> FieldGrid | None:
        if value is None:
            return None
        if len(value) != 2:
            raise ValueError("scalar_field() grid must have shape (nx, ny).")
        nx = int(InputConvert(value[0], int))
        ny = int(InputConvert(value[1], int))
        if nx <= 0 or ny <= 0:
            raise ValueError("scalar_field() grid values must be positive integers.")
        return (nx, ny)

    def _apply_creation_defaults(
        self,
        *,
        colorscale: Any | None,
        z_range: RangeLike | None,
        show_colorbar: bool | None,
        opacity: int | float | None,
        reversescale: bool | None,
        colorbar: Mapping[str, Any] | None,
        trace: Mapping[str, Any] | None,
        levels: int | None,
        filled: bool | None,
        show_labels: bool | None,
        line_color: str | None,
        line_width: int | float | None,
        smoothing: str | bool | None,
        connectgaps: bool | None,
    ) -> None:
        if self._preset == "temperature" and colorscale is None:
            colorscale = "hot"
        if self._preset == "temperature" and show_colorbar is None:
            show_colorbar = True
        if self._preset == "temperature" and colorbar is None:
            colorbar = {"title": {"text": "Temperature"}}

        if colorscale is not None:
            self._colorscale = colorscale
        self._z_range = self._coerce_optional_range(z_range, axis_name="z")
        if show_colorbar is not None:
            self._show_colorbar = bool(show_colorbar)
        if opacity is not None:
            self._opacity = self._coerce_opacity(opacity)
        if reversescale is not None:
            self._reversescale = bool(reversescale)
        self._colorbar = self._coerce_optional_mapping(colorbar)
        self._trace_overrides = self._coerce_optional_mapping(trace)
        if levels is not None:
            self._levels = int(InputConvert(levels, int))
        if filled is not None:
            self._filled = bool(filled)
        if show_labels is not None:
            self._show_labels = bool(show_labels)
        if line_color is not None:
            self._line_color = str(line_color)
        if line_width is not None:
            self._line_width = float(InputConvert(line_width, float))
        if smoothing is not None:
            self._smoothing = smoothing
        if connectgaps is not None:
            self._connectgaps = bool(connectgaps)

    @staticmethod
    def _coerce_opacity(value: int | float | None) -> float | None:
        if value is None:
            return None
        opacity = float(InputConvert(value, float))
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0")
        return opacity

    # ------------------------------------------------------------------
    # Trace/view ownership
    # ------------------------------------------------------------------

    def _iter_trace_handles(self) -> Sequence[go.Contour | go.Heatmap]:
        return tuple(
            handle.trace_handle
            for handle in self._handles.values()
            if handle.trace_handle is not None
        )

    def _reference_trace_handle(self) -> go.Contour | go.Heatmap | None:
        active = self._handles.get(self._smart_figure.views.current_id)
        if active is not None and active.trace_handle is not None:
            return active.trace_handle
        for trace_handle in self._iter_trace_handles():
            return trace_handle
        return None

    def _build_trace_style_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self._colorscale is not None:
            payload["colorscale"] = self._colorscale
        if self._z_range is not None:
            payload["zmin"] = self._z_range[0]
            payload["zmax"] = self._z_range[1]
        payload["showscale"] = self._show_colorbar
        if self._opacity is not None:
            payload["opacity"] = self._opacity
        if self._reversescale:
            payload["reversescale"] = True
        if self._colorbar:
            payload["colorbar"] = dict(self._colorbar)
        if self._connectgaps is not None:
            payload["connectgaps"] = self._connectgaps

        if self._render_mode == "contour":
            contours_payload: dict[str, Any] = {
                "coloring": "fill" if self._filled else "lines",
                "showlabels": self._show_labels,
            }
            if self._levels is not None:
                payload["ncontours"] = self._levels
            payload["contours"] = contours_payload
            line_payload: dict[str, Any] = {}
            if self._line_color is not None:
                line_payload["color"] = self._line_color
            if self._line_width is not None:
                line_payload["width"] = self._line_width
            if line_payload:
                payload["line"] = line_payload
        else:
            if self._smoothing is not None:
                payload["zsmooth"] = self._smoothing

        if self._trace_overrides:
            payload.update(dict(self._trace_overrides))
        return payload

    def _create_trace_handle(self, *, view_id: str, label: str) -> FieldPlotHandle:
        figure_widget = self._smart_figure.views[view_id].figure_widget
        trace: go.Contour | go.Heatmap
        if self._render_mode == "contour":
            trace = go.Contour(
                x=[],
                y=[],
                z=[],
                name=label,
                visible=self._visible,
                **self._build_trace_style_payload(),
            )
        else:
            trace = go.Heatmap(
                x=[],
                y=[],
                z=[],
                name=label,
                visible=self._visible,
                **self._build_trace_style_payload(),
            )
        figure_widget.add_trace(trace)
        trace_handle = figure_widget.data[-1]
        handle = FieldPlotHandle(plot_id=self.id, view_id=view_id, trace_handle=trace_handle)
        self._handles[view_id] = handle
        return handle

    def _apply_style_to_all_trace_handles(self) -> None:
        style_payload = self._build_trace_style_payload()
        for trace_handle in self._iter_trace_handles():
            trace_handle.update(**style_payload)
            trace_handle.visible = self._visible
            trace_handle.name = self.label

    def _set_visibility_for_target_view(self, target_view: str) -> None:
        handle = self._handles.get(target_view)
        if handle is not None and handle.trace_handle is not None:
            handle.trace_handle.visible = self._visible

    def _remove_trace_handle(self, *, view_id: str) -> None:
        handle = self._handles.get(view_id)
        if handle is None or handle.trace_handle is None:
            return
        figure_widget = self._smart_figure.views[view_id].figure_widget
        figure_widget.data = tuple(
            trace for trace in figure_widget.data if trace is not handle.trace_handle
        )
        handle.trace_handle = None

    # ------------------------------------------------------------------
    # Symbolic/numeric binding
    # ------------------------------------------------------------------

    def set_func(
        self,
        x_var: Symbol,
        y_var: Symbol,
        func: Expr,
        parameters: Sequence[Symbol] = (),
    ) -> None:
        parameters = list(parameters)
        self._numpified = numpify_cached(func, vars=[x_var, y_var, *parameters])
        self._x_var = x_var
        self._y_var = y_var
        self._func = sp.sympify(func)
        self._rebind_numeric_expressions()

    def set_numeric_function(
        self,
        x_var: Symbol,
        y_var: Symbol,
        numeric_function: NumericFunction,
        parameters: Sequence[Symbol] = (),
        *,
        symbolic_expression: Expr | None = None,
    ) -> None:
        self._numpified = numeric_function
        self._x_var = x_var
        self._y_var = y_var
        if numeric_function.symbolic is not None:
            self._func = sp.sympify(numeric_function.symbolic)
        elif symbolic_expression is not None:
            self._func = sp.sympify(symbolic_expression)
        elif isinstance(getattr(self, "_func", None), sp.Expr):
            self._func = self._func
        else:
            self._func = sp.Symbol("field_numeric")
        self._rebind_numeric_expressions()

    def _rebind_numeric_expressions(self) -> None:
        dynamic_symbols = tuple(
            sym for sym in self._numpified.all_vars if sym not in {self._x_var, self._y_var}
        )
        if dynamic_symbols:
            dynamic_expression = self._numpified.freeze(
                {sym: DYNAMIC_PARAMETER for sym in dynamic_symbols}
            )
            parameter_manager = self._smart_figure.parameters
            live_context = parameter_manager.parameter_context
            render_context = getattr(
                parameter_manager, "render_parameter_context", live_context
            )
            self._live_numeric_expression = dynamic_expression.set_parameter_context(
                live_context
            )
            self._render_numeric_expression = dynamic_expression.set_parameter_context(
                render_context
            )
        else:
            self._live_numeric_expression = self._numpified
            self._render_numeric_expression = self._numpified

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def figure(self) -> Figure:
        return self._smart_figure

    @property
    def render_mode(self) -> FieldRenderMode:
        return self._render_mode

    @property
    def preset(self) -> str | None:
        return self._preset

    @property
    def x_var(self) -> Symbol:
        return self._x_var

    @property
    def y_var(self) -> Symbol:
        return self._y_var

    @property
    def symbolic_expression(self) -> Expr:
        return self._func

    @property
    def numeric_expression(self) -> NumericFunction:
        return self._live_numeric_expression

    @property
    def parameters(self) -> tuple[Symbol, ...]:
        return tuple(sym for sym in self._numpified.all_vars if sym not in {self._x_var, self._y_var})

    @property
    def views(self) -> tuple[str, ...]:
        return tuple(sorted(self._view_ids))

    @property
    def label(self) -> str:
        return self._label

    @label.setter
    def label(self, value: str) -> None:
        self._label = str(value)
        for trace_handle in self._iter_trace_handles():
            trace_handle.name = value

    @property
    def color(self) -> str | None:
        if self._line_color:
            return self._line_color
        ref = self._reference_trace_handle()
        if ref is not None:
            trace_color = self._representative_colorscale_color(
                getattr(ref, "colorscale", None)
            )
            if trace_color:
                return trace_color
        return self._representative_colorscale_color(self._colorscale)

    @staticmethod
    def _representative_colorscale_color(colorscale: Any) -> str | None:
        if not colorscale or isinstance(colorscale, str):
            return None
        try:
            scale_items = list(colorscale)
        except TypeError:
            return None
        if not scale_items:
            return None
        middle = scale_items[len(scale_items) // 2]
        if isinstance(middle, (tuple, list)) and len(middle) >= 2:
            return str(middle[1])
        return None

    @property
    def opacity(self) -> float | None:
        return self._opacity

    @opacity.setter
    def opacity(self, value: int | float | None) -> None:
        self._opacity = self._coerce_opacity(value)
        self._apply_style_to_all_trace_handles()

    @property
    def colorscale(self) -> Any | None:
        return self._colorscale

    @property
    def z_range(self) -> tuple[float, float] | None:
        return self._z_range

    @property
    def show_colorbar(self) -> bool:
        return self._show_colorbar

    @property
    def reversescale(self) -> bool:
        return self._reversescale

    @property
    def colorbar(self) -> dict[str, Any] | None:
        return None if self._colorbar is None else dict(self._colorbar)

    @property
    def levels(self) -> int | None:
        return self._levels

    @property
    def filled(self) -> bool:
        return self._filled

    @property
    def show_labels(self) -> bool:
        return self._show_labels

    @property
    def line_color(self) -> str | None:
        return self._line_color

    @property
    def line_width(self) -> float | None:
        return self._line_width

    @property
    def smoothing(self) -> str | bool | None:
        return self._smoothing

    @property
    def connectgaps(self) -> bool | None:
        return self._connectgaps

    @property
    def x_domain(self) -> tuple[float, float] | None:
        return self._x_domain

    @x_domain.setter
    def x_domain(self, value: RangeLike | None) -> None:
        if value is None or _is_figure_default(value):
            self._x_domain = None
        else:
            self._x_domain = self._coerce_optional_range(value, axis_name="x")
        self.render()

    @property
    def y_domain(self) -> tuple[float, float] | None:
        return self._y_domain

    @y_domain.setter
    def y_domain(self, value: RangeLike | None) -> None:
        if value is None or _is_figure_default(value):
            self._y_domain = None
        else:
            self._y_domain = self._coerce_optional_range(value, axis_name="y")
        self.render()

    @property
    def grid(self) -> FieldGrid | None:
        return self._grid

    @grid.setter
    def grid(self, value: tuple[int | str, int | str] | None) -> None:
        self._grid = self._coerce_grid(value)
        self.render()

    @property
    def visible(self) -> VisibleSpec:
        return self._visible

    @visible.setter
    def visible(self, value: VisibleSpec) -> None:
        self._visible = value
        for view_id in self._view_ids:
            self._set_visibility_for_target_view(view_id)
        if value is True:
            self.render()

    @property
    def x_data(self) -> np.ndarray | None:
        if self._x_axis_values is None:
            return None
        values = self._x_axis_values.copy()
        values.flags.writeable = False
        return values

    @property
    def y_data(self) -> np.ndarray | None:
        if self._y_axis_values is None:
            return None
        values = self._y_axis_values.copy()
        values.flags.writeable = False
        return values

    @property
    def z_data(self) -> np.ndarray | None:
        if self._z_data is None:
            return None
        values = self._z_data.copy()
        values.flags.writeable = False
        return values

    # ------------------------------------------------------------------
    # View membership and snapshots
    # ------------------------------------------------------------------

    def add_to_view(self, view_id: str) -> None:
        if view_id in self._view_ids:
            return
        self._view_ids.add(view_id)
        self._create_trace_handle(view_id=view_id, label=self.label)
        if view_id == self._smart_figure.views.current_id and self._visible is True:
            self.render(view_id=view_id)

    def remove_from_view(self, view_id: str) -> None:
        if view_id not in self._view_ids:
            return
        self._view_ids.remove(view_id)
        self._remove_trace_handle(view_id=view_id)
        self._handles.pop(view_id, None)

    def add_views(self, views: str | Sequence[str]) -> None:
        if isinstance(views, str):
            self.add_to_view(views)
            return
        for view_id in views:
            self.add_to_view(view_id)

    def remove_views(self, views: str | Sequence[str]) -> None:
        if isinstance(views, str):
            self.remove_from_view(views)
            return
        for view_id in views:
            self.remove_from_view(view_id)

    def snapshot(self, *, id: str = "") -> FieldPlotSnapshot:
        return FieldPlotSnapshot(
            id=id,
            render_mode=self.render_mode,
            preset=self.preset,
            x_var=self.x_var,
            y_var=self.y_var,
            func=self.symbolic_expression,
            parameters=tuple(self.parameters),
            label=self.label,
            visible=self.visible,
            x_domain=self.x_domain,
            y_domain=self.y_domain,
            grid=self.grid,
            colorscale=self.colorscale,
            z_range=self.z_range,
            show_colorbar=self.show_colorbar,
            opacity=self.opacity,
            reversescale=self.reversescale,
            colorbar=self.colorbar,
            trace=(None if self._trace_overrides is None else dict(self._trace_overrides)),
            views=self.views,
            levels=self.levels,
            filled=self.filled,
            show_labels=self.show_labels,
            line_color=self.line_color,
            line_width=self.line_width,
            smoothing=self.smoothing,
            connectgaps=self.connectgaps,
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_grid_values(
        raw_values: Any,
        *,
        x_values: np.ndarray,
        y_values: np.ndarray,
    ) -> np.ndarray:
        target_shape = (y_values.shape[0], x_values.shape[0])
        values = np.asarray(raw_values, dtype=float)
        if values.ndim == 0:
            return np.full(target_shape, float(values), dtype=float)
        if values.shape == target_shape:
            return values.astype(float, copy=False)
        if values.shape == (target_shape[1], target_shape[0]):
            return values.T.astype(float, copy=False)
        if values.size == target_shape[0] * target_shape[1]:
            return np.ravel(values).astype(float, copy=False).reshape(target_shape)
        try:
            return np.broadcast_to(values, target_shape).astype(float, copy=False)
        except ValueError as exc:
            raise ValueError(
                "Scalar field expression must evaluate to a scalar or an array "
                f"broadcastable to grid shape {target_shape}."
            ) from exc

    def render(
        self,
        view_id: str | None = None,
        *,
        use_batch_update: bool = True,
        refresh_parameter_snapshot: bool = True,
    ) -> None:
        target_view = view_id or self._smart_figure.views.current_id
        self._set_visibility_for_target_view(target_view)
        if target_view not in self._view_ids:
            return
        if self._suspend_render or self._visible is not True:
            return

        fig = self._smart_figure
        if refresh_parameter_snapshot:
            refresh_context = getattr(fig.parameters, "refresh_render_parameter_context", None)
            if callable(refresh_context):
                refresh_context()

        if target_view != fig.views.current_id:
            fig.views[target_view].is_stale = True
            return

        view = fig.views[target_view]
        x_viewport = view.current_x_range or view.x_range
        y_viewport = view.current_y_range or view.y_range
        x_domain = self.x_domain or x_viewport
        y_domain = self.y_domain or y_viewport
        nx, ny = self.grid or self.DEFAULT_GRID

        x_values = np.linspace(float(x_domain[0]), float(x_domain[1]), num=int(nx))
        y_values = np.linspace(float(y_domain[0]), float(y_domain[1]), num=int(ny))
        X, Y = np.meshgrid(x_values, y_values)
        z_values = self._coerce_grid_values(
            self._render_numeric_expression(X, Y),
            x_values=x_values,
            y_values=y_values,
        )

        self._x_axis_values = x_values.copy()
        self._y_axis_values = y_values.copy()
        self._z_data = z_values.copy()

        target_handle = self._handles[target_view].trace_handle
        if target_handle is None:
            return

        def _apply_trace_update() -> None:
            target_handle.x = x_values
            target_handle.y = y_values
            target_handle.z = z_values

        if use_batch_update:
            with fig.views[target_view].figure_widget.batch_update():
                _apply_trace_update()
        else:
            _apply_trace_update()

    # ------------------------------------------------------------------
    # In-place updates
    # ------------------------------------------------------------------

    def _apply_style_updates(self, style_kwargs: dict[str, Any]) -> None:
        if "colorscale" in style_kwargs:
            self._colorscale = style_kwargs.get("colorscale")
        if "z_range" in style_kwargs:
            self._z_range = self._coerce_optional_range(style_kwargs.get("z_range"), axis_name="z")
        if "show_colorbar" in style_kwargs:
            self._show_colorbar = bool(style_kwargs.get("show_colorbar"))
        if "opacity" in style_kwargs:
            self._opacity = self._coerce_opacity(style_kwargs.get("opacity"))
        if "reversescale" in style_kwargs:
            self._reversescale = bool(style_kwargs.get("reversescale"))
        if "colorbar" in style_kwargs:
            self._colorbar = self._coerce_optional_mapping(style_kwargs.get("colorbar"))
        if "trace" in style_kwargs:
            self._trace_overrides = self._coerce_optional_mapping(style_kwargs.get("trace"))
        if "levels" in style_kwargs:
            levels = style_kwargs.get("levels")
            self._levels = None if levels is None else int(InputConvert(levels, int))
        if "filled" in style_kwargs:
            self._filled = bool(style_kwargs.get("filled"))
        if "show_labels" in style_kwargs:
            self._show_labels = bool(style_kwargs.get("show_labels"))
        if "line_color" in style_kwargs:
            self._line_color = style_kwargs.get("line_color")
        if "line_width" in style_kwargs:
            width = style_kwargs.get("line_width")
            self._line_width = None if width is None else float(InputConvert(width, float))
        if "smoothing" in style_kwargs:
            self._smoothing = style_kwargs.get("smoothing")
        if "connectgaps" in style_kwargs:
            connectgaps = style_kwargs.get("connectgaps")
            self._connectgaps = None if connectgaps is None else bool(connectgaps)
        self._apply_style_to_all_trace_handles()

    def update(self, **kwargs: Any) -> None:
        render_requested = False
        previous_suspend = self._suspend_render
        self._suspend_render = True
        try:
            if "label" in kwargs:
                self.label = kwargs["label"]

            if "visible" in kwargs:
                self.visible = kwargs["visible"]
                render_requested = render_requested or kwargs["visible"] is True

            if "x_domain" in kwargs:
                val = kwargs["x_domain"]
                if val is None:
                    pass
                elif _is_figure_default(val):
                    self.x_domain = None
                    render_requested = True
                else:
                    self.x_domain = val
                    render_requested = True

            if "y_domain" in kwargs:
                val = kwargs["y_domain"]
                if val is None:
                    pass
                elif _is_figure_default(val):
                    self.y_domain = None
                    render_requested = True
                else:
                    self.y_domain = val
                    render_requested = True

            if "grid" in kwargs:
                val = kwargs["grid"]
                if val is None:
                    pass
                else:
                    self.grid = val
                    render_requested = True

            if "view" in kwargs:
                requested = kwargs["view"]
                if requested is not None:
                    render_requested = True
                    requested_views = {requested} if isinstance(requested, str) else set(requested)
                    for view_id in tuple(self._view_ids):
                        if view_id not in requested_views:
                            self.remove_from_view(view_id)
                    for view_id in requested_views:
                        self.add_to_view(view_id)

            raw_style_kwargs: dict[str, Any] = {}
            for key in (
                "colorscale",
                "z_range",
                "show_colorbar",
                "showscale",
                "opacity",
                "alpha",
                "reversescale",
                "colorbar",
                "trace",
                "levels",
                "filled",
                "show_labels",
                "line_color",
                "line_width",
                "smoothing",
                "zsmooth",
                "connectgaps",
            ):
                if key in kwargs:
                    raw_style_kwargs[key] = kwargs[key]
            if raw_style_kwargs:
                style_kwargs = validate_field_style_kwargs(
                    raw_style_kwargs,
                    caller="ScalarFieldPlot.update()",
                )
                self._apply_style_updates(style_kwargs)

            if any(k in kwargs for k in ("x_var", "y_var", "func", "parameters", "numeric_function")):
                render_requested = True
                x_var = kwargs.get("x_var", self.x_var)
                y_var = kwargs.get("y_var", self.y_var)
                func = kwargs.get("func", self.symbolic_expression)
                parameters = kwargs.get("parameters", self.parameters)
                numeric_fn = kwargs.get("numeric_function")
                if numeric_fn is not None:
                    self.set_numeric_function(
                        x_var,
                        y_var,
                        numeric_fn,
                        parameters=parameters,
                        symbolic_expression=func,
                    )
                else:
                    self.set_func(x_var, y_var, func, parameters)
        finally:
            self._suspend_render = previous_suspend

        if render_requested:
            self.render()


# ----------------------------------------------------------------------
# Figure-facing creation/update helpers
# ----------------------------------------------------------------------


def _normalize_axis_domain(
    axis_spec: Any,
    *,
    axis_name: str,
    domain: RangeLike | None,
    caller: str,
) -> tuple[Any, RangeLike | None]:
    if isinstance(axis_spec, tuple):
        if len(axis_spec) != 3:
            raise ValueError(
                f"{caller} {axis_name} range tuple must have shape ({axis_name}, min, max)."
            )
        if domain is not None:
            raise ValueError(
                f"{caller} cannot combine a {axis_name} range tuple with {axis_name}_domain=."
            )
        return axis_spec[0], (axis_spec[1], axis_spec[2])
    return axis_spec, domain



def create_or_update_scalar_field_plot(
    figure: Figure,
    func: Any,
    x: Any,
    y: Any,
    *,
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: VisibleSpec = True,
    x_domain: RangeLike | None = None,
    y_domain: RangeLike | None = None,
    grid: tuple[int | str, int | str] | None = None,
    render_mode: FieldRenderMode = "heatmap",
    preset: str | None = None,
    colorscale: Any | None = None,
    z_range: RangeLike | None = None,
    show_colorbar: bool | None = None,
    opacity: int | float | None = None,
    alpha: int | float | None = None,
    reversescale: bool | None = None,
    colorbar: Mapping[str, Any] | None = None,
    trace: Mapping[str, Any] | None = None,
    levels: int | None = None,
    filled: bool | None = None,
    show_labels: bool | None = None,
    line_color: str | None = None,
    line_width: int | float | None = None,
    smoothing: str | bool | None = None,
    zsmooth: str | bool | None = None,
    connectgaps: bool | None = None,
    view: str | Sequence[str] | None = None,
    vars: Any | None = None,
    caller: str = "scalar_field()",
) -> ScalarFieldPlot:
    id = resolve_plot_id(figure.plots, id)
    x_var_spec, x_domain = _normalize_axis_domain(
        x, axis_name="x", domain=x_domain, caller=caller
    )
    y_var_spec, y_domain = _normalize_axis_domain(
        y, axis_name="y", domain=y_domain, caller=caller
    )

    x_var, y_var, symbolic_expr, numeric_fn, inferred_parameters = normalize_field_inputs(
        func,
        x_var_spec,
        y_var_spec,
        vars=vars,
        id_hint=id,
    )

    raw_style_kwargs: dict[str, Any] = {}
    for key, value in (
        ("colorscale", colorscale),
        ("z_range", z_range),
        ("show_colorbar", show_colorbar),
        ("opacity", opacity),
        ("alpha", alpha),
        ("reversescale", reversescale),
        ("colorbar", colorbar),
        ("trace", trace),
        ("levels", levels),
        ("filled", filled),
        ("show_labels", show_labels),
        ("line_color", line_color),
        ("line_width", line_width),
        ("smoothing", smoothing),
        ("zsmooth", zsmooth),
        ("connectgaps", connectgaps),
    ):
        if value is not None:
            raw_style_kwargs[key] = value
    style_kwargs = validate_field_style_kwargs(raw_style_kwargs, caller=caller)
    render_mode = ScalarFieldPlot._coerce_render_mode(render_mode)
    preset = ScalarFieldPlot._coerce_preset(preset, render_mode=render_mode)

    if parameters is None:
        requested_parameter_keys: ParameterKeyOrKeys = tuple(inferred_parameters)
        plot_parameters = tuple(inferred_parameters)
    else:
        requested_parameter_keys = parameters
        plot_parameters = expand_parameter_keys_to_symbols(
            parameters,
            inferred_parameters,
            role="scalar-field parameters",
        )

    if requested_parameter_keys:
        figure.parameter(requested_parameter_keys)

    if figure._sync_sidebar_visibility():
        figure._request_active_view_reflow("sidebar_visibility")

    existing = figure.plots.get(id)
    if existing is not None and not isinstance(existing, ScalarFieldPlot):
        remove_plot_from_figure(figure, id)
        existing = None
    if existing is not None and (
        existing.render_mode != render_mode or existing.preset != preset
    ):
        remove_plot_from_figure(figure, id)
        existing = None

    if existing is not None:
        update_kwargs: dict[str, Any] = {
            "x_var": x_var,
            "y_var": y_var,
            "func": symbolic_expr,
            "parameters": plot_parameters,
            "visible": visible,
            "x_domain": x_domain,
            "y_domain": y_domain,
            "grid": grid,
            "view": view,
        }
        for key in (
            "colorscale",
            "z_range",
            "show_colorbar",
            "opacity",
            "reversescale",
            "colorbar",
            "trace",
            "levels",
            "filled",
            "show_labels",
            "line_color",
            "line_width",
            "smoothing",
            "connectgaps",
        ):
            if key in style_kwargs:
                update_kwargs[key] = style_kwargs[key]
        if numeric_fn is not None:
            update_kwargs["numeric_function"] = numeric_fn
        if label is not None:
            update_kwargs["label"] = label
        existing.update(**update_kwargs)
        plot = existing
        figure._legend.on_plot_updated(plot)
        if figure._sync_sidebar_visibility():
            figure._request_active_view_reflow("sidebar_visibility")
        return plot

    view_ids = normalize_view_ids(view, default_view_id=figure.views.current_id)
    plot = ScalarFieldPlot(
        x_var=x_var,
        y_var=y_var,
        func=symbolic_expr,
        smart_figure=figure,
        parameters=plot_parameters,
        x_domain=x_domain,
        y_domain=y_domain,
        grid=grid,
        label=(id if label is None else label),
        visible=visible,
        render_mode=render_mode,
        preset=preset,
        colorscale=style_kwargs.get("colorscale"),
        z_range=style_kwargs.get("z_range"),
        show_colorbar=style_kwargs.get("show_colorbar"),
        opacity=style_kwargs.get("opacity"),
        reversescale=style_kwargs.get("reversescale"),
        colorbar=style_kwargs.get("colorbar"),
        trace=style_kwargs.get("trace"),
        levels=style_kwargs.get("levels"),
        filled=style_kwargs.get("filled"),
        show_labels=style_kwargs.get("show_labels"),
        line_color=style_kwargs.get("line_color"),
        line_width=style_kwargs.get("line_width"),
        smoothing=style_kwargs.get("smoothing"),
        connectgaps=style_kwargs.get("connectgaps"),
        plot_id=id,
        view_ids=view_ids,
        numeric_function=numeric_fn,
    )
    figure.plots[id] = plot
    figure._legend.on_plot_added(plot)
    if figure._sync_sidebar_visibility():
        figure._request_active_view_reflow("sidebar_visibility")
    return plot


# ----------------------------------------------------------------------
# Figure method shims (attached in Figure.py to preserve coordinator size)
# ----------------------------------------------------------------------


def scalar_field_method(
    self: Figure,
    func: Any,
    x: Any,
    y: Any,
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: VisibleSpec = True,
    x_domain: RangeLike | None = None,
    y_domain: RangeLike | None = None,
    grid: tuple[int | str, int | str] | None = None,
    render_mode: FieldRenderMode = "heatmap",
    preset: str | None = None,
    colorscale: Any | None = None,
    z_range: RangeLike | None = None,
    show_colorbar: bool | None = None,
    opacity: int | float | None = None,
    alpha: int | float | None = None,
    reversescale: bool | None = None,
    colorbar: Mapping[str, Any] | None = None,
    trace: Mapping[str, Any] | None = None,
    levels: int | None = None,
    filled: bool | None = None,
    show_labels: bool | None = None,
    line_color: str | None = None,
    line_width: int | float | None = None,
    smoothing: str | bool | None = None,
    zsmooth: str | bool | None = None,
    connectgaps: bool | None = None,
    view: str | Sequence[str] | None = None,
    vars: Any | None = None,
) -> ScalarFieldPlot:
    return create_or_update_scalar_field_plot(
        self,
        func,
        x,
        y,
        parameters=parameters,
        id=id,
        label=label,
        visible=visible,
        x_domain=x_domain,
        y_domain=y_domain,
        grid=grid,
        render_mode=render_mode,
        preset=preset,
        colorscale=colorscale,
        z_range=z_range,
        show_colorbar=show_colorbar,
        opacity=opacity,
        alpha=alpha,
        reversescale=reversescale,
        colorbar=colorbar,
        trace=trace,
        levels=levels,
        filled=filled,
        show_labels=show_labels,
        line_color=line_color,
        line_width=line_width,
        smoothing=smoothing,
        zsmooth=zsmooth,
        connectgaps=connectgaps,
        view=view,
        vars=vars,
        caller="scalar_field()",
    )



def contour_method(self: Figure, func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    kwargs.setdefault("render_mode", "contour")
    kwargs.setdefault("filled", False)
    return create_or_update_scalar_field_plot(self, func, x, y, caller="contour()", **kwargs)



def density_method(self: Figure, func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    kwargs.setdefault("render_mode", "heatmap")
    return create_or_update_scalar_field_plot(self, func, x, y, caller="density()", **kwargs)



def temperature_method(self: Figure, func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    kwargs.setdefault("render_mode", "heatmap")
    kwargs.setdefault("preset", "temperature")
    return create_or_update_scalar_field_plot(self, func, x, y, caller="temperature()", **kwargs)


__all__ = [
    "FieldGrid",
    "FieldPlotHandle",
    "FieldRenderMode",
    "ScalarFieldPlot",
    "create_or_update_scalar_field_plot",
    "field_style_option_docs",
    "contour_method",
    "density_method",
    "scalar_field_method",
    "temperature_method",
]
