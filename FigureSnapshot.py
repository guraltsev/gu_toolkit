"""Immutable snapshot of an entire Figure's reproducible state.

A ``FigureSnapshot`` aggregates parameter metadata, plot snapshots, and
info-card content into a single frozen object that can be inspected
programmatically or fed to :func:`codegen.figure_to_code` to emit a
self-contained Python script.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Hashable, Optional, Tuple, Union

from .ParameterSnapshot import ParameterSnapshot
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


@dataclass(frozen=True)
class FigureSnapshot:
    """Immutable record of a full figure's state.

    Parameters
    ----------
    x_range : tuple[float, float]
        Default x-axis range.
    y_range : tuple[float, float]
        Default y-axis range.
    sampling_points : int
        Default sample count.
    title : str
        Figure title text.
    parameters : ParameterSnapshot
        Full parameter metadata snapshot.
    plots : dict[str, PlotSnapshot]
        Mapping of plot id to its snapshot, in insertion order.
    info_cards : tuple[InfoCardSnapshot, ...]
        Static info card snapshots.
    """

    x_range: Tuple[float, float]
    y_range: Tuple[float, float]
    sampling_points: int
    title: str
    parameters: ParameterSnapshot
    plots: Dict[str, PlotSnapshot]
    info_cards: tuple[InfoCardSnapshot, ...]

    def __repr__(self) -> str:
        return (
            f"FigureSnapshot(title={self.title!r}, "
            f"plots={len(self.plots)}, "
            f"parameters={len(self.parameters)})"
        )
