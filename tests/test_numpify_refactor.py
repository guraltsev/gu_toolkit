from __future__ import annotations

import inspect
from collections.abc import Iterator, Mapping

import sympy as sp
from importlib import import_module

numpify_module = import_module("gu_toolkit.numpify")


class _Cell:
    def __init__(self, value):
        self.value = value


class _Ctx(Mapping[sp.Symbol, float]):
    """Simple live parameter provider used by NumericFunction tests."""

    def __init__(self, mapping):
        self.parameters = {k: _Cell(v) for k, v in mapping.items()}

    def __getitem__(self, key: sp.Symbol) -> float:
        return self.parameters[key].value

    def __iter__(self) -> Iterator[sp.Symbol]:
        return iter(self.parameters)

    def __len__(self) -> int:
        return len(self.parameters)

def test_identifier_mangling_and_collision() -> None:
    a = sp.Symbol("lambda")
    b = sp.Symbol("x-y")
    c1 = sp.Symbol("x", real=True)
    c2 = sp.Symbol("x", integer=True)

    f = numpify_module.numpify(a + b + c1 + c2, vars=(a, b, c1, c2), cache=False)
    assert f.var_names[0].startswith("lambda")
    assert all(name.isidentifier() for name in f.var_names)
    assert len(set(f.var_names)) == len(f.var_names)
    assert f(1, 2, 3, 4) == 10


def test_dynamic_parameter_context_and_unfreeze() -> None:
    x, a = sp.symbols("x a")
    f = numpify_module.numpify(a * x, vars=(x, a), cache=False)
    ctx = _Ctx({a: 2.0})
    bound = f.set_parameter_context(ctx).freeze({a: numpify_module.DYNAMIC_PARAMETER})

    assert bound(3.0) == 6.0
    ctx.parameters[a].value = 4.0
    assert bound(3.0) == 12.0

    unbound = bound.unfreeze(a)
    assert unbound(3.0, 5.0) == 15.0

def test_unfreeze_without_keys_unfreezes_all_nonfree_vars() -> None:
    x, a, b = sp.symbols("x a b")
    f = numpify_module.numpify(a * x + b, vars=(x, a, b), cache=False)
    ctx = _Ctx({a: 2.0, b: 3.0})
    bound = f.set_parameter_context(ctx).freeze(
        {a: numpify_module.DYNAMIC_PARAMETER, b: numpify_module.DYNAMIC_PARAMETER}
    )

    unbound = bound.unfreeze()
    assert unbound(2.0, 4.0, 5.0) == 13.0


def test_dynamic_missing_context_errors() -> None:
    x, a = sp.symbols("x a")
    f = numpify_module.numpify(a * x, vars=(x, a), cache=False).freeze(
        {a: numpify_module.DYNAMIC_PARAMETER}
    )

    try:
        f(1.0)
    except ValueError as exc:
        assert "requires parameter_context" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected dynamic-parameter error")


def test_signature_tracks_freeze_and_unfreeze() -> None:
    x, a, b = sp.symbols("x a b")
    f = numpify_module.numpify(a * x + b, vars=(x, a, b), cache=False)
    assert str(inspect.signature(f)) == "(x, a, b, /)"

    dynamic = f.freeze(
        {a: numpify_module.DYNAMIC_PARAMETER, b: numpify_module.DYNAMIC_PARAMETER}
    )
    assert str(inspect.signature(dynamic)) == "(x, /)"

    unbound = dynamic.unfreeze()
    assert str(inspect.signature(unbound)) == "(x, a, b, /)"
    assert unbound(2.0, 3.0, 4.0) == 10.0
