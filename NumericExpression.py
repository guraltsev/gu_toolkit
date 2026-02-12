"""Live symbolic/numeric expression views backed by a Plot manager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import sympy as sp

from .numpify import DYNAMIC_PARAMETER, NumpifiedFunction

if TYPE_CHECKING:
    import numpy as np
    from .figure_plot import Plot


@dataclass(frozen=True)
class LivePlotSymbolicExpression:
    """Live symbolic expression view for a plot."""

    _plot_manager: "Plot"

    def __call__(self) -> sp.Basic:
        return self._plot_manager._func

    def snapshot(self) -> sp.Basic:
        """Return dead symbolic snapshot."""
        return self._plot_manager._func


@dataclass(frozen=True)
class LivePlotNumericExpression:
    """Live numeric expression view for a plot."""

    _plot_manager: "Plot"

    def __call__(self, x: "np.ndarray") -> "np.ndarray":
        compiled = self.snapshot()
        return compiled(x)

    def snapshot(self) -> NumpifiedFunction:
        """Return dead numeric snapshot as a frozen numpified function."""
        numpified = self._plot_manager.numpified
        ctx = self._plot_manager._smart_figure
        return numpified.set_parameter_context(ctx).freeze(
            {sym: DYNAMIC_PARAMETER for sym in numpified.parameters[1:]}
        )

    def freeze(self, values: dict[sp.Symbol | str, object]) -> NumpifiedFunction:
        """Create a dead numeric expression with explicit frozen values."""
        return self._plot_manager.numpified.freeze(values)
