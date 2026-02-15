"""View model primitives for multi-view figure workspaces.

Purpose
-------
This module defines ``View``, the workspace-level state container introduced by
Project 019 phase 1/2. A view owns axis defaults and viewport state while the
workspace (``Figure``) owns shared parameters and info infrastructure.

Notes
-----
Phase 1/2 intentionally keeps UI routing on a single active Plotly widget.
This model therefore focuses on state ownership and compatibility shims rather
than tab-widget composition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class View:
    """State model for one plotting view in a multi-view workspace.

    Parameters
    ----------
    id : str
        Stable view identifier.
    title : str
        Human-readable title shown in view selectors.
    x_label : str
        Optional x-axis label metadata.
    y_label : str
        Optional y-axis label metadata.
    default_x_range : tuple[float, float]
        View default x-range.
    default_y_range : tuple[float, float]
        View default y-range.
    viewport_x_range : tuple[float, float] or None
        Last known viewport x-range.
    viewport_y_range : tuple[float, float] or None
        Last known viewport y-range.
    is_active : bool
        Whether the view is currently active.
    is_stale : bool
        Whether the view needs a deferred rerender.
    """

    id: str
    title: str
    x_label: str
    y_label: str
    default_x_range: tuple[float, float]
    default_y_range: tuple[float, float]
    viewport_x_range: Optional[tuple[float, float]] = None
    viewport_y_range: Optional[tuple[float, float]] = None
    is_active: bool = False
    is_stale: bool = False

