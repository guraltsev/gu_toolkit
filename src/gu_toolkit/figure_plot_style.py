"""Plot-style metadata and helpers shared by plotting APIs.

This module centralizes the public style contract accepted by
:meth:`gu_toolkit.Figure.Figure.plot` and the module-level :func:`plot`
helper.  The contract is represented as structured metadata so the package can
derive human-readable help text, alias resolution, and lightweight validation
from one source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlotStyleSpec:
    """Structured metadata describing one accepted plot-style keyword.

    Parameters
    ----------
    name:
        Canonical public keyword.
    aliases:
        Alternative keyword spellings accepted for compatibility.
    type_doc:
        Human-readable type description used in discoverability output.
    default_doc:
        Human-readable default behavior description.
    description:
        Plain-language explanation of what the keyword controls.
    accepted_values:
        Optional fixed set of accepted string values. When present, the same
        metadata is used for both documentation and lightweight validation.
    """

    name: str
    aliases: tuple[str, ...] = ()
    type_doc: str = ""
    default_doc: str = ""
    description: str = ""
    accepted_values: tuple[str, ...] = ()

    def format_help(self) -> str:
        """Return the user-facing help text for the canonical keyword."""
        parts: list[str] = [self.description.rstrip(".") + "."] if self.description else []
        if self.accepted_values:
            parts.append(
                "Supported values: " + ", ".join(self.accepted_values) + "."
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
        """Return help text for one alias keyword."""
        alias_name = str(alias)
        if alias_name not in self.aliases:
            raise KeyError(f"{alias_name!r} is not an alias of {self.name!r}")
        parts = [f"Alias for {self.name}."]
        if self.description:
            parts.append(self.description.rstrip(".") + ".")
        if self.accepted_values:
            parts.append(
                "Supported values: " + ", ".join(self.accepted_values) + "."
            )
        if self.type_doc:
            parts.append(f"Type: {self.type_doc}.")
        if self.default_doc:
            parts.append(f"Default: {self.default_doc}.")
        return " ".join(parts)


PLOT_STYLE_OPTIONS: tuple[PlotStyleSpec, ...] = (
    PlotStyleSpec(
        name="color",
        type_doc="str | None",
        default_doc="Plotly/default colorway",
        description=(
            "Line color. Accepts CSS-like names (for example red), hex"
            " strings such as #RRGGBB, or rgb()/rgba() strings"
        ),
    ),
    PlotStyleSpec(
        name="thickness",
        aliases=("width",),
        type_doc="int | float | None",
        default_doc="Plotly line width",
        description="Line width in pixels. Larger values draw thicker lines",
    ),
    PlotStyleSpec(
        name="dash",
        type_doc="str | None",
        default_doc="solid",
        description="Line pattern",
        accepted_values=(
            "solid",
            "dot",
            "dash",
            "longdash",
            "dashdot",
            "longdashdot",
        ),
    ),
    PlotStyleSpec(
        name="opacity",
        aliases=("alpha",),
        type_doc="int | float | None",
        default_doc="1.0 / Plotly default trace opacity",
        description=(
            "Overall trace opacity from 0.0 (fully transparent) to 1.0"
            " (fully opaque)"
        ),
    ),
    PlotStyleSpec(
        name="line",
        type_doc="Mapping[str, Any] | None",
        default_doc="no extra line overrides",
        description="Extra line-style fields as a mapping for advanced per-line styling",
    ),
    PlotStyleSpec(
        name="trace",
        type_doc="Mapping[str, Any] | None",
        default_doc="no extra trace overrides",
        description="Extra full-trace fields as a mapping for advanced Plotly styling",
    ),
    PlotStyleSpec(
        name="autonormalization",
        type_doc="bool | None",
        default_doc="False / disabled",
        description=(
            "Per-plot sound setting. When enabled, playback automatically"
            " scales chunks whose absolute peak exceeds 1.0 back into"
            " [-1, 1] instead of raising an error"
        ),
    ),
)

_PLOT_STYLE_SPEC_BY_NAME = {spec.name: spec for spec in PLOT_STYLE_OPTIONS}
_PLOT_STYLE_ALIAS_TO_CANONICAL = {
    alias: spec.name for spec in PLOT_STYLE_OPTIONS for alias in spec.aliases
}


def plot_style_option_docs(*, include_aliases: bool = True) -> dict[str, str]:
    """Return discoverability text for accepted plot-style keywords.

    Parameters
    ----------
    include_aliases:
        When ``True``, include explicit entries for compatibility aliases such
        as ``width`` and ``alpha``.
    """
    docs: dict[str, str] = {}
    for spec in PLOT_STYLE_OPTIONS:
        docs[spec.name] = spec.format_help()
        if include_aliases:
            for alias in spec.aliases:
                docs[alias] = spec.format_alias_help(alias)
    return docs


def resolve_style_kwargs(
    style_kwargs: dict[str, Any], *, caller: str = "plot()"
) -> dict[str, Any]:
    """Resolve alias keywords in ``style_kwargs`` into canonical names.

    The returned dictionary preserves all non-style keys untouched and removes
    alias keys once they have been folded into their canonical equivalents.

    Raises
    ------
    ValueError
        If a canonical keyword and one of its aliases are provided with
        different values.
    """
    resolved = dict(style_kwargs)

    for spec in PLOT_STYLE_OPTIONS:
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
                        f"{caller} received both {spec.name}= and {other_name}= "
                        "with different values; use only one."
                    )
        if candidates:
            resolved[spec.name] = candidates[0][1]
        for alias in spec.aliases:
            resolved.pop(alias, None)

    return resolved


def validate_style_kwargs(
    style_kwargs: dict[str, Any], *, caller: str = "plot()"
) -> dict[str, Any]:
    """Resolve aliases and validate metadata-driven style constraints.

    Validation is intentionally lightweight and only enforces constraints that
    are encoded in :data:`PLOT_STYLE_OPTIONS`, such as the fixed set of
    accepted ``dash`` values. More specialized validation (for example Plotly's
    own field-level checks) remains the responsibility of downstream code.
    """
    resolved = resolve_style_kwargs(style_kwargs, caller=caller)
    for name, value in tuple(resolved.items()):
        spec = _PLOT_STYLE_SPEC_BY_NAME.get(name)
        if spec is None or value is None or not spec.accepted_values:
            continue
        if value not in spec.accepted_values:
            allowed = ", ".join(spec.accepted_values)
            raise ValueError(
                f"{caller} received invalid {name}={value!r}. "
                f"Supported values: {allowed}."
            )
    return resolved


def resolve_style_aliases(
    *,
    thickness: int | float | None,
    width: int | float | None,
    opacity: int | float | None,
    alpha: int | float | None,
    caller: str = "plot()",
) -> tuple[int | float | None, int | float | None]:
    """Resolve supported alias pairs into canonical values.

    This compatibility helper preserves the pre-refactor return shape used by a
    few internal call sites while delegating the actual alias policy to the
    structured metadata in :data:`PLOT_STYLE_OPTIONS`.
    """
    resolved = resolve_style_kwargs(
        {
            "thickness": thickness,
            "width": width,
            "opacity": opacity,
            "alpha": alpha,
        },
        caller=caller,
    )
    return resolved.get("thickness"), resolved.get("opacity")


__all__ = [
    "PLOT_STYLE_OPTIONS",
    "PlotStyleSpec",
    "plot_style_option_docs",
    "resolve_style_aliases",
    "resolve_style_kwargs",
    "validate_style_kwargs",
]
