from __future__ import annotations

import json
from pathlib import Path

from gu_toolkit.NamedFunction import NamedFunction
from gu_toolkit.expression_context import ExpressionContext
from gu_toolkit.identifier_policy import symbol
from gu_toolkit.math_inputs import ExpressionInput, IdentifierInput


@NamedFunction
def WidgetForce(x):
    return x


def test_expression_input_transport_manifest_separates_symbols_and_functions() -> None:
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
    widget = IdentifierInput(value="")
    widget.math_json = ["Subscript", "a", ["Tuple", 1, 2]]

    assert widget.parse_value() == "a_1_2"


def test_expression_input_parse_value_prefers_mathjson_transport_and_context() -> None:
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


def test_figure_plot_editor_depends_on_public_math_input_boundary() -> None:
    source = (Path(__file__).resolve().parents[1] / "src" / "gu_toolkit" / "figure_plot_editor.py").read_text(
        encoding="utf-8"
    )

    assert "from .math_inputs import ExpressionInput, IdentifierInput" in source
    assert "from ._mathlive_widget import MathLiveField" not in source


def test_mathlive_showcase_notebook_is_figure_free_and_exercises_transport() -> None:
    path = Path(__file__).resolve().parents[1] / "examples" / "MathLive_identifier_system_showcase.ipynb"
    nb = json.loads(path.read_text(encoding="utf-8"))
    text = "\n".join("".join(cell.get("source", [])) for cell in nb["cells"])

    assert "ExpressionInput" in text
    assert "IdentifierInput" in text
    assert "math_json" in text
    assert "transport_manifest" in text
    assert "from gu_toolkit import Figure" not in text
    assert "Figure(" not in text
