"""Public MathLive widget boundary and MathJSON transport rules.

This file protects the figure-independent MathLive layer. The important design
choices are:

- widgets use ``ExpressionContext`` instead of figure state
- MathJSON is the preferred transport when available
- ambiguous transport spellings fail loudly unless the context resolves them
- internal modules should import from the new ``gu_toolkit.mathlive`` package
  rather than from private implementation files
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gu_toolkit import NamedFunction
from gu_toolkit.math_inputs import ExpressionInput as legacy_expression_input
from gu_toolkit.math_inputs import IdentifierInput as legacy_identifier_input
from gu_toolkit.identifiers import symbol
from gu_toolkit.mathlive import (
    ExpressionContext,
    ExpressionInput,
    IdentifierInput,
    MathJSONParseError,
    mathjson_to_identifier,
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
