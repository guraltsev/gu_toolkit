from __future__ import annotations

import json
from pathlib import Path

import pytest
from traitlets import TraitError

import gu_toolkit
from gu_toolkit import IdentifierInput, MathInput
from gu_toolkit.math_input.identifier_widget import (
    DEFAULT_FORBIDDEN_SYMBOLS,
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
        value="theta_x",
        context_names=["mass", "theta_x", "alpha"],
        context_policy="context_only",
    )
    assert field.value == "theta_x"
    assert field.context_names == ["mass", "theta_x", "alpha"]
    assert field.context_policy == "context_only"



def test_identifier_input_allows_new_canonical_identifier_when_policy_is_context_or_new() -> None:
    field = IdentifierInput(
        value="alpha",
        context_names=["mass", "time", "speed"],
        context_policy="context_or_new",
    )
    assert field.value == "alpha"



def test_identifier_input_traits_are_synced() -> None:
    field = IdentifierInput()
    assert field.traits()["value"].metadata["sync"] is True
    assert field.traits()["context_names"].metadata["sync"] is True
    assert field.traits()["context_policy"].metadata["sync"] is True
    assert field.traits()["forbidden_symbols"].metadata["sync"] is True



def test_identifier_input_uses_default_forbidden_symbol_list() -> None:
    field = IdentifierInput(context_policy="context_or_new")
    assert field.forbidden_symbols == list(DEFAULT_FORBIDDEN_SYMBOLS)



def test_identifier_input_forbids_default_function_like_names() -> None:
    with pytest.raises(TraitError):
        IdentifierInput(value="sin", context_policy="context_or_new")

    field = IdentifierInput(context_policy="context_or_new")
    with pytest.raises(TraitError):
        field.value = "log"



def test_identifier_input_allows_replacing_default_forbidden_symbols_at_construction() -> None:
    field = IdentifierInput(
        value="sin",
        context_policy="context_or_new",
        forbidden_symbols=["alpha"],
    )
    assert field.value == "sin"
    assert field.forbidden_symbols == ["alpha"]



def test_identifier_input_rejects_invalid_identifier_shape() -> None:
    with pytest.raises(TraitError):
        IdentifierInput(value="x+1", context_policy="context_or_new")

    field = IdentifierInput(context_policy="context_or_new")
    with pytest.raises(TraitError):
        field.value = r"\theta_x"



def test_identifier_input_rejects_unknown_name_under_context_only() -> None:
    with pytest.raises(TraitError):
        IdentifierInput(
            value="angle",
            context_names=["mass", "time", "speed"],
            context_policy="context_only",
        )



def test_identifier_input_rejects_invalid_context_entries_duplicates_and_forbidden_entries() -> None:
    with pytest.raises(TraitError):
        IdentifierInput(context_names=["mass", r"\theta_x"], context_policy="context_or_new")

    with pytest.raises(TraitError):
        IdentifierInput(context_names=["mass", "mass"], context_policy="context_or_new")

    with pytest.raises(TraitError):
        IdentifierInput(context_names=["mass", "sin"], context_policy="context_or_new")



def test_identifier_input_rejects_policy_changes_that_would_invalidate_current_value() -> None:
    field = IdentifierInput(
        value="alpha",
        context_names=["mass", "time", "speed"],
        context_policy="context_or_new",
    )

    with pytest.raises(TraitError):
        field.context_policy = "context_only"

    assert field.context_policy == "context_or_new"
    assert field.value == "alpha"



def test_identifier_input_rejects_forbidden_symbol_updates_that_conflict_with_current_state() -> None:
    field = IdentifierInput(
        value="alpha",
        context_names=["alpha", "mass"],
        context_policy="context_only",
        forbidden_symbols=["sin"],
    )

    with pytest.raises(TraitError):
        field.forbidden_symbols = ["alpha"]

    assert field.forbidden_symbols == ["sin"]



def test_identifier_input_uses_its_own_frontend_assets() -> None:
    field = IdentifierInput(context_policy="context_or_new")
    assert getattr(field.layout, "width", None) == "100%"
    assert IDENTIFIER_INPUT_ESM_PATH.is_file()
    assert IDENTIFIER_INPUT_CSS_PATH.is_file()



def test_identifier_frontend_does_not_pass_restricted_options_to_constructor() -> None:
    source = IDENTIFIER_INPUT_ESM_PATH.read_text(encoding="utf-8")

    assert "new MathfieldElement({" not in source
    assert "inlineShortcuts:" not in source
    assert "scriptDepth:" not in source
    assert "smartFence:" not in source
    assert "smartMode:" not in source
    assert "smartSuperscript:" not in source



def test_identifier_frontend_keeps_only_the_mathfield_surface() -> None:
    source = IDENTIFIER_INPUT_ESM_PATH.read_text(encoding="utf-8")
    css = IDENTIFIER_INPUT_CSS_PATH.read_text(encoding="utf-8")

    assert "gu-identifier-suggestions" not in source
    assert "gu-identifier-suggestion" not in source
    assert "gu-identifier-suggestions" not in css
    assert "Context names" in source



def test_identifier_frontend_includes_identifier_keyboard_and_subscript_insert() -> None:
    source = IDENTIFIER_INPUT_ESM_PATH.read_text(encoding="utf-8")
    css = IDENTIFIER_INPUT_CSS_PATH.read_text(encoding="utf-8")

    assert "createIdentifierKeyboardLayouts" in source
    assert "keyboard.layouts = createIdentifierKeyboardLayouts" in source
    assert 'scriptDepth = [1, 0]' in source
    assert 'insert: "#@_{#?}"' in source
    assert "hide-keyboard-toggle" in css



def test_canonical_identifier_notebook_is_cleared_and_describes_keyboard_forbidden_and_subscript_checks() -> None:
    notebook = json.loads(
        Path("examples/MathLive_identifier_system_showcase.ipynb").read_text(encoding="utf-8")
    )

    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        assert cell.get("outputs", []) == []
        assert cell.get("execution_count") is None

    markdown = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "markdown"
    )
    normalized_markdown = markdown.lower()
    assert "keyboard" in normalized_markdown
    assert "forbidden" in normalized_markdown
    assert "subscript" in normalized_markdown
    assert "ready for user verification" in normalized_markdown
