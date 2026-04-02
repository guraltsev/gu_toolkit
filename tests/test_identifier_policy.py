from __future__ import annotations

import pytest

from gu_toolkit.identifier_policy import (
    IdentifierError,
    function_head_to_latex,
    identifier_to_latex,
    parse_identifier,
    validate_identifier,
)


@pytest.mark.parametrize(
    "name",
    ["x", "theta", "foo1", "x_val", "theta__x", "a_1_2"],
)
def test_validate_identifier_accepts_canonical_names(name: str) -> None:
    assert validate_identifier(name) == name


@pytest.mark.parametrize(
    "name",
    ["", "1x", r"\theta", "x y", "x+y", "x{1}", "a-b"],
)
def test_validate_identifier_rejects_invalid_names(name: str) -> None:
    with pytest.raises(IdentifierError):
        validate_identifier(name)


@pytest.mark.parametrize(
    ("name", "latex"),
    [
        ("x", "x"),
        ("theta", r"\theta"),
        ("velocity", r"\mathrm{velocity}"),
        ("x_val", r"x_{\mathrm{val}}"),
        ("a_1_2", r"a_{1,2}"),
        ("theta__x", r"\mathrm{theta\_x}"),
        ("v__x_1_2", r"\mathrm{v\_x}_{1,2}"),
        ("x_theta__i_j", r"x_{\mathrm{theta\_i},j}"),
    ],
)
def test_identifier_to_latex_examples(name: str, latex: str) -> None:
    assert identifier_to_latex(name) == latex


@pytest.mark.parametrize(
    ("name", "latex"),
    [
        ("f", "f"),
        ("Force", r"\operatorname{Force}"),
        ("Force_t", r"\operatorname{Force}_{t}"),
        ("Force__x", r"\operatorname{Force\_x}"),
    ],
)
def test_function_head_to_latex_examples(name: str, latex: str) -> None:
    assert function_head_to_latex(name) == latex


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        ("theta", "theta"),
        (r"\theta", "theta"),
        ("velocity", "velocity"),
        (r"\mathrm{velocity}", "velocity"),
        ("a_1_2", "a_1_2"),
        (r"a_{1,2}", "a_1_2"),
        ("theta__x", "theta__x"),
        (r"\mathrm{theta\_x}", "theta__x"),
        (r"x_{\mathrm{theta\_i},j}", "x_theta__i_j"),
        (r"\operatorname{Force}", "Force"),
        (r"\operatorname{Force\_x}", "Force__x"),
        (r"\operatorname{Force}_{t}", "Force_t"),
    ],
)
def test_parse_identifier_examples(text: str, canonical: str) -> None:
    assert parse_identifier(text) == canonical


@pytest.mark.parametrize(
    "canonical",
    ["x", "theta", "velocity", "a_1_2", "theta__x", "x_theta__i_j", "Force", "Force_t", "Force__x"],
)
def test_identifier_round_trip(canonical: str) -> None:
    latex = identifier_to_latex(canonical) if canonical[0].islower() else function_head_to_latex(canonical)
    assert parse_identifier(latex) == canonical
