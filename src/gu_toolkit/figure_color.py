"""Colorway helpers shared by figures, plots, and the legend sidebar.

The toolkit relies on Plotly traces for rendering but owns its own side-panel
legend. When line colors are left implicit, Plotly assigns them in the browser
from the active colorway, which can vary with template choice, trace order, and
visibility state. These helpers centralize colorway resolution so the Python
side can make the same decisions deliberately and persist them when needed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from plotly.colors import DEFAULT_PLOTLY_COLORS

__all__ = [
    "color_for_trace_index",
    "explicit_style_color",
    "resolve_colorway",
]


def _coerce_mapping(value: Any) -> dict[str, Any]:
    """Normalize Plotly-like mapping objects to plain dictionaries."""
    if not value:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_plotly_json"):
        try:
            payload = value.to_plotly_json()
        except Exception:
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def _coerce_colorway(values: Any) -> tuple[str, ...]:
    """Return a sanitized tuple of color strings."""
    if not values:
        return ()
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            result.append(text)
    return tuple(result)


def _non_empty_color(value: Any) -> str | None:
    """Return ``value`` as a stripped color string when present."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_colorway(source: Any) -> tuple[str, ...]:
    """Resolve Plotly's active trace colorway from a figure or layout.

    Resolution order matches Plotly's practical behavior as closely as possible:

    1. An explicit ``layout.colorway`` on the figure.
    2. The template's ``layout.colorway``.
    3. Plotly's classic fallback colors.
    """
    layout = getattr(source, "layout", source)
    if layout is None:
        return tuple(str(color) for color in DEFAULT_PLOTLY_COLORS)

    direct = _coerce_colorway(getattr(layout, "colorway", ()) or ())
    if direct:
        return direct

    template = getattr(layout, "template", None)
    template_layout = getattr(template, "layout", None)
    templated = _coerce_colorway(getattr(template_layout, "colorway", ()) or ())
    if templated:
        return templated

    return tuple(str(color) for color in DEFAULT_PLOTLY_COLORS)


def color_for_trace_index(
    source: Any,
    trace_index: int,
    *,
    fallback: str = "#6c757d",
) -> str:
    """Return the colorway entry that corresponds to ``trace_index``."""
    palette = resolve_colorway(source)
    if not palette:
        return fallback
    return str(palette[int(trace_index) % len(palette)])


def explicit_style_color(
    *,
    color: Any = None,
    line: Any = None,
    trace: Any = None,
) -> str | None:
    """Return an explicitly requested trace color when user style sets one.

    The toolkit accepts color in several forms:

    - ``color=...``
    - ``line={"color": ...}``
    - ``trace={"line": {"color": ...}}``
    - ``trace={"line_color": ...}``
    """
    direct = _non_empty_color(color)
    if direct is not None:
        return direct

    line_mapping = _coerce_mapping(line)
    line_color = _non_empty_color(line_mapping.get("color"))
    if line_color is not None:
        return line_color

    trace_mapping = _coerce_mapping(trace)
    magic_line_color = _non_empty_color(trace_mapping.get("line_color"))
    if magic_line_color is not None:
        return magic_line_color

    nested_line = _coerce_mapping(trace_mapping.get("line"))
    nested_line_color = _non_empty_color(nested_line.get("color"))
    if nested_line_color is not None:
        return nested_line_color

    return None
