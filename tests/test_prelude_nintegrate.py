from __future__ import annotations

import math

import numpy as np
import sympy as sp

from prelude import NIntegrate, NReal_Fourier_Series


def test_nintegrate_finite_interval() -> None:
    x = sp.Symbol("x")
    result = NIntegrate(x**2, (x, 0, 1))
    assert math.isclose(result, 1.0 / 3.0, rel_tol=1e-10, abs_tol=1e-12)


def test_nintegrate_infinite_interval() -> None:
    x = sp.Symbol("x")
    result = NIntegrate(sp.exp(-x), (x, 0, sp.oo))
    assert math.isclose(result, 1.0, rel_tol=1e-9, abs_tol=1e-11)


def test_nintegrate_sympy_with_binding_dict() -> None:
    x, a = sp.symbols("x a")
    result = NIntegrate(a * x, (x, 0, 1), binding={a: 2})
    assert math.isclose(result, 1.0, rel_tol=1e-10, abs_tol=1e-12)


def test_real_fourier_series_constant() -> None:
    x = sp.Symbol("x")
    cos, sin = NReal_Fourier_Series(3, (x, 0, 2 * sp.pi), samples=1024)
    assert math.isclose(cos[0], 3.0 * math.sqrt(2 * math.pi), rel_tol=1e-3)
    assert np.allclose(cos[1:20], 0.0, atol=1e-8)
    assert np.allclose(sin[1:20], 0.0, atol=1e-8)


def test_real_fourier_series_single_sine_mode() -> None:
    x = sp.Symbol("x")
    cos, sin = NReal_Fourier_Series(sp.sin(3 * x), (x, 0, 2 * sp.pi), samples=1024)
    # L2-normalized sin basis gives coefficient sqrt(pi) on (0, 2pi).
    assert math.isclose(sin[3], math.sqrt(math.pi), rel_tol=2e-2)
    assert np.allclose(cos[:20], 0.0, atol=1e-2)


def test_nintegrate_requires_missing_binding() -> None:
    x, a = sp.symbols("x a")
    try:
        NIntegrate(a * x, (x, 0, 1))
    except ValueError as exc:
        assert "Missing bindings" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError when parameter binding is missing")
