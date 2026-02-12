from __future__ import annotations

import importlib.util
from pathlib import Path

import sympy as sp


def _import_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Cell:
    def __init__(self, value):
        self.value = value


class _Ctx:
    def __init__(self, mapping):
        self.parameters = {k: _Cell(v) for k, v in mapping.items()}


def test_identifier_mangling_and_collision() -> None:
    mod = _import_module_from_path("numpify", Path("numpify.py"))

    a = sp.Symbol("lambda")
    b = sp.Symbol("x-y")
    c1 = sp.Symbol("x", real=True)
    c2 = sp.Symbol("x", integer=True)

    f = mod.numpify(a + b + c1 + c2, parameters=(a, b, c1, c2), cache=False)
    assert f.parameter_names[0].startswith("lambda")
    assert all(name.isidentifier() for name in f.parameter_names)
    assert len(set(f.parameter_names)) == len(f.parameter_names)
    assert f(1, 2, 3, 4) == 10


def test_dynamic_parameter_context_and_unfreeze() -> None:
    mod = _import_module_from_path("numpify", Path("numpify.py"))

    x, a = sp.symbols("x a")
    f = mod.numpify(a * x, parameters=(x, a), cache=False)
    ctx = _Ctx({a: 2.0})
    bound = f.set_parameter_context(ctx).freeze({a: mod.DYNAMIC_PARAMETER})

    assert bound(3.0) == 6.0
    ctx.parameters[a].value = 4.0
    assert bound(3.0) == 12.0

    unbound = bound.unfreeze(a)
    assert unbound(3.0, 5.0) == 15.0


def test_dynamic_missing_context_errors() -> None:
    mod = _import_module_from_path("numpify", Path("numpify.py"))

    x, a = sp.symbols("x a")
    f = mod.numpify(a * x, parameters=(x, a), cache=False).freeze({a: mod.DYNAMIC_PARAMETER})

    try:
        f(1.0)
    except ValueError as exc:
        assert "requires parameter_context" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected dynamic-parameter error")
