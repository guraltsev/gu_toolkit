"""Immutable snapshot of a single plot's reproducible state.

A :class:`PlotSnapshot` captures everything needed to emit a plotting call that
reconstructs one curve on a :class:`gu_toolkit.Figure.Figure`. Cartesian plots
round-trip through ``fig.plot(...)`` and parametric plots round-trip through
``fig.parametric_plot(...)``.
"""

from __future__ import annotations

from dataclasses import dataclass

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
        Independent variable for cartesian plots, or the shared parameter
        variable for parametric plots.
    func : sympy.Expr
        Main symbolic expression. For cartesian plots this is ``y(x)``. For
        parametric plots this stores the y-coordinate expression ``y(t)``.
    parameters : tuple[Symbol, ...]
        Parameter symbols used in the plot, in evaluation order.
    label : str
        Legend label.
    visible : bool
        Plot visibility state.
    x_domain : tuple[float, float] or None
        Explicit cartesian-domain override, or ``None`` for figure default.
        Parametric plots keep this field as ``None`` because their sampling
        interval is stored in ``parameter_domain`` instead.
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
    autonormalization : bool
        Whether sound playback automatically rescales chunks whose absolute
        peak exceeds 1.0 back into ``[-1, 1]``.
    views : tuple[str, ...]
        View memberships for this plot.
    kind : str, optional
        Plot kind discriminator. Supported values are ``"cartesian"`` and
        ``"parametric"``.
    x_func : sympy.Expr or None, optional
        Parametric x-coordinate expression ``x(t)``. ``None`` for cartesian
        plots.
    parameter_domain : tuple[float, float] or None, optional
        Parametric sampling interval ``(t_min, t_max)``. ``None`` for cartesian
        plots.
    """

    id: str
    var: Symbol
    func: Expr
    parameters: tuple[Symbol, ...]
    label: str
    visible: bool
    x_domain: tuple[float, float] | None
    sampling_points: int | None
    color: str | None
    thickness: float | None
    dash: str | None
    opacity: float | None
    autonormalization: bool = False
    views: tuple[str, ...] = ()
    kind: str = "cartesian"
    x_func: Expr | None = None
    parameter_domain: tuple[float, float] | None = None

    @property
    def samples(self) -> int | None:
        """Compatibility alias for :attr:`sampling_points`."""
        return self.sampling_points

    @property
    def is_parametric(self) -> bool:
        """Return whether this snapshot represents a parametric curve."""
        return self.kind == "parametric"

    @property
    def y_func(self) -> Expr:
        """Return the primary stored symbolic expression.

        This property is a readability alias for ``func`` when consuming a
        parametric snapshot.
        """
        return self.func

    def __repr__(self) -> str:
        return (
            f"PlotSnapshot(id={self.id!r}, kind={self.kind!r}, "
            f"var={self.var!r}, func={self.func!r}, label={self.label!r})"
        )
