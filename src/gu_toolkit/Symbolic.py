"""Symbolic convenience helpers used throughout the notebook-facing API.

The :mod:`gu_toolkit.Symbolic` module provides lightweight wrappers around
core SymPy constructs to make interactive expression authoring concise and
readable:

* :class:`SymbolFamily` creates a *family* of symbols that can be indexed via
  ``[]`` while preserving SymPy assumptions.
* :class:`FunctionFamily` creates indexed SymPy undefined functions and also
  behaves like a callable base function.
* :func:`symbols` creates one or more symbol/function families from a
  space-separated string, mirroring :func:`sympy.symbols` ergonomics.
* :class:`Infix` and the predefined operator instances (:data:`eq`,
  :data:`lt`, :data:`le`, :data:`gt`, :data:`ge`) provide pipe-based infix
  syntax such as ``a |eq| b`` for relational construction.

Names are normalized into LaTeX-oriented SymPy names by default. This means
Greek identifiers such as ``"alpha"`` become ``"\\alpha"``, indexed symbols
use explicit braces (for example ``x_{1}``), and multi-letter function names
are wrapped in ``\\operatorname{...}`` unless the user already supplied an
explicit LaTeX form.
"""

from __future__ import annotations

from numbers import Integral
from typing import Any

import sympy as sp


def _create_family(factory, source, **kwargs):
    """Create family objects while preserving SymPy's output shape."""

    if isinstance(source, sp.Symbol):
        return factory(source.name, **kwargs)
    if isinstance(source, (tuple, list, set)):
        mapped = (_create_family(factory, item, **kwargs) for item in source)
        return type(source)(mapped)
    return factory(str(source), **kwargs)


def _escape_latex_text(text: str) -> str:
    """Escape plain text for safe use inside ``\text{...}``."""

    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
        "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def _normalize_symbol_name(name: Any) -> str:
    """Return the canonical LaTeX-oriented SymPy name for a symbol base."""

    text = str(name)
    if not text:
        return text
    return sp.latex(sp.Symbol(text))


def _normalize_function_name(name: Any) -> str:
    """Return the canonical LaTeX-oriented SymPy name for a function base.

    Rules
    -----
    - User-supplied ``\\operatorname{...}`` is preserved exactly.
    - Existing explicit LaTeX names (for example ``\alpha``) are preserved.
    - Greek letter names are converted to their LaTeX macro forms.
    - One-letter plain names remain plain.
    - Other multi-letter plain names are wrapped in ``\\operatorname{...}``.
    """

    text = str(name)
    if not text:
        return text

    if "\\operatorname{" in text:
        return text

    if "\\" in text or "{" in text or "}" in text:
        return text

    latexified = _normalize_symbol_name(text)
    if latexified != text:
        return latexified

    if len(text) == 1:
        return text

    return rf"\operatorname{{{text}}}"


def _format_index_component(value: Any) -> str:
    """Render one index component as a LaTeX subscript fragment."""

    if isinstance(value, sp.Integer):
        return str(int(value))
    if isinstance(value, Integral) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, str):
        return rf"\text{{{_escape_latex_text(value)}}}"
    if isinstance(value, sp.Basic):
        return sp.latex(value)
    return str(value)


def _build_indexed_name(base_name: str, indices: tuple[Any, ...]) -> str:
    """Combine a base LaTeX name with one or more indexed components."""

    rendered = ",".join(_format_index_component(value) for value in indices)
    return f"{base_name}_{{{rendered}}}"


def _latex_function_application(self, printer) -> str:
    """Render applied undefined functions without ``\\left``/``\\right``."""

    args = ", ".join(printer._print(arg) for arg in self.args)
    return f"{self.func.__name__}({args})"


def symbols(names, *, cls=sp.Symbol, **args) -> Any:
    """Create one or more symbolic families with SymPy-compatible signature.

    This helper intentionally keeps the same call signature as
    :func:`sympy.symbols`, but maps common classes to toolkit families:

    * ``cls=sympy.Symbol`` -> :class:`SymbolFamily`
    * ``cls=sympy.Function`` -> :class:`FunctionFamily`

    Any other ``cls`` is delegated directly to :func:`sympy.symbols`.

    Examples
    --------
    >>> x, y = symbols("x y")
    >>> x[1], y[2]
    (x_{1}, y_{2})
    >>> f, g = symbols("f g", cls=sp.Function)
    >>> f(sp.Symbol("t")), g[0](sp.Symbol("t"))
    (f(t), g_{0}(t))
    >>> n = symbols("n", integer=True)
    >>> n[3].is_integer
    True
    """

    if cls in (sp.Symbol, SymbolFamily):
        family_cls = SymbolFamily
    elif cls in (sp.Function, FunctionFamily):
        family_cls = FunctionFamily
    else:
        return sp.symbols(names, cls=cls, **args)

    parser_args = {}
    if "seq" in args:
        parser_args["seq"] = args["seq"]
    parsed = sp.symbols(names, cls=sp.Symbol, **parser_args)
    return _create_family(family_cls, parsed, **args)


class SymbolFamily(sp.Symbol):
    """A SymPy symbol that lazily creates indexed child symbols.

    Parameters
    ----------
    name:
        Base symbol name used for the family root (for example ``"x"``).
        The stored SymPy name is normalized to a LaTeX-oriented form, so
        ``"alpha"`` becomes ``"\\alpha"``.
    **kwargs:
        SymPy symbol assumptions (for example ``integer=True`` or
        ``positive=True``). The same assumptions are propagated to all indexed
        children produced by :meth:`__getitem__`.

    Notes
    -----
    * ``SymbolFamily`` is itself a valid SymPy symbol and can be used directly
      in expressions.
    * Indexed children are named ``"{base}_{i,j,...}"`` with explicit braces.
      String indices are rendered as ``\text{...}``.
    * Child objects are cached per index tuple, so ``x[1] is x[1]`` is ``True``.

    Examples
    --------
    >>> x = SymbolFamily("x")
    >>> x[0]
    x_{0}
    >>> x[1, 2]
    x_{1,2}
    >>> alpha = SymbolFamily("alpha")
    >>> alpha.name
    '\\alpha'
    >>> n = SymbolFamily("n", integer=True)
    >>> n[3].is_integer
    True
    """

    def __new__(cls, name, **kwargs):
        """Create the family root symbol and initialize child caches."""

        latex_name = _normalize_symbol_name(name)
        obj = super().__new__(cls, latex_name, **kwargs)
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
            child_name = _build_indexed_name(self.name, k)
            self._family_cache[k] = sp.Symbol(child_name, **self._family_kwargs)
        return self._family_cache[k]


class FunctionFamily:
    """A family of SymPy undefined functions supporting indexed lookup.

    Parameters
    ----------
    name:
        Base function name used for the root function and indexed variants.
        Single-letter plain names remain plain, while multi-letter plain names
        are wrapped in ``\\operatorname{...}``. Existing explicit LaTeX names
        are preserved.
    **kwargs:
        Optional keyword arguments forwarded to :func:`sympy.Function`.

    Notes
    -----
    * Calling the family object directly (for example ``f(x)``) delegates to
      the base function ``Function(name)``.
    * Indexing creates function symbols named ``"{base}_{i,j,...}"``.
    * Applied functions render in LaTeX without ``\\left``/``\\right``.
    * Function symbols are cached by index tuple.

    Examples
    --------
    >>> f = FunctionFamily("f")
    >>> f(sp.Symbol("x"))
    f(x)
    >>> g = FunctionFamily("foo")
    >>> g.name
    '\\operatorname{foo}'
    >>> g[1](sp.Symbol("x"))
    \\operatorname{foo}_{1}(x)
    """

    def __init__(self, name, **kwargs):
        """Initialize the base function and index cache."""

        self.name = _normalize_function_name(name)
        self._kwargs = kwargs
        self._base = sp.Function(
            self.name,
            __dict__={"_latex": _latex_function_application},
            **kwargs,
        )
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
            indexed_name = _build_indexed_name(self.name, k)
            self._cache[k] = sp.Function(
                indexed_name,
                __dict__={"_latex": _latex_function_application},
                **self._kwargs,
            )
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
    "symbols",
    "SymbolFamily",
    "FunctionFamily",
    "Infix",
    "eq",
    "lt",
    "le",
    "gt",
    "ge",
]
