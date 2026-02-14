"""Symbolic extensions for exploratory SymPy usage.

Contains convenience symbolic primitives used by the notebook namespace:
- SymbolFamily / FunctionFamily
- infix relational operators (eq/lt/le/gt/ge)
"""

from __future__ import annotations

import sympy as sp


class SymbolFamily(sp.Symbol):
    """A SymPy Symbol that creates indexed children via ``[]``."""

    def __new__(cls, name, **kwargs):
        obj = super().__new__(cls, name, **kwargs)
        obj._family_cache = {}
        obj._family_kwargs = kwargs
        return obj

    def __getitem__(self, k):
        if not isinstance(k, tuple):
            k = (k,)
        if k not in self._family_cache:
            sub = ",".join(map(str, k))
            child_name = f"{self.name}_{sub}"
            self._family_cache[k] = sp.Symbol(child_name, **self._family_kwargs)
        return self._family_cache[k]


class FunctionFamily:
    """A wrapper for SymPy functions that supports indexed children."""

    def __init__(self, name, **kwargs):
        self.name = name
        self._kwargs = kwargs
        self._base = sp.Function(name, **kwargs)
        self._cache = {}

    def __getitem__(self, k):
        if not isinstance(k, tuple):
            k = (k,)
        if k not in self._cache:
            sub = ",".join(map(str, k))
            self._cache[k] = sp.Function(f"{self.name}_{sub}", **self._kwargs)
        return self._cache[k]

    def __call__(self, *args):
        return self._base(*args)

    def _sympy_(self):
        return self._base

    def __str__(self):
        return str(self._base)

    def __repr__(self):
        return repr(self._base)


class Infix:
    """Generic infix operator used as: ``a |OP| b``."""

    __slots__ = ("func",)

    def __init__(self, func):
        self.func = func

    def __ror__(self, left):
        return _InfixPartial(self.func, left)


class _InfixPartial:
    __slots__ = ("func", "left")

    def __init__(self, func, left):
        self.func = func
        self.left = left

    def __or__(self, right):
        return self.func(self.left, right)


eq = Infix(sp.Eq)
lt = Infix(sp.Lt)
le = Infix(sp.Le)
gt = Infix(sp.Gt)
ge = Infix(sp.Ge)


__all__ = [
    "SymbolFamily",
    "FunctionFamily",
    "Infix",
    "eq",
    "lt",
    "le",
    "gt",
    "ge",
]
