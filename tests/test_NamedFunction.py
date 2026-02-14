from __future__ import annotations

import sympy as sp
from gu_toolkit.NamedFunction import NamedFunction


def test_docstring_latex_from_sympy_expr() -> None:
    @NamedFunction
    def SquarePlusOne(x):
        """Return x^2 + 1 as a NamedFunction example."""
        return x**2 + 1

    doc = SquarePlusOne.__doc__ or ""
    assert r"\mathrm{SquarePlusOne}(x) = x^{2} + 1" in doc, doc
    assert r"\mathtt{\text{x**2 + 1}}" not in doc, doc


def test_docstring_latex_from_string_expr() -> None:
    @NamedFunction
    def SquarePlusOneStr(x):
        """Return x^2 + 1, but as a string (should still render as math in the docstring)."""
        return "x**2 + 1"

    doc = SquarePlusOneStr.__doc__ or ""
    assert r"\mathrm{SquarePlusOneStr}(x) = x^{2} + 1" in doc, doc
    assert r"\mathtt{\text{x**2 + 1}}" not in doc, doc


def test_expand_definition_rewrite() -> None:
    x = sp.Symbol("x")

    @NamedFunction
    def F(x):
        return x + 1

    expr = F(x).rewrite("expand_definition")
    assert sp.simplify(expr - (x + 1)) == 0, expr


def test_opaque_definition_stays_opaque() -> None:
    x = sp.Symbol("x")

    @NamedFunction
    def G(x):
        return None

    expr = G(x).rewrite("expand_definition")
    assert expr == G(x), expr

