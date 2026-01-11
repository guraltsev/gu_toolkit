"""
Numpify: SymPy to NumPy Compilation Module
==========================================

This module provides tools to compile symbolic SymPy expressions into high-performance,
vectorized NumPy functions. It offers specific support for:
1. "Deep" rewriting of custom SymPy functions via the 'expand_definition' hint.
2. Injecting custom numerical implementations (f_numpy) for specific symbols.
3. Automatic vectorization (converting inputs to NumPy arrays).
4. Manual control over argument order.
5. Inspectable source code via the generated function's docstring.

Usage:
    from gu_toolkit.compile.numpify import numpify
    import sympy as sp

    x, y = sp.symbols('x y')
    # Auto-detect args (alphabetical: x, y)
    func = numpify(sp.sin(x) * y)
    
    # Manual args order (y, x)
    func_explicit = numpify(sp.sin(x) * y, args=(y, x))
"""

__gu_exports__ = ["numpify"]
__gu_priority__ = 200
__gu_enabled__ = True



import textwrap
from typing import Any, Callable, Dict, Iterable, Optional, Union

import numpy as np
import sympy as sp
from sympy.printing.numpy import NumPyPrinter

__all__ = ["numpify"]


def numpify(
    expr: sp.Expr,
    *,
    args: Optional[Iterable[sp.Symbol]] = None,
    f_numpy: Optional[Dict[sp.Symbol, Callable[..., Any]]] = None,
    vectorize: bool = True,
    expand_definition: bool = True,
) -> Callable[..., Any]:
    """
    Compile a SymPy expression into a NumPy function.

    Parameters
    ----------
    expr:
        SymPy expression to compile.
    args:
        Optional explicit ordering of arguments (symbols).
        If None, autodetect from expr.free_symbols and order alphabetically by name.
    f_numpy:
        Optional mapping from specific symbols to custom numerical implementations.
        Keys must be SymPy Symbols; values are callables returning numerical results.
    vectorize:
        If True, inputs are coerced to NumPy arrays and operations are vectorized.
    expand_definition:
        If True, applies a deep rewrite of custom SymPy functions that implement
        `_eval_expand_definition()`.

    Returns
    -------
    Callable[..., Any]
        A Python function accepting numerical arguments in the chosen order.
    """
    if not isinstance(expr, sp.Basic):
        raise TypeError(f"numpify expects a SymPy expression, got {type(expr)}")

    if args is None:
        args = tuple(sorted(expr.free_symbols, key=lambda s: s.name))
    else:
        args = tuple(args)

    # Expand custom definitions if requested
    if expand_definition:
        expr = sp.expand(expr, deep=True)

    # Custom symbol -> numpy function mapping
    f_numpy = dict(f_numpy) if f_numpy is not None else {}

    # Construct numpy printer with custom function mapping
    printer = NumPyPrinter(settings={"user_functions": {}})
    # SymPy's NumPyPrinter uses `user_functions` for function names rather than symbols,
    # but we can inject replacements by mapping symbol names into locals below.

    # Generate source
    arg_names = [a.name for a in args]
    expr_code = printer.doprint(expr)

    # Build function body
    lines = []
    lines.append("def _generated(" + ", ".join(arg_names) + "):")
    if vectorize:
        for nm in arg_names:
            lines.append(f"    {nm} = np.asarray({nm})")
    # Inject custom numeric mappings by name
    for sym, fn in f_numpy.items():
        if not isinstance(sym, sp.Symbol):
            raise TypeError(f"f_numpy keys must be SymPy Symbols, got {type(sym)}")
        lines.append(f"    {sym.name} = _f_numpy['{sym.name}']")

    lines.append(f"    return {expr_code}")

    src = "\n".join(lines)

    # Compile
    glb: Dict[str, Any] = {"np": np, "_f_numpy": {k.name: v for k, v in f_numpy.items()}}
    loc: Dict[str, Any] = {}
    exec(src, glb, loc)
    fn = loc["_generated"]

    # Attach useful docs
    fn.__doc__ = textwrap.dedent(
        f"""
        Auto-generated NumPy function from SymPy expression.

        expr: {repr(expr)}
        args: {arg_names}

        Source:
        {src}
        """
    ).strip()

    return fn
