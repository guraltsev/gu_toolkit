"""Style metadata and validation helpers for scalar-field plotting APIs.

The scalar-field subsystem accepts a separate, field-oriented style contract
from line plots. This module mirrors :mod:`gu_toolkit.figure_plot_style` so the
public API, discoverability helpers, and lightweight validation all derive from
one source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldStyleSpec:
    """Structured metadata for one public scalar-field style keyword."""

    name: str
    aliases: tuple[str, ...] = ()
    type_doc: str = ""
    default_doc: str = ""
    description: str = ""
    accepted_values: tuple[Any, ...] = ()

    def format_help(self) -> str:
        parts = []
        if self.description:
            parts.append(self.description.rstrip(".") + ".")
        if self.accepted_values:
            parts.append(
                "Supported values: " + ", ".join(repr(v) for v in self.accepted_values) + "."
            )
        if self.aliases:
            alias_word = "Alias" if len(self.aliases) == 1 else "Aliases"
            parts.append(f"{alias_word}: {', '.join(self.aliases)}.")
        if self.type_doc:
            parts.append(f"Type: {self.type_doc}.")
        if self.default_doc:
            parts.append(f"Default: {self.default_doc}.")
        return " ".join(parts)

    def format_alias_help(self, alias: str) -> str:
        alias_name = str(alias)
        if alias_name not in self.aliases:
            raise KeyError(f"{alias_name!r} is not an alias of {self.name!r}")
        parts = [f"Alias for {self.name}."]
        if self.description:
            parts.append(self.description.rstrip(".") + ".")
        if self.accepted_values:
            parts.append(
                "Supported values: " + ", ".join(repr(v) for v in self.accepted_values) + "."
            )
        if self.type_doc:
            parts.append(f"Type: {self.type_doc}.")
        if self.default_doc:
            parts.append(f"Default: {self.default_doc}.")
        return " ".join(parts)


FIELD_STYLE_OPTIONS: tuple[FieldStyleSpec, ...] = (
    FieldStyleSpec(
        name="colorscale",
        type_doc="str | sequence[tuple[float, str]] | None",
        default_doc="Plotly/default field colorscale",
        description="Scalar-field colorscale used for contour or heatmap coloring",
    ),
    FieldStyleSpec(
        name="z_range",
        type_doc="tuple[int | float | str, int | float | str] | None",
        default_doc="automatic from data",
        description="Explicit scalar range shown by the colorscale as (zmin, zmax)",
    ),
    FieldStyleSpec(
        name="show_colorbar",
        aliases=("showscale",),
        type_doc="bool | None",
        default_doc="False for contour, True for heatmap/temperature",
        description="Show or hide the Plotly colorbar",
    ),
    FieldStyleSpec(
        name="opacity",
        aliases=("alpha",),
        type_doc="int | float | None",
        default_doc="1.0 / Plotly default trace opacity",
        description="Overall field opacity from 0.0 (transparent) to 1.0 (opaque)",
    ),
    FieldStyleSpec(
        name="reversescale",
        type_doc="bool | None",
        default_doc="False",
        description="Reverse the colorscale direction",
    ),
    FieldStyleSpec(
        name="colorbar",
        type_doc="dict[str, Any] | None",
        default_doc="no extra colorbar overrides",
        description="Extra Plotly colorbar fields as a mapping",
    ),
    FieldStyleSpec(
        name="trace",
        type_doc="dict[str, Any] | None",
        default_doc="no extra trace overrides",
        description="Extra full-trace fields as a mapping for advanced Plotly styling",
    ),
    FieldStyleSpec(
        name="levels",
        type_doc="int | None",
        default_doc="Plotly contour default",
        description="Approximate number of contour levels",
    ),
    FieldStyleSpec(
        name="filled",
        type_doc="bool | None",
        default_doc="False for contour",
        description="Fill contour bands instead of drawing contour lines only",
    ),
    FieldStyleSpec(
        name="show_labels",
        type_doc="bool | None",
        default_doc="False",
        description="Show contour labels on contour lines",
    ),
    FieldStyleSpec(
        name="line_color",
        type_doc="str | None",
        default_doc="Plotly/default contour line coloring",
        description="Explicit contour-line color override",
    ),
    FieldStyleSpec(
        name="line_width",
        type_doc="int | float | None",
        default_doc="Plotly contour line width",
        description="Contour-line width in pixels",
    ),
    FieldStyleSpec(
        name="smoothing",
        aliases=("zsmooth",),
        type_doc="str | bool | None",
        default_doc="False",
        description="Heatmap smoothing policy",
        accepted_values=(False, "fast", "best"),
    ),
    FieldStyleSpec(
        name="connectgaps",
        type_doc="bool | None",
        default_doc="Plotly default",
        description="Whether missing heatmap cells should be gap-connected",
    ),
)

_FIELD_STYLE_SPEC_BY_NAME = {spec.name: spec for spec in FIELD_STYLE_OPTIONS}


def field_style_option_docs(*, include_aliases: bool = True) -> dict[str, str]:
    """Return discoverability text for scalar-field style keywords."""
    docs: dict[str, str] = {}
    for spec in FIELD_STYLE_OPTIONS:
        docs[spec.name] = spec.format_help()
        if include_aliases:
            for alias in spec.aliases:
                docs[alias] = spec.format_alias_help(alias)
    return docs


def resolve_field_style_kwargs(
    style_kwargs: dict[str, Any], *, caller: str = "scalar_field()"
) -> dict[str, Any]:
    """Resolve alias keywords in ``style_kwargs`` into canonical names."""
    resolved = dict(style_kwargs)

    for spec in FIELD_STYLE_OPTIONS:
        candidates = [
            (name, resolved[name])
            for name in (spec.name, *spec.aliases)
            if name in resolved and resolved[name] is not None
        ]
        if len(candidates) > 1:
            canonical_value = candidates[0][1]
            for other_name, other_value in candidates[1:]:
                if other_value != canonical_value:
                    raise ValueError(
                        f"{caller} received both {spec.name}= and {other_name}= with different values; use only one."
                    )
        if candidates:
            resolved[spec.name] = candidates[0][1]
        for alias in spec.aliases:
            resolved.pop(alias, None)

    return resolved


def validate_field_style_kwargs(
    style_kwargs: dict[str, Any], *, caller: str = "scalar_field()"
) -> dict[str, Any]:
    """Resolve aliases and validate metadata-driven scalar-field style constraints."""
    resolved = resolve_field_style_kwargs(style_kwargs, caller=caller)
    for name, value in tuple(resolved.items()):
        spec = _FIELD_STYLE_SPEC_BY_NAME.get(name)
        if spec is None or value is None or not spec.accepted_values:
            continue
        if value not in spec.accepted_values:
            allowed = ", ".join(repr(v) for v in spec.accepted_values)
            raise ValueError(
                f"{caller} received invalid {name}={value!r}. Supported values: {allowed}."
            )

    levels = resolved.get("levels")
    if levels is not None and int(levels) <= 0:
        raise ValueError(f"{caller} requires levels to be a positive integer.")

    opacity = resolved.get("opacity")
    if opacity is not None:
        opacity_value = float(opacity)
        if not 0.0 <= opacity_value <= 1.0:
            raise ValueError(f"{caller} requires opacity to be between 0.0 and 1.0.")

    z_range = resolved.get("z_range")
    if z_range is not None:
        if not isinstance(z_range, tuple) or len(z_range) != 2:
            raise ValueError(
                f"{caller} requires z_range to have shape (zmin, zmax)."
            )

    return resolved


__all__ = [
    "FIELD_STYLE_OPTIONS",
    "FieldStyleSpec",
    "field_style_option_docs",
    "resolve_field_style_kwargs",
    "validate_field_style_kwargs",
]
