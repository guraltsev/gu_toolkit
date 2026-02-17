"""Project 005 regression and coverage tests for test infrastructure gaps.

These tests intentionally target historically under-covered utility helpers called
out in the project roadmap to keep coverage progress aligned with documented
infrastructure goals.
"""

from __future__ import annotations

from importlib import import_module

import pytest
import sympy as sp

InputConvert = import_module("gu_toolkit.InputConvert").InputConvert
ParameterSnapshot = import_module("gu_toolkit.ParameterSnapshot").ParameterSnapshot
_normalize_vars = import_module("gu_toolkit.numpify")._normalize_vars


def test_inputconvert_complex_to_real_respects_truncate_flag() -> None:
    """Complex-to-real conversion should truncate only when explicitly allowed."""
    assert InputConvert(3 + 4j, float, truncate=True) == pytest.approx(3.0)

    with pytest.raises(ValueError, match="Could not convert"):
        InputConvert(3 + 4j, float, truncate=False)


def test_inputconvert_int_exactness_and_string_sympy_path() -> None:
    """Int conversion should enforce exactness and support symbolic strings."""
    with pytest.raises(ValueError, match="Could not convert"):
        InputConvert("2.25", int, truncate=False)

    assert InputConvert("sqrt(16)", int, truncate=False) == 4


def test_parameter_snapshot_name_resolution_and_ambiguity() -> None:
    """String lookup should work for unambiguous names and fail when ambiguous."""
    x_real = sp.Symbol("x", real=True)
    y = sp.Symbol("y")
    snapshot = ParameterSnapshot(
        {
            x_real: {"value": 2.0, "min": -1.0, "max": 3.0},
            y: {"value": 5.0, "min": 0.0, "max": 10.0},
        }
    )

    assert snapshot["x"]["value"] == 2.0
    assert snapshot.value_map()["y"] == 5.0

    x_positive = sp.Symbol("x", positive=True)
    ambiguous_snapshot = ParameterSnapshot(
        {
            x_real: {"value": 1.0},
            x_positive: {"value": 2.0},
        }
    )

    with pytest.raises(KeyError, match="Ambiguous parameter name"):
        _ = ambiguous_snapshot["x"]


def test_normalize_vars_mapping_and_tuple_plus_mapping_forms() -> None:
    """Variable-spec normalization should preserve positional and keyed contracts."""
    x, y, z = sp.symbols("x y z")
    expr = x + y + z

    mapping_result = _normalize_vars(expr, {0: x, 1: y, "gain": z})
    assert mapping_result["all"] == (x, y, z)
    assert mapping_result["keyed"] == (("gain", z),)

    tuple_mapping_result = _normalize_vars(expr, (x, y, {"gain": z}))
    assert tuple_mapping_result["all"] == (x, y, z)
    assert tuple_mapping_result["keyed"] == (("gain", z),)


def test_normalize_vars_rejects_invalid_specs() -> None:
    """Invalid vars specs should raise informative validation errors."""
    x, y = sp.symbols("x y")
    expr = x + y

    with pytest.raises(ValueError, match="contiguous and start at 0"):
        _normalize_vars(expr, {0: x, 2: y})

    with pytest.raises(ValueError, match="Duplicate symbol"):
        _normalize_vars(expr, (x, {"alias": x}))
