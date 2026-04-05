from __future__ import annotations

import pytest
from traitlets import TraitError

import gu_toolkit
from gu_toolkit import IdentifierInput, MathInput
from gu_toolkit.math_input.identifier_widget import (
    IDENTIFIER_INPUT_CSS_PATH,
    IDENTIFIER_INPUT_ESM_PATH,
)


def test_identifier_input_is_reexported_from_top_level() -> None:
    assert gu_toolkit.IdentifierInput is IdentifierInput


def test_identifier_input_is_a_separate_math_input_subclass() -> None:
    field = IdentifierInput(context_names=["mass"], context_policy="context_only")
    assert isinstance(field, MathInput)
    assert type(field) is IdentifierInput


def test_identifier_input_starts_with_provided_context_value() -> None:
    field = IdentifierInput(
        value="mass",
        context_names=["mass", "time", "speed"],
        context_policy="context_only",
    )
    assert field.value == "mass"
    assert field.context_names == ["mass", "time", "speed"]
    assert field.context_policy == "context_only"


def test_identifier_input_allows_new_identifier_when_policy_is_context_or_new() -> None:
    field = IdentifierInput(
        value="angle",
        context_names=["mass", "time", "speed"],
        context_policy="context_or_new",
    )
    assert field.value == "angle"


def test_identifier_input_traits_are_synced() -> None:
    field = IdentifierInput()
    assert field.traits()["value"].metadata["sync"] is True
    assert field.traits()["context_names"].metadata["sync"] is True
    assert field.traits()["context_policy"].metadata["sync"] is True


def test_identifier_input_rejects_invalid_identifier_shape() -> None:
    with pytest.raises(TraitError):
        IdentifierInput(value="theta_x", context_policy="context_or_new")

    field = IdentifierInput(context_policy="context_or_new")
    with pytest.raises(TraitError):
        field.value = "x+1"


def test_identifier_input_rejects_unknown_name_under_context_only() -> None:
    with pytest.raises(TraitError):
        IdentifierInput(
            value="angle",
            context_names=["mass", "time", "speed"],
            context_policy="context_only",
        )


def test_identifier_input_rejects_invalid_context_entries_and_duplicates() -> None:
    with pytest.raises(TraitError):
        IdentifierInput(context_names=["mass", "theta_x"], context_policy="context_or_new")

    with pytest.raises(TraitError):
        IdentifierInput(context_names=["mass", "mass"], context_policy="context_or_new")


def test_identifier_input_rejects_policy_changes_that_would_invalidate_current_value() -> None:
    field = IdentifierInput(
        value="angle",
        context_names=["mass", "time", "speed"],
        context_policy="context_or_new",
    )

    with pytest.raises(TraitError):
        field.context_policy = "context_only"

    assert field.context_policy == "context_or_new"
    assert field.value == "angle"


def test_identifier_input_uses_its_own_frontend_assets() -> None:
    field = IdentifierInput(context_policy="context_or_new")
    assert getattr(field.layout, "width", None) == "100%"
    assert IDENTIFIER_INPUT_ESM_PATH.is_file()
    assert IDENTIFIER_INPUT_CSS_PATH.is_file()
