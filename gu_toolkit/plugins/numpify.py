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
    import sympy

    x, y = sympy.symbols('x y')
    # Auto-detect args (alphabetical: x, y)
    func = numpify(sympy.sin(x) * y)
    
    # Manual args order (y, x)
    func_explicit = numpify(sympy.sin(x) * y, args=(y, x))
"""

__gu_exports__ = ["numpify"]
__gu_priority__ = 200
__gu_enabled__ = True



import textwrap
from typing import Any, Callable, Dict, Iterable, Optional, Union

import numpy 
import sympy
from sympy.printing.numpy import NumPyPrinter

__all__ = ["numpify"]


def numpify(
    expr: sympy.Expr,
    *,
    args: Optional[Iterable[sympy.Symbol]] = None,
    f_numpy: Optional[Dict[sympy.Symbol, Callable[..., Any]]] = None,
    vectorize: bool = True,
    expand_definition: bool = True,
) -> Callable[..., Any]:
    """
    Compile a SymPy expression into a NumPy function.

    Notes
    -----
    - `expr` is sympified, so Python scalars like `5` are accepted.
    - `args` may be a single `sympy.Symbol` or an iterable of Symbols.
    - If `vectorize=True` and `expr` is constant (no free symbols), the returned
      function broadcasts the constant to match the broadcast shape of inputs.

    Doctests
    --------
    >>> import numpy as _np
    >>> x = sympy.Symbol("x")
    >>> f = numpify(5, args=x)
    >>> f(0)
    5.0
    >>> f(_np.array([1, 2, 3])).tolist()
    [5.0, 5.0, 5.0]

    >>> g = numpify(sympy.sin(x), args=x)
    >>> out = g(_np.array([0.0, _np.pi/2]))
    >>> _np.allclose(out, _np.array([0.0, 1.0]))
    True
    """
    # 1) Accept Python scalars/etc.
    try:
        expr = sympy.sympify(expr)
    except Exception as e:  # pragma: no cover
        raise TypeError(f"numpify expects a SymPy-compatible expression, got {type(expr)}") from e

    if not isinstance(expr, sympy.Basic):
        raise TypeError(f"numpify expects a SymPy expression, got {type(expr)}")

    # 2) Normalize args
    if args is None:
        args_tuple: tuple[sympy.Symbol, ...] = tuple(sorted(expr.free_symbols, key=lambda s: s.name))
    elif isinstance(args, sympy.Symbol):
        args_tuple = (args,)
    else:
        try:
            args_tuple = tuple(args)
        except TypeError as e:
            raise TypeError("args must be a SymPy Symbol or an iterable of SymPy Symbols") from e

    for a in args_tuple:
        if not isinstance(a, sympy.Symbol):
            raise TypeError(f"args must contain only SymPy Symbols, got {type(a)}")

    # Expand custom definitions if requested
    if expand_definition:
        expr = sympy.expand(expr, deep=True)

    # Custom symbol -> numpy function mapping
    f_numpy = dict(f_numpy) if f_numpy is not None else {}
    for sym, fn in f_numpy.items():
        if not isinstance(sym, sympy.Symbol):
            raise TypeError(f"f_numpy keys must be SymPy Symbols, got {type(sym)}")

    # Guard against expressions that reference symbols not provided by args
    missing = set(expr.free_symbols) - set(args_tuple)
    if missing:
        missing_str = ", ".join(sorted((s.name for s in missing)))
        args_str = ", ".join(a.name for a in args_tuple)
        raise ValueError(
            f"Expression contains symbols not listed in args: {missing_str}. "
            f"Provided args: ({args_str})."
        )

    # Optional sanity: prevent accidental overwrites
    if set(f_numpy.keys()) & set(args_tuple):
        overlap = ", ".join(sorted(s.name for s in (set(f_numpy.keys()) & set(args_tuple))))
        raise ValueError(
            f"f_numpy keys overlap with args ({overlap}). This would overwrite argument values."
        )

    printer = NumPyPrinter(settings={"user_functions": {}})

    arg_names = [a.name for a in args_tuple]
    expr_code = printer.doprint(expr)

    is_constant = (len(expr.free_symbols) == 0)

    lines: list[str] = []
    lines.append("def _generated(" + ", ".join(arg_names) + "):")
    if vectorize:
        for nm in arg_names:
            lines.append(f"    {nm} = numpy.asarray({nm})")

    # Inject custom numeric mappings by name
    for sym in f_numpy.keys():
        lines.append(f"    {sym.name} = _f_numpy['{sym.name}']")

    # 3) Broadcast constants to input shape when vectorizing
    if vectorize and is_constant and len(arg_names) > 0:
        lines.append(f"    _shape = numpy.broadcast({', '.join(arg_names)}).shape")
        # Use + zeros(...) so dtype promotion follows numpy rules naturally.
        lines.append(f"    return ({expr_code}) + numpy.zeros(_shape)")
    else:
        lines.append(f"    return {expr_code}")

    src = "\n".join(lines)

    glb: Dict[str, Any] = {
        "numpy": numpy,
        "_f_numpy": {k.name: v for k, v in f_numpy.items()},
    }
    loc: Dict[str, Any] = {}
    exec(src, glb, loc)
    fn = loc["_generated"]

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
