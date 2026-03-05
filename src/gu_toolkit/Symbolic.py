"""Symbolic convenience helpers used throughout the notebook-facing API.

The :mod:`gu_toolkit.Symbolic` module provides lightweight wrappers around
core SymPy constructs to make interactive expression authoring concise and
readable:

* :class:`SymbolFamily` creates a *family* of symbols that can be indexed via
  ``[]`` while preserving SymPy assumptions.
* :class:`FunctionFamily` creates indexed SymPy undefined functions and also
  behaves like a callable base function.
* :class:`Infix` and the predefined operator instances (:data:`eq`,
  :data:`lt`, :data:`le`, :data:`gt`, :data:`ge`) provide pipe-based infix
  syntax such as ``a |eq| b`` for relational construction.

All helpers are deterministic and internally cached by index tuple, so
repeating the same index returns the same symbolic object instance.
"""

from __future__ import annotations

import sympy as sp


class SymbolFamily(sp.Symbol):
    """A SymPy symbol that lazily creates indexed child symbols.

    Parameters
    ----------
    name:
        Base symbol name used for the family root (for example ``"x"``).
    **kwargs:
        SymPy symbol assumptions (for example ``integer=True`` or
        ``positive=True``). The same assumptions are propagated to all indexed
        children produced by :meth:`__getitem__`.

    Notes
    -----
    * ``SymbolFamily`` is itself a valid SymPy symbol and can be used directly
      in expressions.
    * Indexed children are named ``"{base}_{i,j,...}"`` where the index values
      are converted with :class:`str` and joined by commas.
    * Child objects are cached per index tuple, so ``x[1] is x[1]`` is ``True``.

    Examples
    --------
    >>> x = SymbolFamily("x")
    >>> x[0]
    x_0
    >>> x[1, 2]
    x_1,2
    >>> n = SymbolFamily("n", integer=True)
    >>> n[3].is_integer
    True
    """

    def __new__(cls, name, **kwargs):
        """Create the family root symbol and initialize child caches."""
        obj = super().__new__(cls, name, **kwargs)
        obj._family_cache = {}
        obj._family_kwargs = kwargs
        return obj

    def __getitem__(self, k):
        """Return an indexed child symbol from this family.

        Parameters
        ----------
        k:
            A single index value or a tuple of index values.

        Returns
        -------
        sympy.Symbol
            Cached or newly-created child symbol named with ``self.name`` and
            the provided indices.
        """
        if not isinstance(k, tuple):
            k = (k,)
        if k not in self._family_cache:
            sub = ",".join(map(str, k))
            child_name = f"{self.name}_{sub}"
            self._family_cache[k] = sp.Symbol(child_name, **self._family_kwargs)
        return self._family_cache[k]


class FunctionFamily:
    """A family of SymPy undefined functions supporting indexed lookup.

    Parameters
    ----------
    name:
        Base function name used for the root function and indexed variants.
    **kwargs:
        Optional keyword arguments forwarded to :func:`sympy.Function`.

    Notes
    -----
    * Calling the family object directly (for example ``f(x)``) delegates to
      the base function ``Function(name)``.
    * Indexing creates function symbols named ``"{base}_{i,j,...}"``.
    * Function symbols are cached by index tuple.

    Examples
    --------
    >>> f = FunctionFamily("f")
    >>> f(sp.Symbol("x"))
    f(x)
    >>> f[1](sp.Symbol("x"))
    f_1(x)
    """

    def __init__(self, name, **kwargs):
        """Initialize the base function and index cache."""
        self.name = name
        self._kwargs = kwargs
        self._base = sp.Function(name, **kwargs)
        self._cache = {}

    def __getitem__(self, k):
        """Return an indexed function symbol for ``k``.

        Parameters
        ----------
        k:
            A single index value or a tuple of index values.

        Returns
        -------
        sympy.FunctionClass
            Cached or newly-created undefined function class.
        """
        if not isinstance(k, tuple):
            k = (k,)
        if k not in self._cache:
            sub = ",".join(map(str, k))
            self._cache[k] = sp.Function(f"{self.name}_{sub}", **self._kwargs)
        return self._cache[k]

    def __call__(self, *args):
        """Call the base undefined function with positional arguments."""
        return self._base(*args)

    def _sympy_(self):
        """Return the wrapped SymPy object for SymPy protocol interop."""
        return self._base

    def __str__(self):
        """Return the string representation of the base function."""
        return str(self._base)

    def __repr__(self):
        """Return the repr of the base function."""
        return repr(self._base)


class Infix:
    """Pipe-based infix operator adapter.

    ``Infix`` wraps a two-argument callable so it can be used with the ``|``
    operator:

    ``left |Infix(func)| right``  -> ``func(left, right)``.

    Parameters
    ----------
    func:
        Callable that accepts ``(left, right)`` and returns a value.
    """

    __slots__ = ("func",)

    def __init__(self, func):
        """Store the callable used to evaluate infix expressions."""
        self.func = func

    def __ror__(self, left):
        """Capture the left operand and return a partial infix object."""
        return _InfixPartial(self.func, left)


class _InfixPartial:
    """Internal helper that stores the left-hand operand for :class:`Infix`."""

    __slots__ = ("func", "left")

    def __init__(self, func, left):
        self.func = func
        self.left = left

    def __or__(self, right):
        """Apply the wrapped binary callable to ``(left, right)``."""
        return self.func(self.left, right)


#: Infix wrapper for :func:`sympy.Eq`.
eq = Infix(sp.Eq)
#: Infix wrapper for :func:`sympy.Lt`.
lt = Infix(sp.Lt)
#: Infix wrapper for :func:`sympy.Le`.
le = Infix(sp.Le)
#: Infix wrapper for :func:`sympy.Gt`.
gt = Infix(sp.Gt)
#: Infix wrapper for :func:`sympy.Ge`.
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
