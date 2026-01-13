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
    Compile a SymPy expression into a high-performance NumPy function with broadcasting support.

    This function generates a Python function that evaluates the given SymPy expression
    using NumPy operations, enabling vectorized evaluation over arrays of inputs.
    The generated function automatically handles NumPy broadcasting and dtype promotion.

    Parameters
    ----------
    expr : sympy.Expr or convertible
        SymPy expression to compile. Can be any object convertible via `sympy.sympify`,
        including Python scalars (e.g., 5), strings, or existing SymPy expressions.
    args : Optional[Iterable[sympy.Symbol]], optional
        Symbols to treat as function arguments. If None (default), uses all free symbols
        in `expr` sorted alphabetically by name. Can be a single Symbol or iterable.
    f_numpy : Optional[Dict[sympy.Symbol, Callable[..., Any]]], optional
        Custom mapping from SymPy Symbols to NumPy-compatible functions.
        Useful when symbols represent functions rather than variables (e.g., mapping `f`
        to `np.sin`). Keys must be Symbols not present in `args`.
    vectorize : bool, default True
        If True, generates a function that broadcasts over array inputs using NumPy
        operations. If False, generates a scalar function that may be slower for
        array inputs but avoids broadcasting overhead for scalar use cases.
        When True and `expr` is constant, the function returns an array of the constant
        value shaped by broadcasting the inputs.
    expand_definition : bool, default True
        If True, applies `sympy.expand(deep=True)` to the expression before compilation.
        This can improve performance by expanding composite operations and should
        generally be left enabled unless expression expansion is undesirable.

    Returns
    -------
    Callable[..., Any]
        Generated function that accepts numerical inputs corresponding to `args`.
        The function:
        - Converts inputs to NumPy arrays (when `vectorize=True`)
        - Applies custom symbol mappings from `f_numpy`
        - Evaluates the expression using NumPy operations
        - Returns scalars or arrays with proper dtype promotion

    Raises
    ------
    TypeError
        - If `expr` cannot be sympified
        - If `args` contains non-Symbol elements
        - If `f_numpy` keys are not Symbols
    ValueError
        - If `expr` contains symbols not listed in `args`
        - If `f_numpy` keys overlap with `args` symbols

    Notes
    -----
    1. Broadcasting behavior:
       - With `vectorize=True`: All inputs are converted to arrays via `numpy.asarray`
         and broadcasting follows NumPy rules.
       - With constant expressions: Returns `constant + numpy.zeros(broadcast_shape)`
         to ensure proper dtype and shape handling.
       - With `vectorize=False`: Inputs are not converted, and operations may fail
         on array inputs.

    2. Performance considerations:
       - The generated function is created via `exec` and may have overhead on
         very small inputs.
       - For large arrays, the vectorized version provides near-native NumPy performance.
       - Custom functions in `f_numpy` are injected by name and must be available in
         the NumPy namespace or provided as callables.

    3. Symbol resolution:
       - All symbols in `expr` must be accounted for: either in `args` (as variables)
         or in `f_numpy` (as functions).
       - The generated function's parameter order matches the order of symbols in `args`.

    4. Safety:
       - Uses `exec` internally; exercise caution with untrusted expressions.
       - The generated function includes its source code in its `__doc__` for inspection.

    Examples
    --------
    >>> import sympy
    >>> import numpy as np
    >>> x, y = sympy.symbols('x y')

    Basic scalar and vector evaluation:
    >>> f = numpify(5, args=x)
    >>> f(0)
    5.0
    >>> f(np.array([1, 2, 3]))
    array([5., 5., 5.])

    Trigonometric function:
    >>> g = numpify(sympy.sin(x), args=x)
    >>> g(np.array([0, np.pi/2]))
    array([0., 1.])

    Multiple arguments with broadcasting:
    >>> h = numpify(x**2 + y, args=(x, y))
    >>> h([1, 2, 3], 10)  # Broadcast y=10 across x
    array([11., 14., 19.])

    Custom function mapping:
    >>> from numpy import exp
    >>> f_map = {sympy.Function('f')(x): exp}
    >>> expr = sympy.Function('f')(x) * 2
    >>> j = numpify(expr, args=x, f_numpy=f_map)
    >>> j(0)
    2.0
    >>> j(1)  # 2 * exp(1)
    5.43656365691809

    Disable vectorization for scalar-only use:
    >>> k = numpify(x**2, args=x, vectorize=False)
    >>> k(3)
    9.0
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
