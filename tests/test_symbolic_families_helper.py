import inspect

import sympy as sp

from gu_toolkit.Symbolic import FunctionFamily, SymbolFamily, symbols


def test_symbols_signature_matches_sympy_symbols():
    assert inspect.signature(symbols) == inspect.signature(sp.symbols)


def test_symbol_family_uses_latex_based_root_names():
    x = SymbolFamily("x")
    alpha = SymbolFamily("alpha")

    assert x.name == "x"
    assert alpha.name == r"\alpha"


def test_symbol_family_index_names_use_braces_and_normalized_integers():
    a = SymbolFamily("a")

    assert a[3].name == "a_{3}"
    assert a[sp.Integer(7)].name == "a_{7}"
    assert a[1, 2].name == "a_{1,2}"


def test_symbol_family_string_indices_render_with_text():
    a = SymbolFamily("a")

    assert a["str"].name == r"a_{\text{str}}"
    assert a[1, "str"].name == r"a_{1,\text{str}}"


def test_symbols_returns_tuple_for_multiple_names():
    x, alpha = symbols("x alpha")

    assert isinstance(x, SymbolFamily)
    assert isinstance(alpha, SymbolFamily)
    assert x[1].name == "x_{1}"
    assert alpha[2].name == r"\alpha_{2}"


def test_symbols_returns_single_for_one_name_and_assumptions():
    n = symbols("n", integer=True)

    assert isinstance(n, SymbolFamily)
    assert n[4].is_integer is True
    assert n[4].name == "n_{4}"


def test_function_family_keeps_single_letter_names_plain():
    f = FunctionFamily("f")
    t = sp.Symbol("t")

    assert f.name == "f"
    assert f[0].name == "f_{0}"
    assert sp.latex(f(t)) == "f(t)"
    assert sp.latex(f[0](t)) == "f_{0}(t)"


def test_function_family_wraps_multi_letter_plain_names_in_operatorname():
    foo = FunctionFamily("foo")
    t = sp.Symbol("t")

    assert foo.name == r"\operatorname{foo}"
    assert foo[2].name == r"\operatorname{foo}_{2}"
    assert sp.latex(foo(t)) == r"\operatorname{foo}(t)"
    assert sp.latex(foo[2](t)) == r"\operatorname{foo}_{2}(t)"


def test_function_family_preserves_explicit_operatorname_without_double_wrapping():
    opf = FunctionFamily(r"\operatorname{f}")
    t = sp.Symbol("t")

    assert opf.name == r"\operatorname{f}"
    assert opf[1].name == r"\operatorname{f}_{1}"
    assert sp.latex(opf(t)) == r"\operatorname{f}(t)"


def test_function_family_converts_greek_names_to_latex_macros():
    alpha = FunctionFamily("alpha")
    t = sp.Symbol("t")

    assert alpha.name == r"\alpha"
    assert alpha[3].name == r"\alpha_{3}"
    assert sp.latex(alpha(t)) == r"\alpha(t)"


def test_symbols_function_cls_creates_function_families_with_latex_names():
    f, foo = symbols("f foo", cls=sp.Function)

    assert isinstance(f, FunctionFamily)
    assert isinstance(foo, FunctionFamily)
    assert f.name == "f"
    assert foo.name == r"\operatorname{foo}"


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
