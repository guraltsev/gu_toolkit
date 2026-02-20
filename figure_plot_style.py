"""Plot-style option contracts shared by figure plotting APIs.

This module centralizes the discoverable style keyword metadata and alias
resolution rules used by :meth:`Figure.plot` and module-level ``plot`` helper
entry points. Keeping these contracts outside ``Figure.py`` supports
coordinator-only responsibilities and provides a single place for tests to lock
style semantics.
"""

from __future__ import annotations

PLOT_STYLE_OPTIONS: dict[str, str] = {
    "color": "Line color. Accepts CSS-like names (e.g., red), hex (#RRGGBB), or rgb()/rgba() strings.",
    "thickness": "Line width in pixels. Larger values draw thicker lines.",
    "width": "Alias for thickness.",
    "dash": "Line pattern. Supported values: solid, dot, dash, longdash, dashdot, longdashdot.",
    "opacity": "Overall trace opacity from 0.0 (fully transparent) to 1.0 (fully opaque).",
    "alpha": "Alias for opacity.",
    "line": "Extra line-style fields as a mapping (for advanced per-line styling).",
    "trace": "Extra trace fields as a mapping (for advanced full-trace styling).",
}


def resolve_style_aliases(
    *,
    thickness: int | float | None,
    width: int | float | None,
    opacity: int | float | None,
    alpha: int | float | None,
) -> tuple[int | float | None, int | float | None]:
    """Resolve user-provided style aliases into canonical values.

    Raises
    ------
    ValueError
        If alias and canonical values are both provided with different values.
    """
    if width is not None:
        if thickness is not None and width != thickness:
            raise ValueError(
                "plot() received both thickness= and width= with different values; use only one."
            )
        thickness = width if thickness is None else thickness

    if alpha is not None:
        if opacity is not None and alpha != opacity:
            raise ValueError(
                "plot() received both opacity= and alpha= with different values; use only one."
            )
        opacity = alpha if opacity is None else opacity

    return thickness, opacity


__all__ = ["PLOT_STYLE_OPTIONS", "resolve_style_aliases"]
