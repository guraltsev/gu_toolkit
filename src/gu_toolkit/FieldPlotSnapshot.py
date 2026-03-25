"""Immutable snapshot of one scalar-field plot's reproducible state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sympy.core.expr import Expr
from sympy.core.symbol import Symbol


@dataclass(frozen=True)
class FieldPlotSnapshot:
    """Immutable record of one contour/heatmap scalar-field plot."""

    id: str
    render_mode: Literal["contour", "heatmap"]
    preset: str | None
    x_var: Symbol
    y_var: Symbol
    func: Expr
    parameters: tuple[Symbol, ...]
    label: str
    visible: bool
    x_domain: tuple[float, float] | None
    y_domain: tuple[float, float] | None
    grid: tuple[int, int] | None
    colorscale: Any | None
    z_range: tuple[float, float] | None
    show_colorbar: bool | None
    opacity: float | None
    reversescale: bool | None
    colorbar: dict[str, Any] | None
    trace: dict[str, Any] | None
    views: tuple[str, ...] = ()
    levels: int | None = None
    filled: bool | None = None
    show_labels: bool | None = None
    line_color: str | None = None
    line_width: float | None = None
    smoothing: str | bool | None = None
    connectgaps: bool | None = None
    kind: str = "field"

    @property
    def is_field(self) -> bool:
        """Return whether this snapshot represents a scalar-field trace."""
        return True

    @property
    def is_contour(self) -> bool:
        """Return whether the snapshot renders as a contour trace."""
        return self.render_mode == "contour"

    @property
    def is_heatmap(self) -> bool:
        """Return whether the snapshot renders as a heatmap trace."""
        return self.render_mode == "heatmap"

    def __repr__(self) -> str:
        return (
            f"FieldPlotSnapshot(id={self.id!r}, render_mode={self.render_mode!r}, "
            f"x_var={self.x_var!r}, y_var={self.y_var!r}, func={self.func!r})"
        )
