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

if TYPE_CHECKING:
    from .Figure import Figure
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
        symbols: Symbol | Sequence[Symbol],
        *,
        control: str | None = None,
        **kwargs: Any,
    ) -> ParamRef | dict[Symbol, ParamRef]:
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


def render(reason: str = "manual", trigger: ParamEvent | None = None) -> None:
    _require_current_figure().render(reason=reason, trigger=trigger)


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


def set_y_range(value: tuple[int | float | str, int | float | str]) -> None:
    _require_current_figure().y_range = value


def get_y_range() -> tuple[float, float]:
    return _require_current_figure().y_range


def set_sampling_points(value: int | str | object | None) -> None:
    _require_current_figure().sampling_points = value


def get_sampling_points() -> int | None:
    return _require_current_figure().sampling_points


def plot_style_options() -> dict[str, str]:
    """Return help text for supported plot-style keywords.

    The mapping is generated from the structured plot-style metadata used by
    :class:`Figure`, so aliases and accepted values stay synchronized with the
    actual plotting contract.
    """
    from .Figure import Figure

    return Figure.plot_style_options()


def parameter(
    symbols: Symbol | Sequence[Symbol],
    *,
    control: str | None = None,
    **kwargs: Any,
) -> ParamRef | dict[Symbol, ParamRef]:
    fig = _require_current_figure()
    return fig.parameters.parameter(symbols, control=control, **kwargs)


def plot(
    func: Any,
    var: Any,
    parameters: Sequence[Symbol] | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: bool = True,
    x_domain: tuple[int | float | str, int | float | str] | None = None,
    sampling_points: int | str | None = None,
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
    )


__all__ = [
    "get_sampling_points",
    "get_title",
    "get_x_range",
    "get_y_range",
    "info",
    "parameter",
    "parameters",
    "plot",
    "plots",
    "plot_style_options",
    "render",
    "set_sampling_points",
    "set_title",
    "set_x_range",
    "set_y_range",
]
