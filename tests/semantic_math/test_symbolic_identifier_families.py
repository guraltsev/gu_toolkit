"""Higher-level symbolic helpers must reuse the identifier policy.

The low-level identifier layer is only useful if the convenient symbolic APIs
obey the same rules. These tests make that contract explicit for
``SymbolFamily``, ``FunctionFamily``, and ``symbols``.
"""

from __future__ import annotations

import inspect

import pytest
import sympy as sp

from gu_toolkit.identifiers import IdentifierError
from gu_toolkit.mathlive import ExpressionContext
from gu_toolkit.Symbolic import FunctionFamily, SymbolFamily, symbols


def test_symbols_signature_matches_sympy_symbols() -> None:
    """The helper should stay drop-in compatible with SymPy's ``symbols`` signature."""

    assert inspect.signature(symbols) == inspect.signature(sp.symbols)


@pytest.mark.parametrize("name", ["x", "alpha", "theta__x"])
def test_symbol_family_keeps_canonical_root_names(name: str) -> None:
    """Family roots should store canonical names exactly as validated."""

    family = SymbolFamily(name)
    assert family.name == name


def test_symbol_family_index_names_use_canonical_identifier_encoding() -> None:
    """Integer indices should become canonical underscore atoms."""

    a = SymbolFamily("a")

    assert a[3].name == "a_3"
    assert a[sp.Integer(7)].name == "a_7"
    assert a[1, 2].name == "a_1_2"


def test_symbol_family_string_indices_escape_literal_underscores() -> None:
    """String indices should preserve literal underscores by doubling them."""

    a = SymbolFamily("a")

    assert a["str"].name == "a_str"
    assert a[1, "theta_i"].name == "a_1_theta__i"


def test_symbol_family_rendering_uses_identifier_policy() -> None:
    """Rendering a family member should still go through the canonical identifier renderer."""

    alpha = SymbolFamily("alpha")
    x1 = SymbolFamily("x")[1]
    ctx = ExpressionContext.from_symbols([alpha, x1])

    assert ctx.render_latex(alpha) == r"\alpha"
    assert ctx.render_latex(x1) == r"x_{1}"


def test_symbols_returns_tuple_for_multiple_names() -> None:
    """Multi-name input should preserve SymPy's output shape while upgrading the element type."""

    x, alpha = symbols("x alpha")

    assert isinstance(x, SymbolFamily)
    assert isinstance(alpha, SymbolFamily)
    assert x[1].name == "x_1"
    assert alpha[2].name == "alpha_2"


def test_symbols_returns_single_for_one_name_and_assumptions() -> None:
    """Assumptions should flow through to generated family members."""

    n = symbols("n", integer=True)

    assert isinstance(n, SymbolFamily)
    assert n[4].is_integer is True
    assert n[4].name == "n_4"


def test_function_family_keeps_single_letter_names_plain() -> None:
    r"""Single-letter function heads should render without an ``\operatorname`` wrapper."""

    f = FunctionFamily("f")
    t = sp.Symbol("t")

    assert f.name == "f"
    assert f[0].name == "f_0"
    assert sp.latex(f(t)) == "f(t)"
    assert sp.latex(f[0](t)) == "f_{0}(t)"


def test_function_family_uses_semantic_latex_for_multi_letter_names() -> None:
    """Multi-letter function names should render as readable operators."""

    foo = FunctionFamily("foo")
    t = sp.Symbol("t")

    assert foo.name == "foo"
    assert foo[2].name == "foo_2"
    assert sp.latex(foo(t)) == r"\operatorname{foo}(t)"
    assert sp.latex(foo[2](t)) == r"\operatorname{foo}_{2}(t)"


def test_function_family_converts_greek_names_to_latex_macros() -> None:
    """Greek canonical names should still render as proper LaTeX macros."""

    alpha = FunctionFamily("alpha")
    t = sp.Symbol("t")

    assert alpha.name == "alpha"
    assert alpha[3].name == "alpha_3"
    assert sp.latex(alpha(t)) == r"\alpha(t)"


def test_symbols_function_cls_creates_function_families_with_canonical_names() -> None:
    """Passing ``cls=sp.Function`` should upgrade the result to ``FunctionFamily`` objects."""

    f, foo = symbols("f foo", cls=sp.Function)

    assert isinstance(f, FunctionFamily)
    assert isinstance(foo, FunctionFamily)
    assert f.name == "f"
    assert foo.name == "foo"


def test_symbols_supports_seq_keyword_shape() -> None:
    """The SymPy-style ``seq=True`` shape contract should stay intact."""

    (x,) = symbols("x", seq=True)
    assert isinstance(x, SymbolFamily)


def test_symbols_supports_sympy_cls_passthrough() -> None:
    """Unrecognized ``cls`` values should fall back to SymPy's native behavior."""

    x = symbols("x", cls=sp.Dummy)
    assert isinstance(x, sp.Dummy)


def test_symbols_invalid_empty_names_raises() -> None:
    """Whitespace-only input should still fail the same way SymPy would fail missing names."""

    with pytest.raises(ValueError):
        symbols("   ")


@pytest.mark.parametrize(
    "constructor, bad_name",
    [
        (SymbolFamily, r"\theta"),
        (SymbolFamily, "1x"),
        (FunctionFamily, r"\operatorname{Force}"),
        (FunctionFamily, "1Force"),
    ],
)
def test_symbolic_family_constructors_reuse_identifier_validation(constructor, bad_name: str) -> None:
    """Family constructors should fail with ``IdentifierError`` for noncanonical spellings."""

    with pytest.raises(IdentifierError):
        constructor(bad_name)


@pytest.mark.parametrize("bad_name", [r"\theta", "1x"])
def test_symbols_helper_raises_identifier_error_for_bad_symbol_identifiers(bad_name: str) -> None:
    """The convenience ``symbols`` helper should expose the same identifier rules to notebook users."""

    with pytest.raises(IdentifierError):
        symbols(bad_name)
