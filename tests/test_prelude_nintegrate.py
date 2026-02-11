from __future__ import annotations

import math

import sympy as sp

from prelude import NIntegrate


def test_nintegrate_finite_interval() -> None:
    x = sp.Symbol("x")
    result = NIntegrate(x**2, (x, 0, 1))
    assert math.isclose(result, 1.0 / 3.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_infinite_interval() -> None:
    x = sp.Symbol("x")
    result = NIntegrate(sp.exp(-x), (x, 0, sp.oo))
    assert math.isclose(result, 1.0, rel_tol=1e-9, abs_tol=1e-11)
