from __future__ import annotations

from unittest.mock import patch

import sympy as sp

from gu_toolkit.ParseLaTeX import parse_latex


def test_parse_latex_falls_back_when_lark_returns_tree() -> None:
    calls: list[str] = []

    def _fake_parse_latex(_tex, *args, backend=None, **kwargs):
        calls.append(backend)
        if backend == "lark":
            return object()
        if backend == "antlr":
            return sp.Symbol("x") + 1
        raise AssertionError("unexpected backend")

    with patch(
        "gu_toolkit.ParseLaTeX._sympy_parse_latex", side_effect=_fake_parse_latex
    ):
        out = parse_latex(r"\\frac{1}{2}x")

    assert out == sp.Symbol("x") + 1
    assert calls == ["lark", "antlr"]
