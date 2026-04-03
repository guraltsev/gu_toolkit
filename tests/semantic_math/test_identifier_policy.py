"""Contracts for the canonical identifier system.

These tests document the identifier layer as the source of truth for symbolic
names. The important design rule is that canonical names are plain Python-like
strings and display LaTeX is always derived from those names.

The tests deliberately use the new canonical import path
``gu_toolkit.identifiers`` so the directory layout itself becomes part of the
specification. A small compatibility check at the end protects the legacy
import path during migration.
"""

from __future__ import annotations

import pytest

from gu_toolkit.identifier_policy import validate_identifier as legacy_validate_identifier
from gu_toolkit.identifiers import (
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
def test_validate_identifier_accepts_documented_canonical_examples(name: str) -> None:
    """Canonical names should already be valid storage representations."""

    assert validate_identifier(name) == name


@pytest.mark.parametrize(
    "name",
    ["", "1x", r"\theta", "x y", "x+y", "x{1}", "a-b"],
)
def test_validate_identifier_rejects_noncanonical_spellings(name: str) -> None:
    """Raw LaTeX, whitespace, and punctuation must fail fast and clearly."""

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
def test_identifier_to_latex_matches_documented_examples(name: str, latex: str) -> None:
    """The renderer should teach users how canonical spelling becomes display LaTeX."""

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
def test_function_head_to_latex_matches_documented_examples(name: str, latex: str) -> None:
    """Function heads share the same canonical grammar but render differently."""

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
def test_parse_identifier_recovers_documented_examples(text: str, canonical: str) -> None:
    """The parser should map explicit display spellings back to canonical storage names."""

    assert parse_identifier(text) == canonical


@pytest.mark.parametrize(
    "canonical",
    ["x", "theta", "velocity", "a_1_2", "theta__x", "x_theta__i_j", "Force", "Force_t", "Force__x"],
)
def test_identifier_round_trips_between_canonical_and_display_forms(canonical: str) -> None:
    """Rendering and parsing should be reversible for the documented naming surface."""

    latex = identifier_to_latex(canonical) if canonical[0].islower() else function_head_to_latex(canonical)
    assert parse_identifier(latex) == canonical


def test_legacy_identifier_policy_import_reexports_the_canonical_helper() -> None:
    """Older imports should still work while the codebase migrates to subpackages."""

    assert legacy_validate_identifier is validate_identifier
    assert legacy_validate_identifier("theta__x") == "theta__x"
