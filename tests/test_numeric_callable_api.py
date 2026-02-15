from __future__ import annotations

import inspect
from collections.abc import Iterator, Mapping
from importlib import import_module

import numpy as np
import sympy as sp

numpify_module = import_module("gu_toolkit.numpify")


class _LookupOnlyCtx(Mapping[sp.Symbol, float]):
    """Context provider that only supports key lookup semantics."""

    def __init__(self, values: Mapping[sp.Symbol, float]):
        self._cells = {k: [float(v)] for k, v in values.items()}

    def set_value(self, key: sp.Symbol, value: float) -> None:
        self._cells[key][0] = float(value)

    def __getitem__(self, key: sp.Symbol) -> float:
        return self._cells[key][0]

    def __iter__(self) -> Iterator[sp.Symbol]:
        return iter(self._cells)

    def __len__(self) -> int:
        return len(self._cells)


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


def test_numeric_function_can_wrap_pure_python_callable_without_symbolic() -> None:
    x, a, b = sp.symbols("x a b")

    def pure_python_callable(xparam, yparam, zparam):
        return xparam + yparam * zparam

    nf = numpify_module.NumericFunction(
        pure_python_callable,
        vars=(x, {"yparam": a, "zparam": b}),
    )

    assert nf.symbolic is None
    assert nf.vars() == (x, {"yparam": a, "zparam": b})
    assert tuple(nf.vars) == (x,)
    assert nf(2, yparam=3, zparam=4) == 14


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


def test_vars_named_parameter_semantics_for_numeric_function_constructor() -> None:
    x, a, b = sp.symbols("x a b")

    def f(xparam, yparam, zparam):
        return 10 * xparam + yparam - zparam

    nf = numpify_module.NumericFunction(
        f,
        vars=(x, {"yparam": a, "zparam": b}),
    )

    assert nf.name_for_symbol[x] == "x"
    assert nf.name_for_symbol[a] == "a"
    assert nf.name_for_symbol[b] == "b"
    assert nf(5, yparam=9, zparam=4) == 55


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


def test_dynamic_parameter_context_uses_lookup_only_mapping() -> None:
    x, a = sp.symbols("x a")
    compiled = numpify_module.numpify(a * x, vars=(x, a), cache=False)
    ctx = _LookupOnlyCtx({a: 2.0})
    dynamic = compiled.set_parameter_context(ctx).freeze({a: numpify_module.DYNAMIC_PARAMETER})

    assert dynamic(3.0) == 6.0
    ctx.set_value(a, 4.0)
    assert dynamic(3.0) == 12.0


def test_signature_and_free_var_tracking_with_keyed_tail() -> None:
    x, y, s = sp.symbols("x y s")
    compiled = numpify_module.numpify(x + y * s, vars=(x, {"y": y, "scale": s}), cache=False)

    assert str(inspect.signature(compiled)) == "(x, y, s, /)"

    dynamic = compiled.freeze({y: numpify_module.DYNAMIC_PARAMETER, s: 5.0})
    assert dynamic.free_vars == (x,)
    assert dynamic.free_var_signature == ((x, "x"),)
    assert str(inspect.signature(dynamic)) == "(x, /)"


def test_keyed_calling_validation_errors() -> None:
    x, y, s = sp.symbols("x y s")
    compiled = numpify_module.numpify(x + y * s, vars=(x, {"y": y, "scale": s}), cache=False)

    try:
        compiled(2, y=3)
    except TypeError as exc:
        assert "Missing keyed argument" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected missing keyed argument error")

    try:
        compiled(2, y=3, scale=4, nope=1)
    except TypeError as exc:
        assert "Unknown keyed argument" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected unknown keyed argument error")


def test_freeze_accepts_symbol_name_or_key_aliases() -> None:
    x, a = sp.symbols("x a")
    compiled = numpify_module.numpify(a * x, vars=(x, {"alpha": a}), cache=False)

    by_name = compiled.freeze(a=2.0)
    by_key = compiled.freeze(alpha=3.0)

    assert by_name(4.0) == 8.0
    assert by_key(4.0) == 12.0


def test_numeric_function_repr_mentions_numeric_function_name() -> None:
    x = sp.Symbol("x")
    compiled = numpify_module.numpify(x + 1, vars=x, cache=False)
    assert "NumericFunction" in repr(compiled)


def test_compiled_numeric_function_supports_vectorized_output() -> None:
    x, a = sp.symbols("x a")
    compiled = numpify_module.numpify(a * x, vars=(x, a), cache=False).freeze({a: 2.5})
    values = compiled(np.array([1.0, 2.0, 4.0]))
    assert np.allclose(values, np.array([2.5, 5.0, 10.0]))
