"""Figure context stack and defaults."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .Figure import Figure

_FIGURE_STACK_LOCAL = threading.local()


def _figure_stack() -> list[Figure]:
    """Return a thread-local figure stack."""
    stack = getattr(_FIGURE_STACK_LOCAL, "stack", None)
    if stack is None:
        stack = []
        _FIGURE_STACK_LOCAL.stack = stack
    return stack


class _FigureDefaultSentinel:
    """Sentinel value meaning "inherit from figure defaults"."""

    __slots__ = ()

    def __repr__(self) -> str:
        """Return the stable debug token for the figure-default sentinel."""
        return "FIGURE_DEFAULT"


FIGURE_DEFAULT = _FigureDefaultSentinel()


def _is_figure_default(value: Any) -> bool:
    """Return True when *value* requests figure-default behavior."""
    return value is FIGURE_DEFAULT or (
        isinstance(value, str) and value.lower() == "figure_default"
    )


def _current_figure() -> Figure | None:
    """Return the most recently pushed Figure, if any.

    Returns
    -------
    Figure or None
        The current figure on the stack, or ``None`` if no figure is active.
    """
    stack = _figure_stack()
    if not stack:
        return None
    return stack[-1]


def _require_current_figure() -> Figure:
    """Return the current Figure, or raise if none is active.

    Returns
    -------
    Figure
        The active Figure on the stack.

    Raises
    ------
    RuntimeError
        If no Figure is active.
    """
    fig = _current_figure()
    if fig is None:
        raise RuntimeError("No current Figure. Use `with fig:` first.")
    return fig


def current_figure(*, required: bool = True) -> Figure | None:
    """Return the active Figure from the context stack.

    Parameters
    ----------
    required : bool, default=True
        If True, raise when no figure is currently active.

    Returns
    -------
    Figure or None
        Active figure, or None when ``required=False`` and no context is active.
    """
    fig = _current_figure()
    if fig is None and required:
        raise RuntimeError(
            "No active Figure. Use `with fig:` to set one, "
            "or pass an explicit figure as parameter_context."
        )
    return fig


def _push_current_figure(fig: Figure) -> None:
    """Push a Figure onto the global stack.

    Parameters
    ----------
    fig : Figure
        The figure to mark as current.

    Returns
    -------
    None
    """
    _figure_stack().append(fig)


def _pop_current_figure(fig: Figure) -> None:
    """Remove a specific Figure from the global stack if present.

    Parameters
    ----------
    fig : Figure
        The figure to remove.

    Returns
    -------
    None
    """
    stack = _figure_stack()
    if not stack:
        return
    if stack[-1] is fig:
        stack.pop()
        return
    for i in range(len(stack) - 1, -1, -1):
        if stack[i] is fig:
            del stack[i]
            break


@contextmanager
def _use_figure(fig: Figure) -> Iterator[Figure]:
    """Context manager that temporarily sets a Figure as current.

    Parameters
    ----------
    fig : Figure
        The figure to make current within the context.

    Yields
    ------
    Figure
        The same figure passed in.
    """
    _push_current_figure(fig)
    try:
        yield fig
    finally:
        _pop_current_figure(fig)


# -----------------------------
# Small type aliases
# -----------------------------
NumberLike = int | float
NumberLikeOrStr = int | float | str
RangeLike = tuple[NumberLikeOrStr, NumberLikeOrStr]
VisibleSpec = bool | str  # Plotly uses True/False or the string "legendonly".

PLOT_STYLE_OPTIONS: dict[str, str] = {
    "color": "Line color. Accepts CSS-like names (e.g., red), hex (#RRGGBB), or rgb()/rgba() strings.",
    "thickness": "Line width in pixels. Larger values draw thicker lines.",
    "dash": "Line pattern. Supported values: solid, dot, dash, longdash, dashdot, longdashdot.",
    "opacity": "Overall trace opacity from 0.0 (fully transparent) to 1.0 (fully opaque).",
    "line": "Extra line-style fields as a mapping (for advanced per-line styling).",
    "trace": "Extra trace fields as a mapping (for advanced full-trace styling).",
}
