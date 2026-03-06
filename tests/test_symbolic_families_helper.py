import inspect

import sympy as sp

from gu_toolkit.Symbolic import FunctionFamily, SymbolFamily, symbols


def test_symbols_signature_matches_sympy_symbols():
    assert inspect.signature(symbols) == inspect.signature(sp.symbols)


def test_symbols_returns_tuple_for_multiple_names():
    x, y = symbols("x y")

    assert isinstance(x, SymbolFamily)
    assert isinstance(y, SymbolFamily)
    assert x[1] == sp.Symbol("x_1")
    assert y[2] == sp.Symbol("y_2")


def test_symbols_returns_single_for_one_name_and_assumptions():
    n = symbols("n", integer=True)

    assert isinstance(n, SymbolFamily)
    assert n[4].is_integer is True


def test_symbols_function_cls_creates_function_families():
    f, g = symbols("f, g", cls=sp.Function)

    assert isinstance(f, FunctionFamily)
    assert isinstance(g, FunctionFamily)
    t = sp.Symbol("t")
    assert str(f(t)) == "f(t)"
    assert str(g[0](t)) == "g_0(t)"


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
