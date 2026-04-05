from __future__ import annotations

import pytest
from traitlets import TraitError

import gu_toolkit
from gu_toolkit import MathInput
from gu_toolkit.math_input.widget import MATH_INPUT_CSS_PATH, MATH_INPUT_ESM_PATH


def test_math_input_is_reexported_from_top_level() -> None:
    assert gu_toolkit.MathInput is MathInput


def test_math_input_starts_with_provided_value() -> None:
    field = MathInput(value=r"\frac{x+1}{x-1}")
    assert field.value == r"\frac{x+1}{x-1}"


def test_math_input_value_trait_is_synced_and_string_typed() -> None:
    field = MathInput()
    assert field.traits()["value"].metadata["sync"] is True
    field.value = r"x^2 + 1"
    assert field.value == r"x^2 + 1"


def test_math_input_rejects_non_string_values() -> None:
    field = MathInput()
    with pytest.raises(TraitError):
        field.value = 123  # type: ignore[assignment]


def test_math_input_uses_its_own_state_and_assets() -> None:
    first = MathInput(value="x")
    second = MathInput(value="y")

    first.value = "z"

    assert second.value == "y"
    assert getattr(first.layout, "width", None) == "100%"
    assert MATH_INPUT_ESM_PATH.is_file()
    assert MATH_INPUT_CSS_PATH.is_file()
