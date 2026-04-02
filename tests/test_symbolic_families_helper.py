import inspect

import sympy as sp

from gu_toolkit.Symbolic import FunctionFamily, SymbolFamily, symbols
from gu_toolkit.expression_context import ExpressionContext


def test_symbols_signature_matches_sympy_symbols():
    assert inspect.signature(symbols) == inspect.signature(sp.symbols)


def test_symbol_family_keeps_canonical_root_names():
    x = SymbolFamily("x")
    alpha = SymbolFamily("alpha")

    assert x.name == "x"
    assert alpha.name == "alpha"


def test_symbol_family_index_names_use_canonical_identifier_encoding():
    a = SymbolFamily("a")

    assert a[3].name == "a_3"
    assert a[sp.Integer(7)].name == "a_7"
    assert a[1, 2].name == "a_1_2"


def test_symbol_family_string_indices_escape_literal_underscores():
    a = SymbolFamily("a")

    assert a["str"].name == "a_str"
    assert a[1, "theta_i"].name == "a_1_theta__i"


def test_symbol_family_rendering_uses_identifier_policy():
    alpha = SymbolFamily("alpha")
    x1 = SymbolFamily("x")[1]
    ctx = ExpressionContext.from_symbols([alpha, x1])

    assert ctx.render_latex(alpha) == r"\alpha"
    assert ctx.render_latex(x1) == r"x_{1}"


def test_symbols_returns_tuple_for_multiple_names():
    x, alpha = symbols("x alpha")

    assert isinstance(x, SymbolFamily)
    assert isinstance(alpha, SymbolFamily)
    assert x[1].name == "x_1"
    assert alpha[2].name == "alpha_2"


def test_symbols_returns_single_for_one_name_and_assumptions():
    n = symbols("n", integer=True)

    assert isinstance(n, SymbolFamily)
    assert n[4].is_integer is True
    assert n[4].name == "n_4"


def test_function_family_keeps_single_letter_names_plain():
    f = FunctionFamily("f")
    t = sp.Symbol("t")

    assert f.name == "f"
    assert f[0].name == "f_0"
    assert sp.latex(f(t)) == "f(t)"
    assert sp.latex(f[0](t)) == "f_{0}(t)"


def test_function_family_uses_semantic_latex_for_multi_letter_names():
    foo = FunctionFamily("foo")
    t = sp.Symbol("t")

    assert foo.name == "foo"
    assert foo[2].name == "foo_2"
    assert sp.latex(foo(t)) == r"\operatorname{foo}(t)"
    assert sp.latex(foo[2](t)) == r"\operatorname{foo}_{2}(t)"


def test_function_family_rejects_noncanonical_latex_names():
    try:
        FunctionFamily(r"\operatorname{f}")
    except Exception as exc:
        assert "match" in str(exc).lower() or "identifier" in str(exc).lower()
    else:
        raise AssertionError("Expected failure for non-canonical function names")


def test_function_family_converts_greek_names_to_latex_macros():
    alpha = FunctionFamily("alpha")
    t = sp.Symbol("t")

    assert alpha.name == "alpha"
    assert alpha[3].name == "alpha_3"
    assert sp.latex(alpha(t)) == r"\alpha(t)"


def test_symbols_function_cls_creates_function_families_with_canonical_names():
    f, foo = symbols("f foo", cls=sp.Function)

    assert isinstance(f, FunctionFamily)
    assert isinstance(foo, FunctionFamily)
    assert f.name == "f"
    assert foo.name == "foo"


def test_symbols_supports_seq_keyword_shape():
    (x,) = symbols("x", seq=True)
    assert isinstance(x, SymbolFamily)


def test_symbols_supports_sympy_cls_passthrough():
    x = symbols("x", cls=sp.Dummy)
    assert isinstance(x, sp.Dummy)


def test_symbols_invalid_empty_names_raises():
    try:
        symbols("   ")
    except ValueError as exc:
        assert "no symbols" in str(exc).lower() or "missing" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for empty names")
