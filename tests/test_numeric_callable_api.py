from __future__ import annotations

import sympy as sp
import gu_toolkit.numpify as numpify_module


def test_numpify_returns_numeric_function_with_symbolic() -> None:
    x = sp.Symbol("x")
    out = numpify_module.numpify(x + 1, vars=x, cache=False)
    assert isinstance(out, numpify_module.NumericFunction)
    assert out.symbolic == x + 1


def test_legacy_numpified_function_defaults_symbolic_none() -> None:
    x = sp.Symbol("x")
    legacy = numpify_module.NumpifiedFunction(lambda v: v + 2, vars=(x,))
    assert isinstance(legacy, numpify_module.NumericFunction)
    assert legacy.symbolic is None
    assert legacy(3) == 5


def test_vars_roundtrip_and_mixed_calling_modes() -> None:
    x, y, s = sp.symbols("x y s")
    fn = numpify_module.numpify(x + y * s, vars=(x, {"y": y, "scale": s}), cache=False)

    assert fn.vars() == (x, {"y": y, "scale": s})
    assert tuple(fn.vars) == (x,)
    assert fn(2, y=3, scale=4) == 14


def test_mapping_with_integer_slots_roundtrip_and_call() -> None:
    x, y, s = sp.symbols("x y s")
    spec = {0: x, 1: y, "scale": s}
    fn = numpify_module.numpify(x + y * s, vars=spec, cache=False)

    assert fn.vars() == spec
    assert tuple(fn.vars) == (x, y)
    assert fn(2, 3, scale=4) == 14


def test_integer_mapping_keys_must_be_contiguous() -> None:
    x, y = sp.symbols("x y")
    try:
        numpify_module.numpify(x + y, vars={0: x, 2: y}, cache=False)
    except ValueError as exc:
        assert "contiguous" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected contiguity validation failure")


def test_freeze_unfreeze_parity_for_legacy_and_numeric() -> None:
    x, a = sp.symbols("x a")
    compiled = numpify_module.numpify(a * x, vars=(x, a), cache=False)

    via_numeric = compiled.freeze({a: 2})
    via_legacy = numpify_module.NumpifiedFunction(
        compiled._fn,
        vars=(x, a),
        symbolic=compiled.symbolic,
        call_signature=compiled.call_signature,
        source=compiled.source,
    ).freeze({a: 2})

    assert via_numeric(3) == via_legacy(3) == 6
    assert via_numeric.unfreeze(a)(3, 4) == via_legacy.unfreeze(a)(3, 4) == 12
