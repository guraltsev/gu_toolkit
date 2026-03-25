"""Shared helpers for plot creation/update workflows.

These helpers keep light, coordination-oriented logic out of ``Figure.py`` so
feature additions can grow in focused modules without inflating the coordinator
module beyond the decomposition budget enforced by the test suite.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def resolve_plot_id(existing_plots: Mapping[str, Any], requested_id: str | None) -> str:
    """Return a stable plot id, auto-generating one when needed."""
    if requested_id is not None:
        return requested_id
    for i in range(100):
        candidate = f"f_{i}"
        if candidate not in existing_plots:
            return candidate
    raise ValueError("Too many auto-generated IDs")



def normalize_view_ids(
    view: str | Sequence[str] | None,
    *,
    default_view_id: str,
) -> tuple[str, ...]:
    """Normalize a public ``view=`` argument into a tuple of view ids."""
    if isinstance(view, str):
        return (view,)
    if view is None:
        return (default_view_id,)
    return tuple(view)



def remove_plot_from_figure(figure: Any, plot_id: str) -> None:
    """Detach a plot's traces, remove it from the registry, and update UI."""
    plot = figure.plots.pop(plot_id, None)
    if plot is None:
        return
    for view_id in tuple(plot.views):
        plot.remove_from_view(view_id)
    figure._legend.on_plot_removed(plot_id)
