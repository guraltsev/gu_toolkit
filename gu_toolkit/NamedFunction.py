"""
NamedFunction: SymPy function classes from Python callables
==========================================================

Purpose
-------
Provide a small decorator, :func:`NamedFunction`, that turns either:

1) a regular Python function, or
2) a small "spec class" with ``symbolic`` and ``numeric`` methods

into a concrete SymPy ``Function`` subclass.

This is useful when you want to write expressions such as ``G(x)`` in SymPy while also
attaching:

- a symbolic definition (for rewriting/expansion),
- and/or a NumPy-ready numerical implementation (for compilation).

Supported Python versions
-------------------------
- Python >= 3.10

Dependencies
------------
- SymPy (required)

Public API
----------
- :func:`NamedFunction`

Design notes
------------
SymPy's ``Function`` uses a metaclass with a read-only ``__signature__``.  To preserve
nice interactive help (``inspect.signature``) we generate the function class using a
custom metaclass that exposes an overridden signature.

The generated SymPy Function class implements:

- ``_eval_rewrite_as_expand_definition``: used by ``expr.rewrite("expand_definition")``
- ``_eval_evalf``: numeric fallback via rewriting, when possible
- ``f_numpy`` (optional): a NumPy-friendly callable for numerical evaluation in
  compilation pipelines such as :func:`gu_toolkit.numpify.numpify`.

Examples
--------
Function decorator:

>>> import sympy as sp
>>> from NamedFunction import NamedFunction
>>> x = sp.Symbol("x")
>>> @NamedFunction
... def F(x):
...     return x + 1
>>> sp.simplify(F(x).rewrite("expand_definition") - (x + 1))
0

Class decorator with an *opaque* symbolic definition (returns None):

>>> @NamedFunction
... class G:
...     def symbolic(self, x):
...         return None
...     def numeric(self, x):
...         return x
>>> expr = G(x)
>>> expr.rewrite("expand_definition") == expr
True
>>> callable(getattr(G, "f_numpy", None))
True
"""

from __future__ import annotations

import inspect
import textwrap
from typing import Any, Callable, Optional, Tuple, Type, Union, cast

import sympy as sp


__all__ = ["NamedFunction"]


# Common Greek letters to avoid wrapping in \mathrm{...} in LaTeX.
_GREEK_LETTERS: set[str] = {
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
    "lambda",
    "mu",
    "nu",
    "xi",
    "omicron",
    "pi",
    "rho",
    "sigma",
    "tau",
    "upsilon",
    "phi",
    "chi",
    "psi",
    "omega",
    "Gamma",
    "Delta",
    "Theta",
    "Lambda",
    "Xi",
    "Pi",
    "Sigma",
    "Upsilon",
    "Phi",
    "Psi",
    "Omega",
}


class _SignedFunctionMeta(type(sp.Function)):
    """Metaclass that allows us to override ``__signature__`` on generated classes."""

    @property
    def __signature__(cls) -> Optional[inspect.Signature]:  # noqa: D401
        return cast(Optional[inspect.Signature], getattr(cls, "_custom_signature", None))


def NamedFunction(obj: Union[Callable[..., Any], Type[Any]]) -> Type[sp.Function]:
    """Decorate a Python callable or spec class to produce a SymPy Function class.

    There are two supported modes.

    Mode 1: function decorator
        The decorated function must accept ``n`` positional arguments and return either:
        - a SymPy expression (for symbolic expansion), or
        - ``None`` (to indicate an opaque/undefined symbolic expansion).

        You may also attach a NumPy implementation by setting ``func.f_numpy = callable``
        *before* decorating.

    Mode 2: class decorator
        The decorated class must define *exactly* two methods:

        - ``symbolic(self, *args)``: returns a SymPy expression or ``None``.
        - ``numeric(self, *args)``: returns a NumPy-compatible value.

        The resulting SymPy Function class will expose ``f_numpy(*args)`` that calls the
        class's ``numeric`` method (without instantiating the class).

    Parameters
    ----------
    obj:
        A function or a class.

    Returns
    -------
    Type[sympy.Function]
        A SymPy Function subclass with name equal to the original object name.

    Raises
    ------
    TypeError
        If ``obj`` is neither a function nor a class.
    ValueError
        If a decorated class is missing ``symbolic`` or ``numeric``, or their signatures
        are inconsistent.
    """
    if inspect.isclass(obj):
        return _handle_class_decoration(cast(Type[Any], obj))
    if callable(obj):
        return _handle_function_decoration(cast(Callable[..., Any], obj))
    raise TypeError(f"@NamedFunction must decorate a function or a class, not {type(obj)}")


def _generate_enhanced_docstring(
    *,
    original_doc: Optional[str],
    expansion_str: str,
    latex_str: str,
    has_custom_numeric: bool,
) -> str:
    """Create a consistent docstring for the generated SymPy Function class."""
    doc: list[str] = []

    # Original doc (if any)
    if original_doc:
        doc.append(textwrap.dedent(original_doc).strip())
        doc.append("")

    # Summary
    doc.append("NamedFunction-generated SymPy Function.")
    doc.append("")
    doc.append("Definition")
    doc.append("----------")
    doc.append(expansion_str)

    if latex_str:
        doc.append("")
        doc.append("LaTeX")
        doc.append("----")
        doc.append(f"$ {latex_str} $")

    if has_custom_numeric:
        doc.append("")
        doc.append("Numerical implementation")
        doc.append("------------------------")
        doc.append("This function exposes a NumPy-friendly implementation via `f_numpy(*args)`.")

    return "\n".join(doc).strip()


def _get_smart_latex_symbol(name: str) -> sp.Symbol:
    """Return a Symbol with a helpful LaTeX name.

    Rules:
    - Greek letter names are rendered as Greek in LaTeX (``alpha`` -> ``\\alpha``).
    - Multi-letter words are wrapped in ``\\mathrm{...}``.
    - Underscores are interpreted as subscripts (``x_val`` -> ``x_{val}``).
    """
    if not name:
        return sp.Symbol(name)

    if "_" in name:
        head, sub = name.split("_", 1)
    else:
        head, sub = name, None

    if len(head) > 1 and head not in _GREEK_LETTERS:
        tex_head = f"\\mathrm{{{head}}}"
    else:
        tex_head = f"\\{head}" if head in _GREEK_LETTERS else head

    tex = f"{tex_head}_{{{sub}}}" if sub else tex_head
    return sp.Symbol(name, latex_name=tex)


def _compute_symbolic_representation(
    func: Callable[..., Any],
    nargs: int,
    *,
    func_name: str,
    is_method: bool,
) -> Tuple[str, str]:
    """Try to call *func* on placeholder symbols to display its symbolic definition.

    This is used only for documentation; failures should not prevent decoration.
    """
    # 1) Pick placeholder symbols, ideally matching parameter names.
    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        start = 1 if is_method else 0
        param_names = [p.name for p in params[start:] if p.kind != p.VAR_POSITIONAL]

        if any(p.kind == p.VAR_POSITIONAL for p in params):
            syms = tuple(_get_smart_latex_symbol(f"x_{i}") for i in range(nargs))
        elif len(param_names) == nargs:
            syms = tuple(_get_smart_latex_symbol(nm) for nm in param_names)
        else:
            syms = tuple(_get_smart_latex_symbol(f"x_{i}") for i in range(nargs))
    except Exception:
        syms = tuple(_get_smart_latex_symbol(f"x_{i}") for i in range(nargs))

    # 2) Evaluate symbolic definition on placeholders.
    try:
        if is_method:
            result = func(None, *syms)
        else:
            result = func(*syms)
    except Exception as e:
        return f"Could not expand definition automatically.\nError: {e}", ""

    if result is None:
        return "`None` (Opaque function)", ""

    args_str = ", ".join(str(s) for s in syms)
    str_repr = f"`{func_name}({args_str}) = {result}`"

    latex_rhs = sp.latex(result)
    latex_args = ", ".join(sp.latex(s) for s in syms)

    if len(func_name) > 1 and func_name not in _GREEK_LETTERS:
        latex_func_name = f"\\mathrm{{{func_name}}}"
    elif func_name in _GREEK_LETTERS:
        latex_func_name = f"\\{func_name}"
    else:
        latex_func_name = func_name

    latex_repr = f"{latex_func_name}({latex_args}) = {latex_rhs}"
    return str_repr, latex_repr


def _handle_function_decoration(func: Callable[..., Any]) -> Type[sp.Function]:
    """Create a SymPy Function class from a plain function."""
    sig = inspect.signature(func)
    nargs = len(sig.parameters)

    def _eval_rewrite_as_expand_definition(self: sp.Function, *args: Any, **kwargs: Any) -> sp.Basic:
        # NOTE: return self to keep the function opaque.
        result = func(*args)
        if result is None or result == self:
            return self
        return cast(sp.Basic, result)

    def _eval_evalf(self: sp.Function, prec: int) -> sp.Basic:
        rewritten = self.rewrite("expand_definition")
        if rewritten == self:
            return self
        return rewritten.evalf(prec)

    has_numpy = callable(getattr(func, "f_numpy", None))

    expansion_str, latex_str = _compute_symbolic_representation(
        func, nargs, func_name=func.__name__, is_method=False
    )

    new_doc = _generate_enhanced_docstring(
        original_doc=func.__doc__,
        expansion_str=expansion_str,
        latex_str=latex_str,
        has_custom_numeric=has_numpy,
    )

    class_dict: dict[str, Any] = {
        "nargs": nargs,
        "_eval_rewrite_as_expand_definition": _eval_rewrite_as_expand_definition,
        "_eval_evalf": _eval_evalf,
        "__module__": func.__module__,
        "__doc__": new_doc,
        "_original_func": staticmethod(func),
        "f_numpy": getattr(func, "f_numpy", None),
    }

    NewClass = _SignedFunctionMeta(func.__name__, (sp.Function,), class_dict)
    NewClass._custom_signature = sig
    return cast(Type[sp.Function], NewClass)


def _handle_class_decoration(cls: Type[Any]) -> Type[sp.Function]:
    """Create a SymPy Function class from a spec class (symbolic + numeric)."""
    if not hasattr(cls, "symbolic") or not hasattr(cls, "numeric"):
        raise ValueError(
            f"Class {cls.__name__} decorated with @NamedFunction must define "
            "both 'symbolic' and 'numeric' methods."
        )

    symbolic_func = getattr(cls, "symbolic")
    numeric_func = getattr(cls, "numeric")

    sig_sym = inspect.signature(symbolic_func)
    sig_num = inspect.signature(numeric_func)

    if len(sig_sym.parameters) != len(sig_num.parameters):
        raise ValueError(
            f"Signature mismatch in {cls.__name__}: 'symbolic' takes {len(sig_sym.parameters)} args "
            f"but 'numeric' takes {len(sig_num.parameters)} args."
        )

    nargs = len(sig_sym.parameters) - 1
    if nargs < 0:
        raise ValueError(f"{cls.__name__}.symbolic must accept at least 'self'.")

    def _eval_rewrite_as_expand_definition(self: sp.Function, *args: Any, **kwargs: Any) -> sp.Basic:
        result = symbolic_func(None, *args)
        if result is None or result == self:
            return self
        return cast(sp.Basic, result)

    def _eval_evalf(self: sp.Function, prec: int) -> sp.Basic:
        rewritten = self.rewrite("expand_definition")
        if rewritten == self:
            return self
        return rewritten.evalf(prec)

    @staticmethod
    def f_numpy(*args: Any) -> Any:
        return numeric_func(None, *args)

    expansion_str, latex_str = _compute_symbolic_representation(
        symbolic_func, nargs, func_name=cls.__name__, is_method=True
    )

    new_doc = _generate_enhanced_docstring(
        original_doc=cls.__doc__,
        expansion_str=expansion_str,
        latex_str=latex_str,
        has_custom_numeric=True,
    )

    # Store a signature matching SymPy usage (no 'self').
    params = list(sig_sym.parameters.values())[1:]
    public_sig = inspect.Signature(params)

    class_dict: dict[str, Any] = {
        "nargs": nargs,
        "_eval_rewrite_as_expand_definition": _eval_rewrite_as_expand_definition,
        "_eval_evalf": _eval_evalf,
        "__module__": cls.__module__,
        "__doc__": new_doc,
        "f_numpy": f_numpy,
        "_original_class": cls,
    }

    NewClass = _SignedFunctionMeta(cls.__name__, (sp.Function,), class_dict)
    NewClass._custom_signature = public_sig
    return cast(Type[sp.Function], NewClass)
