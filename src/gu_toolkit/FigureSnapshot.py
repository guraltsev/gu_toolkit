"""Immutable snapshot of an entire Figure's reproducible state.

A ``FigureSnapshot`` aggregates parameter metadata, plot snapshots, and
info-card content into a single frozen object that can be inspected
programmatically or fed to :func:`codegen.figure_to_code` to emit a
self-contained Python script.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field

from .ParameterSnapshot import ParameterSnapshot
from .FieldPlotSnapshot import FieldPlotSnapshot
from .PlotSnapshot import PlotSnapshot


@dataclass(frozen=True)
class InfoCardSnapshot:
    """Immutable record of a simple info card.

    Parameters
    ----------
    id : Hashable
        Card identifier (key in the info panel).
    segments : tuple[str, ...]
        Ordered text segments.  Static segments contain their original text;
        dynamic (callable) segments are stored as the placeholder
        ``"<dynamic>"``.
    """

    id: Hashable
    segments: tuple[str, ...]
    view_id: str | None = None


@dataclass(frozen=True)
class ViewSnapshot:
    """Immutable record of one workspace view.

    Parameters
    ----------
    id : str
        Stable view identifier.
    title : str
        Human-readable label for the view selector.
    x_label : str
        Optional x-axis label metadata.
    y_label : str
        Optional y-axis label metadata.
    x_range : tuple[float, float]
        Default x-range for the view.
    y_range : tuple[float, float]
        Default y-range for the view.
    viewport_x_range : tuple[float, float] or None
        Last known viewport x-range.
    viewport_y_range : tuple[float, float] or None
        Last known viewport y-range.
    """

    id: str
    title: str
    x_label: str
    y_label: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    viewport_x_range: tuple[float, float] | None = None
    viewport_y_range: tuple[float, float] | None = None


@dataclass(frozen=True)
class FigureSnapshot:
    """Immutable record of a full figure's state.

    Parameters
    ----------
    x_range : tuple[float, float]
        Default x-axis range for the main view.
    y_range : tuple[float, float]
        Default y-axis range for the main view.
    sampling_points : int
        Current figure sample count used by inherited plots.
    title : str
        Figure title text.
    parameters : ParameterSnapshot
        Full parameter metadata snapshot.
    plots : dict[str, PlotSnapshot | FieldPlotSnapshot]
        Mapping of plot id to its snapshot, in insertion order.
    info_cards : tuple[InfoCardSnapshot, ...]
        Static info card snapshots.
    views : tuple[ViewSnapshot, ...]
        Workspace view definitions.
    active_view_id : str
        Currently selected view id.
    default_x_range : tuple[float, float] or None
        Figure-level default x-range used for new views.
    default_y_range : tuple[float, float] or None
        Figure-level default y-range used for new views.
    default_samples : int or None
        Figure-level default samples used for newly created plots.
    """

    x_range: tuple[float, float]
    y_range: tuple[float, float]
    sampling_points: int
    title: str
    parameters: ParameterSnapshot
    plots: dict[str, PlotSnapshot | FieldPlotSnapshot]
    info_cards: tuple[InfoCardSnapshot, ...]
    views: tuple[ViewSnapshot, ...] = field(default_factory=tuple)
    active_view_id: str = "main"
    default_x_range: tuple[float, float] | None = None
    default_y_range: tuple[float, float] | None = None
    default_samples: int | None = None

    def __post_init__(self) -> None:
        if self.default_x_range is None:
            object.__setattr__(self, "default_x_range", self.x_range)
        if self.default_y_range is None:
            object.__setattr__(self, "default_y_range", self.y_range)
        if self.default_samples is None:
            object.__setattr__(self, "default_samples", self.sampling_points)

    @property
    def samples(self) -> int:
        """Compatibility alias for :attr:`sampling_points`."""
        return self.sampling_points

    def __repr__(self) -> str:
        return (
            f"FigureSnapshot(title={self.title!r}, "
            f"plots={len(self.plots)}, "
            f"parameters={len(self.parameters)})"
        )
