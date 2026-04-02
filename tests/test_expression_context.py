from __future__ import annotations

import sympy as sp

from gu_toolkit.NamedFunction import NamedFunction
from gu_toolkit.expression_context import ExpressionContext
from gu_toolkit.identifier_policy import symbol


@NamedFunction
def ContextForce(x):
    return x


@NamedFunction
def ContextForce__x(x):
    return x


def test_mathlive_wrapped_mathrm_function_call_is_recovered() -> None:
    a = symbol("a")
    b = symbol("b")
    x = symbol("x")
    ctx = ExpressionContext.from_symbols(
        [a, b, x],
        functions=[ContextForce],
        include_named_functions=False,
    )

    expr = ctx.parse_expression(r"a\cdot\mathrm{ContextForce\left(b\cdot x\right)}")
    assert expr == a * ContextForce(b * x)


def test_mathlive_wrapped_mathrm_function_call_with_literal_underscore_is_recovered() -> None:
    t = symbol("t")
    ctx = ExpressionContext.from_symbols(
        [t],
        functions=[ContextForce__x],
        include_named_functions=False,
    )

    expr = ctx.parse_expression(r"\mathrm{ContextForce\_x\left(t\right)}")
    assert expr.func is ContextForce__x
    assert expr.args == (t,)


def test_known_multi_letter_symbol_stays_atomic() -> None:
    velocity = symbol("velocity")
    x = symbol("x")
    ctx = ExpressionContext.from_symbols([velocity, x], include_named_functions=False)

    expr = ctx.parse_expression("velocity*x")
    assert expr == velocity * x


def test_unknown_multi_letter_name_still_splits() -> None:
    ctx = ExpressionContext()

    expr = ctx.parse_expression("ab")
    assert expr == sp.Symbol("a") * sp.Symbol("b")


def test_explicit_mathrm_symbol_is_reversible_even_without_context() -> None:
    ctx = ExpressionContext()
    velocity = symbol("velocity")

    expr = ctx.parse_expression(r"\mathrm{velocity}*x")
    assert expr == velocity * sp.Symbol("x")


def test_known_named_function_parses_as_callable_head() -> None:
    x = symbol("x")
    ctx = ExpressionContext.from_symbols([x], functions=[ContextForce], include_named_functions=False)

    expr = ctx.parse_expression("ContextForce(x)")
    assert expr.func is ContextForce
    assert expr.args == (x,)


def test_explicit_operatorname_function_head_parses_as_callable_head() -> None:
    x = symbol("x")
    ctx = ExpressionContext.from_symbols([x], functions=[ContextForce], include_named_functions=False)

    expr = ctx.parse_expression(r"\operatorname{ContextForce}(x)")
    assert expr.func is ContextForce
    assert expr.args == (x,)


def test_explicit_mathrm_function_head_remains_supported_for_compatibility() -> None:
    x = symbol("x")
    ctx = ExpressionContext.from_symbols([x], functions=[ContextForce], include_named_functions=False)

    expr = ctx.parse_expression(r"\mathrm{ContextForce}(x)")
    assert expr.func is ContextForce
    assert expr.args == (x,)


def test_context_render_latex_uses_semantic_symbol_names() -> None:
    velocity = symbol("velocity")
    theta_x = symbol("theta__x")
    ctx = ExpressionContext.from_symbols([velocity, theta_x], include_named_functions=False)

    expr = velocity + theta_x
    assert ctx.render_latex(expr) == r"\mathrm{theta\_x} + \mathrm{velocity}"


def test_context_render_latex_uses_operatorname_for_named_functions() -> None:
    x = symbol("x")
    ctx = ExpressionContext.from_symbols([x], functions=[ContextForce], include_named_functions=False)

    assert ctx.render_latex(ContextForce(x)) == r"\operatorname{ContextForce}(x)"


def test_lambda_symbol_can_be_protected_via_context() -> None:
    lam = symbol("lambda")
    ctx = ExpressionContext.from_symbols([lam], include_named_functions=False)

    expr = ctx.parse_expression("lambda + 1")
    assert expr == lam + 1


def test_mathjson_expression_transport_preserves_known_symbols_and_functions() -> None:
    velocity = symbol("velocity")
    x = symbol("x")
    theta_x = symbol("theta__x")
    ctx = ExpressionContext.from_symbols(
        [velocity, x, theta_x],
        functions=[ContextForce],
        include_named_functions=False,
    )

    expr = ctx.parse_expression(
        "",
        math_json=["Add", ["Multiply", "velocity", "x"], ["ContextForce", "theta__x"]],
    )

    assert expr == velocity * x + ContextForce(theta_x)


def test_mathjson_identifier_transport_supports_subscript_tuples() -> None:
    ctx = ExpressionContext()

    assert ctx.parse_identifier("", math_json=["Subscript", "a", ["Tuple", 1, 2]]) == "a_1_2"


def test_mathjson_transport_allows_context_symbol_over_standard_constant() -> None:
    pi_symbol = symbol("pi")
    ctx = ExpressionContext.from_symbols([pi_symbol], include_named_functions=False)

    expr = ctx.parse_expression("", math_json="pi")
    assert expr == pi_symbol


def test_mathjson_transport_supports_subscripted_function_heads() -> None:
    x = symbol("x")
    ctx = ExpressionContext.from_symbols([x], functions=["Force_t"], include_named_functions=False)

    expr = ctx.parse_expression("", math_json=[["Subscript", "Force", "t"], "x"])
    assert expr.func.__gu_name__ == "Force_t"
    assert expr.args == (x,)
