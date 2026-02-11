from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, TYPE_CHECKING

from sympy.core.symbol import Symbol

from .ParameterSnapshot import ParameterSnapshot

if TYPE_CHECKING:
    import numpy as np
    from .SmartFigure import SmartPlot


def _coerce_bound_values(
    source: ParameterSnapshot | Mapping[Symbol, Any],
    parameters: tuple[Symbol, ...],
    *,
    plot_id: str | None = None,
) -> tuple[Any, ...]:
    if isinstance(source, ParameterSnapshot):
        value_map = source.values_only()
    elif isinstance(source, Mapping):
        value_map = dict(source)
    else:
        raise TypeError("bind(...) expects a ParameterSnapshot or dict[Symbol, Any].")

    non_symbol_keys = [key for key in value_map if not isinstance(key, Symbol)]
    if non_symbol_keys:
        raise TypeError(f"bind(...) requires Symbol keys only; got: {non_symbol_keys!r}")

    missing = [symbol for symbol in parameters if symbol not in value_map]
    if missing:
        missing_str = ", ".join(str(symbol) for symbol in missing)
        if plot_id is not None:
            raise KeyError(f"Missing bound values for plot '{plot_id}': [{missing_str}]")
        raise KeyError(f"Missing bound values: [{missing_str}]")

    return tuple(value_map[symbol] for symbol in parameters)


@dataclass(frozen=True)
class DeadUnboundNumericExpression:
    core: Callable[..., Any]
    parameters: tuple[Symbol, ...]

    def bind(self, snapshot_or_dict: ParameterSnapshot | Mapping[Symbol, Any]) -> "DeadBoundNumericExpression":
        bound_values = _coerce_bound_values(snapshot_or_dict, self.parameters)
        return DeadBoundNumericExpression(core=self.core, parameters=self.parameters, bound_values=bound_values)

    def __call__(self, x: "np.ndarray") -> "np.ndarray":
        raise TypeError("This numeric expression is unbound; call .bind(...) before evaluation.")


@dataclass(frozen=True)
class DeadBoundNumericExpression:
    core: Callable[..., Any]
    parameters: tuple[Symbol, ...]
    bound_values: tuple[Any, ...]

    def __call__(self, x: "np.ndarray") -> "np.ndarray":
        return self.core(x, *self.bound_values)

    def unbind(self) -> DeadUnboundNumericExpression:
        return DeadUnboundNumericExpression(core=self.core, parameters=self.parameters)

    def bind(self, snapshot_or_dict: ParameterSnapshot | Mapping[Symbol, Any]) -> "DeadBoundNumericExpression":
        return self.unbind().bind(snapshot_or_dict)


@dataclass(frozen=True)
class LiveNumericExpression:
    plot: "SmartPlot"

    def __call__(self, x: "np.ndarray") -> "np.ndarray":
        return self.plot._eval_numeric_live(x)

    def bind(self, snapshot_or_dict: ParameterSnapshot | Mapping[Symbol, Any]) -> DeadBoundNumericExpression:
        bound_values = _coerce_bound_values(
            snapshot_or_dict,
            self.plot.parameters,
            plot_id=getattr(self.plot, "id", None),
        )
        return DeadBoundNumericExpression(
            core=self.plot._core,
            parameters=self.plot.parameters,
            bound_values=bound_values,
        )

    def unbind(self) -> DeadUnboundNumericExpression:
        return DeadUnboundNumericExpression(core=self.plot._core, parameters=self.plot.parameters)
