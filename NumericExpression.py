"""Legacy symbolic expression view helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import sympy as sp

if TYPE_CHECKING:
    from .figure_plot import Plot


@dataclass(frozen=True)
class LivePlotSymbolicExpression:
    """Symbolic expression view for a plot."""

    _plot_manager: "Plot"

    def __call__(self) -> sp.Basic:
        return self._plot_manager._func

    def snapshot(self) -> sp.Basic:
        """Return symbolic snapshot."""
        return self._plot_manager._func
