"""Immutable snapshot of a single Plot's reproducible state.

A ``PlotSnapshot`` captures everything needed to emit a ``fig.plot(...)`` call
that reconstructs the curve: the symbolic expression, independent variable,
parameter list, styling, and domain/sampling overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union

from sympy.core.expr import Expr
from sympy.core.symbol import Symbol


@dataclass(frozen=True)
class PlotSnapshot:
    """Immutable record of one plot's state.

    Parameters
    ----------
    id : str
        Plot identifier (key in ``Figure.plots``).
    var : sympy.Symbol
        Independent variable.
    func : sympy.Expr
        Symbolic expression being plotted.
    parameters : tuple[Symbol, ...]
        Parameter symbols used in *func* (in evaluation order).
    label : str
        Legend label.
    visible : bool or str
        Plotly visibility (``True``, ``False``, or ``"legendonly"``).
    x_domain : tuple[float, float] or None
        Explicit domain override, or ``None`` for figure default.
    sampling_points : int or None
        Per-plot sample count override, or ``None`` for figure default.
    color : str or None
        Line color.
    thickness : float or None
        Line width in pixels.
    dash : str or None
        Line dash pattern.
    opacity : float or None
        Trace opacity (0.0 – 1.0).
    """

    id: str
    var: Symbol
    func: Expr
    parameters: tuple[Symbol, ...]
    label: str
    visible: Union[bool, str]
    x_domain: Optional[Tuple[float, float]]
    sampling_points: Optional[int]
    color: Optional[str]
    thickness: Optional[float]
    dash: Optional[str]
    opacity: Optional[float]

    def __repr__(self) -> str:
        return (
            f"PlotSnapshot(id={self.id!r}, var={self.var!r}, "
            f"func={self.func!r}, label={self.label!r})"
        )
