"""Colorway helpers shared by figures, plots, and the legend sidebar.

The toolkit relies on Plotly traces for rendering but owns its own side-panel
legend. When line colors are left implicit, Plotly assigns them in the browser
from the active colorway, which can vary with template choice, trace order, and
visibility state. These helpers centralize colorway resolution so the Python
side can make the same decisions deliberately and persist them when needed.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from plotly.colors import DEFAULT_PLOTLY_COLORS

try:  # pragma: no cover - optional dependency in many notebook stacks
    from PIL import ImageColor
except Exception:  # pragma: no cover - Pillow is not a declared dependency
    ImageColor = None

__all__ = [
    "color_to_picker_hex",
    "color_for_trace_index",
    "explicit_style_color",
    "resolve_colorway",
]


_HEX_COLOR_RE = re.compile(r"^#(?P<body>[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGBA_COLOR_RE = re.compile(
    r"^rgba?\(\s*"
    r"(?P<red>\d{1,3})\s*,\s*"
    r"(?P<green>\d{1,3})\s*,\s*"
    r"(?P<blue>\d{1,3})"
    r"(?:\s*,\s*(?P<alpha>[+-]?\d*\.?\d+))?"
    r"\s*\)$",
    re.IGNORECASE,
)


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


def _rgb_to_hex(red: int, green: int, blue: int) -> str:
    """Format one RGB triplet as an HTML ``#rrggbb`` color."""
    return f"#{red:02x}{green:02x}{blue:02x}"


def color_to_picker_hex(value: Any, *, fallback: str = "#6c757d") -> str:
    """Convert a color string to ``#rrggbb`` for browser color pickers.

    Legend style editing now uses a graphical picker backed by the browser's
    native ``<input type=\"color\">`` control. That control only accepts opaque
    hexadecimal colors, so the toolkit normalizes the most common plot-style
    inputs here.

    Supported inputs:

    - ``#rgb`` / ``#rgba`` / ``#rrggbb`` / ``#rrggbbaa`` (alpha ignored)
    - ``rgb(r, g, b)`` / ``rgba(r, g, b, a)`` (alpha ignored)
    - named colors when Pillow is available in the runtime environment

    Values that cannot be normalized fall back to ``fallback``.
    """

    text = _non_empty_color(value)
    if text is None:
        return str(fallback)

    match = _HEX_COLOR_RE.fullmatch(text)
    if match is not None:
        body = match.group("body")
        if len(body) in {3, 4}:
            body = "".join(ch * 2 for ch in body[:3])
        elif len(body) == 8:
            body = body[:6]
        return f"#{body.lower()}"

    match = _RGBA_COLOR_RE.fullmatch(text)
    if match is not None:
        try:
            red = int(match.group("red"))
            green = int(match.group("green"))
            blue = int(match.group("blue"))
        except (TypeError, ValueError):
            return str(fallback)
        if not all(0 <= channel <= 255 for channel in (red, green, blue)):
            return str(fallback)
        return _rgb_to_hex(red, green, blue)

    if ImageColor is not None:
        try:
            red, green, blue = ImageColor.getrgb(text)[:3]
        except Exception:
            return str(fallback)
        return _rgb_to_hex(red, green, blue)

    return str(fallback)


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
