"""Property-based regression tests for Project 005 testing-infrastructure goals.

These tests exercise numeric edge-case behavior for conversion and callable
construction helpers to increase confidence beyond example-based unit tests.
"""

from __future__ import annotations

import math
from importlib import import_module

import numpy as np
import pytest
import sympy as sp

InputConvert = import_module("gu_toolkit.InputConvert").InputConvert
numpify = import_module("gu_toolkit.numpify").numpify

try:
    from hypothesis import given
    from hypothesis import strategies as st
except ModuleNotFoundError:  # pragma: no cover - environment-specific fallback
    pytest.skip("hypothesis is required for property-based tests", allow_module_level=True)


FINITE_FLOATS = st.floats(allow_nan=False, allow_infinity=False, width=64)
# Keep numpify parity checks away from IEEE-754 overflow boundaries so failures
# indicate semantic mismatches rather than backend-dependent overflow behavior.
SAFE_NUMPIFY_FLOATS = st.floats(
    min_value=-1e150,
    max_value=1e150,
    allow_nan=False,
    allow_infinity=False,
    width=64,
)
NONZERO_FINITE_FLOATS = st.floats(
    allow_nan=False,
    allow_infinity=False,
    width=64,
).filter(lambda x: x != 0.0)


@given(value=FINITE_FLOATS)
def test_inputconvert_float_roundtrip_for_finite_reals(value: float) -> None:
    """Finite real inputs should round-trip through float conversion."""
    result = InputConvert(value, float, truncate=False)
    assert math.isfinite(result)
    assert result == value


@given(real=FINITE_FLOATS, imag=NONZERO_FINITE_FLOATS)
def test_inputconvert_complex_rejects_nonreal_without_truncation(
    real: float, imag: float
) -> None:
    """Complex -> float conversion must fail when imaginary part is non-zero."""
    with pytest.raises(ValueError, match="imaginary part is non-zero"):
        InputConvert(complex(real, imag), float, truncate=False)


@given(real=FINITE_FLOATS, imag=NONZERO_FINITE_FLOATS)
def test_inputconvert_complex_truncates_to_real_projection(
    real: float, imag: float
) -> None:
    """Complex -> float conversion should project to the real part when truncating."""
    result = InputConvert(complex(real, imag), float, truncate=True)
    assert result == pytest.approx(real)


@given(x_value=SAFE_NUMPIFY_FLOATS, y_value=SAFE_NUMPIFY_FLOATS)
def test_numpify_matches_symbolic_expression_for_scalar_inputs(
    x_value: float, y_value: float
) -> None:
    """Scalar numeric callables should match direct symbolic evaluation."""
    x, y = sp.symbols("x y")
    expr = x**2 + 2 * y - 3
    numeric = numpify(expr, vars=(x, y), cache=False)

    observed = numeric(x_value, y_value)
    expected = float(expr.subs({x: x_value, y: y_value}).evalf())

    assert observed == pytest.approx(expected)


@given(values=st.lists(SAFE_NUMPIFY_FLOATS, min_size=1, max_size=20))
def test_numpify_vectorized_callable_tracks_numpy_baseline(values: list[float]) -> None:
    """Vectorized single-variable callables should agree with NumPy baselines."""
    x = sp.Symbol("x")
    expr = x**2 + 2 * x + 1
    numeric = numpify(expr, vars=(x,), cache=False)

    arr = np.asarray(values, dtype=float)
    observed = numeric(arr)
    expected = arr**2 + 2 * arr + 1

    assert isinstance(observed, np.ndarray)
    np.testing.assert_allclose(observed, expected)
