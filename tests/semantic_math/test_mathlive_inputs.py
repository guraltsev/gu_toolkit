"""Public MathLive widget boundary and MathJSON transport rules.

This file protects the figure-independent MathLive layer. The important design
choices are:

- widgets use ``ExpressionContext`` instead of figure state
- MathJSON is the preferred transport when it is still synchronized with the current widget text
- ambiguous transport spellings fail loudly unless the context resolves them
- internal modules should import from the new ``gu_toolkit.mathlive`` package
  rather than from private implementation files
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gu_toolkit import NamedFunction
from gu_toolkit.identifiers import symbol
from gu_toolkit.math_inputs import ExpressionInput as legacy_expression_input
from gu_toolkit.math_inputs import IdentifierInput as legacy_identifier_input
from gu_toolkit.mathlive import (
    ExpressionContext,
    ExpressionInput,
    IdentifierInput,
    MathJSONParseError,
    mathjson_to_identifier,
    mathjson_to_sympy,
)


@NamedFunction
def WidgetForce(x):
    return x


def test_expression_input_transport_manifest_separates_symbols_and_functions() -> None:
    """The frontend manifest should teach MathLive which names are symbols and which are callables."""

    velocity = symbol("velocity")
    x = symbol("x")
    ctx = ExpressionContext.from_symbols([velocity, x], functions=[WidgetForce], include_named_functions=False)

    widget = ExpressionInput(context=ctx)
    symbols = {entry["name"]: entry for entry in widget.semantic_context["symbols"]}
    functions = {entry["name"]: entry for entry in widget.semantic_context["functions"]}

    assert widget.field_role == "expression"
    assert symbols["velocity"]["latex"] == r"\mathrm{velocity}"
    assert functions["WidgetForce"]["latexHead"] == r"\operatorname{WidgetForce}"
    assert functions["WidgetForce"]["template"] == r"\operatorname{WidgetForce}(#0)"


def test_identifier_input_parse_value_prefers_mathjson_transport() -> None:
    """Structured MathJSON input should win over the plain text field when both are present."""

    widget = IdentifierInput(value="")
    widget.math_json = ["Subscript", "a", ["Tuple", 1, 2]]

    assert widget.parse_value() == "a_1_2"


def test_expression_input_parse_value_prefers_mathjson_transport_and_context() -> None:
    """Expression widgets should resolve MathJSON through the same symbol/function registry as text input."""

    velocity = symbol("velocity")
    theta_x = symbol("theta__x")
    ctx = ExpressionContext.from_symbols(
        [velocity, theta_x],
        functions=[WidgetForce],
        include_named_functions=False,
    )

    widget = ExpressionInput(context=ctx, value="")
    widget.math_json = ["Add", ["WidgetForce", "theta__x"], ["Multiply", "velocity", 2]]

    assert widget.parse_value() == WidgetForce(theta_x) + 2 * velocity


def test_identifier_input_text_edits_override_older_mathjson_transport() -> None:
    """Changing the visible text after a structured payload should not keep returning a stale identifier."""

    widget = IdentifierInput(value=r"a_{1,2}")
    widget.math_json = ["Subscript", "a", ["Tuple", 1, 2]]

    widget.value = "x"

    assert widget.parse_value() == "x"


def test_expression_input_text_edits_override_older_mathjson_transport() -> None:
    """Expression widgets should fall back to the newer text when an older MathJSON payload becomes stale."""

    x = symbol("x")
    y = symbol("y")
    ctx = ExpressionContext.from_symbols([x, y], include_named_functions=False)
    widget = ExpressionInput(context=ctx, value="x")
    widget.math_json = "x"

    widget.value = "y"

    assert widget.parse_value() == y


def test_transport_source_value_keeps_matching_mathjson_authoritative_even_if_sync_order_varies() -> None:
    """An explicit frontend source snapshot should preserve MathJSON authority once it matches the visible text again."""

    widget = IdentifierInput(value=r"a_{1,2}")
    widget.math_json = ["Subscript", "a", ["Tuple", 1, 2]]
    widget.value = "x"
    assert widget.parse_value() == "x"

    widget.value = r"a_{1,2}"
    widget.transport_source_value = r"a_{1,2}"

    assert widget.parse_value() == "a_1_2"


def test_transport_rejects_ambiguous_single_underscore_without_context() -> None:
    """A single underscore in transport space is ambiguous, so unregistered names should be rejected."""

    with pytest.raises(MathJSONParseError, match="ambiguous"):
        mathjson_to_identifier("theta_x")


def test_transport_accepts_the_same_name_when_context_registers_it() -> None:
    """Once the context says a name is atomic, transport should trust that registration."""

    ctx = ExpressionContext.from_symbols([symbol("theta_x")], include_named_functions=False)

    assert mathjson_to_identifier("theta_x", context=ctx) == "theta_x"


def test_figure_plot_editor_depends_on_the_canonical_mathlive_boundary() -> None:
    """Figure editing code should consume the public widgets from the new subpackage, not private backends."""

    source = (Path(__file__).resolve().parents[2] / "src" / "gu_toolkit" / "figure_plot_editor.py").read_text(
        encoding="utf-8"
    )

    assert "from .mathlive.inputs import ExpressionInput, IdentifierInput" in source
    assert "from ._mathlive_widget import MathLiveField" not in source


def test_legacy_math_inputs_import_still_points_at_the_public_widgets() -> None:
    """Older imports should remain valid while users migrate to ``gu_toolkit.mathlive``."""

    assert legacy_expression_input is ExpressionInput
    assert legacy_identifier_input is IdentifierInput


def test_expression_input_rejects_empty_sentinel_mathjson_when_no_text_is_present() -> None:
    """An empty MathJSON sentinel should behave like missing input, not like the number zero."""

    widget = ExpressionInput(value="")
    widget.math_json = "Nothing"

    with pytest.raises(ValueError, match="required"):
        widget.parse_value()


def test_expression_input_ignores_empty_sentinel_mathjson_when_text_is_present() -> None:
    """When MathJSON only carries an empty sentinel, the visible text field should remain authoritative."""

    x = symbol("x")
    ctx = ExpressionContext.from_symbols([x], include_named_functions=False)
    widget = ExpressionInput(context=ctx, value="x")
    widget.math_json = "Nothing"

    assert widget.parse_value() == x


def test_identifier_input_rejects_empty_sentinel_mathjson_when_no_text_is_present() -> None:
    """Identifier widgets should reject empty/sentinel transport instead of accepting a fake identifier."""

    widget = IdentifierInput(value="")
    widget.math_json = "Nothing"

    with pytest.raises(ValueError, match="required"):
        widget.parse_value()


def test_identifier_input_ignores_empty_sentinel_mathjson_when_text_is_present() -> None:
    """Visible text should win when the MathJSON payload only says that the field is empty."""

    widget = IdentifierInput(value="x")
    widget.math_json = "Nothing"

    assert widget.parse_value() == "x"


def test_low_level_mathjson_helpers_reject_empty_sentinel_payloads() -> None:
    """The transport boundary should treat empty MathJSON sentinels as missing input, not semantic content."""

    empty_payloads = [
        "Nothing",
        {"sym": "Nothing"},
        ["Hold", "Nothing"],
        {"fn": "Hold", "args": ["Nothing"]},
        {"fn": {"sym": "Hold"}, "args": [{"sym": "Nothing"}]},
    ]

    for payload in empty_payloads:
        with pytest.raises(MathJSONParseError, match="empty"):
            mathjson_to_identifier(payload)
        with pytest.raises(MathJSONParseError, match="empty"):
            mathjson_to_sympy(payload)
