"""Module-level convenience API for current-figure workflows.

The helpers in this module do not own plotting state. They resolve the
*current figure* from :mod:`gu_toolkit.figure_context` and delegate to that
figure's public API.

Two context patterns matter:

- ``with fig:`` makes ``fig`` the current target while leaving the current view
  unchanged.
- ``with fig.views["detail"]:`` makes ``fig`` current *and* temporarily makes
  ``"detail"`` the active view, so module-level helpers route into that view.

Examples
--------
>>> import sympy as sp
>>> from gu_toolkit import Figure, parameter, plot, info
>>> x, a = sp.symbols("x a")
>>> fig = Figure()  # doctest: +SKIP
>>> fig.views.add("detail", x_range=(-1, 1), y_range=(-1, 1))  # doctest: +SKIP
>>> with fig.views["detail"]:  # doctest: +SKIP
...     parameter(a, min=-1, max=1)  # doctest: +SKIP
...     plot(a * sp.sin(x), x, id="wave")  # doctest: +SKIP
...     info("Zoomed view")  # doctest: +SKIP

Notes
-----
``plot(...)`` will auto-create a new figure when no current figure exists.
Other helpers such as ``parameter(...)``, ``info(...)``, and range/title
setters require an active figure context.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from IPython.display import display
from sympy.core.symbol import Symbol

from .figure_context import _current_figure, _require_current_figure
from .ParameterSnapshot import ParameterSnapshot, ParameterValueSnapshot
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .parameter_keys import ParameterKeyOrKeys

if TYPE_CHECKING:
    from .Figure import Figure
    from .figure_field import ScalarFieldPlot
    from .figure_plot import Plot
    from .figure_plot_normalization import PlotVarsSpec


class _CurrentParametersProxy(Mapping):
    """Module-level proxy to the current figure's ParameterManager."""

    def _fig(self) -> Figure:
        return _require_current_figure()

    def _mgr(self) -> Any:
        return self._fig().parameters

    def __getitem__(self, key: Hashable) -> ParamRef:
        return self._mgr()[key]

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self._mgr())

    def __len__(self) -> int:
        return len(self._mgr())

    def __contains__(self, key: object) -> bool:
        return key in self._mgr()

    def __setitem__(self, key: Hashable, value: Any) -> None:
        self[key].value = value

    def parameter(
        self,
        symbols: ParameterKeyOrKeys,
        *,
        control: str | None = None,
        **kwargs: Any,
    ) -> ParamRef | dict[str, ParamRef]:
        return self._mgr().parameter(symbols, control=control, **kwargs)

    def snapshot(
        self, *, full: bool = False
    ) -> ParameterValueSnapshot | ParameterSnapshot:
        return self._mgr().snapshot(full=full)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mgr(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(self._mgr(), name, value)


class _CurrentPlotsProxy(Mapping):
    """Module-level proxy to the current figure's plots mapping."""

    def _fig(self) -> Figure:
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
plots = _CurrentPlotsProxy()


def set_title(text: str) -> None:
    _require_current_figure().title = text


def get_title() -> str:
    return _require_current_figure().title


def render(
    reason: str = "manual",
    trigger: ParamEvent | None = None,
    *,
    force: bool = False,
) -> None:
    """Queue or synchronously execute a render on the current figure."""
    _require_current_figure().render(reason=reason, trigger=trigger, force=force)


def sound_generation_enabled(enabled: bool | None = None) -> bool:
    """Query or set sound generation on the current figure."""
    return _require_current_figure().sound_generation_enabled(enabled)


def info(
    spec: str
    | Callable[[Figure, Any], str]
    | Sequence[str | Callable[[Figure, Any], str]],
    id: Hashable | None = None,
    *,
    view: str | None = None,
) -> None:
    """Create or replace a simple info card on the current figure.

    When ``view`` is provided, the card is only visible while that view is the
    active view on the current figure.
    """
    _require_current_figure().info(spec=spec, id=id, view=view)


def set_x_range(value: tuple[int | float | str, int | float | str]) -> None:
    _require_current_figure().x_range = value


def get_x_range() -> tuple[float, float]:
    return _require_current_figure().x_range


def set_default_x_range(value: tuple[int | float | str, int | float | str]) -> None:
    _require_current_figure().default_x_range = value


def get_default_x_range() -> tuple[float, float]:
    return _require_current_figure().default_x_range


def set_y_range(value: tuple[int | float | str, int | float | str]) -> None:
    _require_current_figure().y_range = value


def get_y_range() -> tuple[float, float]:
    return _require_current_figure().y_range


def set_default_y_range(value: tuple[int | float | str, int | float | str]) -> None:
    _require_current_figure().default_y_range = value


def get_default_y_range() -> tuple[float, float]:
    return _require_current_figure().default_y_range


def set_samples(value: int | str | object | None) -> None:
    _require_current_figure().samples = value


def get_samples() -> int | None:
    return _require_current_figure().samples


def set_default_samples(value: int | str | object | None) -> None:
    _require_current_figure().default_samples = value


def get_default_samples() -> int | None:
    return _require_current_figure().default_samples


def set_sampling_points(value: int | str | object | None) -> None:
    set_samples(value)


def get_sampling_points() -> int | None:
    return get_samples()


def plot_style_options() -> dict[str, str]:
    """Return help text for supported plot-style keywords.

    The mapping is generated from the structured plot-style metadata used by
    :class:`Figure`, so aliases and accepted values stay synchronized with the
    actual plotting contract.
    """
    from .Figure import Figure

    return Figure.plot_style_options()


def field_style_options() -> dict[str, str]:
    """Return help text for supported scalar-field style keywords."""
    from .Figure import Figure

    return Figure.field_style_options()


def parameter(
    symbols: ParameterKeyOrKeys,
    *,
    control: str | None = None,
    **kwargs: Any,
) -> ParamRef | dict[str, ParamRef]:
    fig = _require_current_figure()
    return fig.parameters.parameter(symbols, control=control, **kwargs)


def plot(
    func: Any,
    var: Any,
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: bool = True,
    x_domain: tuple[int | float | str, int | float | str] | None = None,
    sampling_points: int | str | object | None = None,
    color: str | None = None,
    thickness: int | float | None = None,
    width: int | float | None = None,
    dash: str | None = None,
    opacity: int | float | None = None,
    alpha: int | float | None = None,
    line: Mapping[str, Any] | None = None,
    trace: Mapping[str, Any] | None = None,
    view: str | Sequence[str] | None = None,
    vars: PlotVarsSpec | None = None,
    samples: int | str | object | None = None,
) -> Plot:
    """Plot on the current figure, auto-creating one when needed."""
    fig = _current_figure()
    if fig is None:
        from .Figure import Figure

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
        samples=samples,
    )


def parametric_plot(
    funcs: Sequence[Any],
    parameter_range: tuple[Any, Any, Any],
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: bool = True,
    sampling_points: int | str | object | None = None,
    color: str | None = None,
    thickness: int | float | None = None,
    width: int | float | None = None,
    dash: str | None = None,
    opacity: int | float | None = None,
    alpha: int | float | None = None,
    line: Mapping[str, Any] | None = None,
    trace: Mapping[str, Any] | None = None,
    view: str | Sequence[str] | None = None,
    vars: PlotVarsSpec | None = None,
    samples: int | str | object | None = None,
) -> Plot:
    """Plot a parametric curve on the current figure.

    The curve is defined by ``(x(t), y(t))`` sampled over
    ``parameter_range == (t, min, max)``. When no current figure exists, this
    helper creates and displays one, mirroring :func:`plot`.
    """
    fig = _current_figure()
    if fig is None:
        from .Figure import Figure

        fig = Figure()
        display(fig)
    return fig.parametric_plot(
        funcs,
        parameter_range,
        parameters=parameters,
        id=id,
        label=label,
        visible=visible,
        sampling_points=sampling_points,
        color=color,
        thickness=thickness,
        width=width,
        dash=dash,
        opacity=opacity,
        alpha=alpha,
        line=line,
        trace=trace,
        view=view,
        vars=vars,
        samples=samples,
    )


def scalar_field(
    func: Any,
    x: Any,
    y: Any,
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: bool = True,
    x_domain: tuple[int | float | str, int | float | str] | None = None,
    y_domain: tuple[int | float | str, int | float | str] | None = None,
    grid: tuple[int | str, int | str] | None = None,
    render_mode: str = "heatmap",
    preset: str | None = None,
    colorscale: Any | None = None,
    z_range: tuple[int | float | str, int | float | str] | None = None,
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
    """Plot a scalar field on the current figure, auto-creating one when needed."""
    fig = _current_figure()
    if fig is None:
        from .Figure import Figure

        fig = Figure()
        display(fig)
    return fig.scalar_field(
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
    )


def contour(func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    """Plot contour lines or filled contours on the current figure."""
    return scalar_field(func, x, y, render_mode="contour", **kwargs)


def density(func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    """Plot a scalar field as a heatmap on the current figure."""
    return scalar_field(func, x, y, render_mode="heatmap", **kwargs)


def temperature(func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    """Plot a scalar field with thermal heatmap defaults on the current figure."""
    kwargs.setdefault("preset", "temperature")
    return scalar_field(func, x, y, render_mode="heatmap", **kwargs)


__all__ = [
    "get_default_samples",
    "get_default_x_range",
    "get_default_y_range",
    "get_samples",
    "get_sampling_points",
    "get_title",
    "get_x_range",
    "get_y_range",
    "info",
    "parameter",
    "parameters",
    "parametric_plot",
    "plot",
    "scalar_field",
    "contour",
    "density",
    "temperature",
    "plots",
    "plot_style_options",
    "field_style_options",
    "sound_generation_enabled",
    "render",
    "set_default_samples",
    "set_default_x_range",
    "set_default_y_range",
    "set_samples",
    "set_sampling_points",
    "set_title",
    "set_x_range",
    "set_y_range",
]
