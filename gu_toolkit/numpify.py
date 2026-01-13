"""
Numpify: SymPy to NumPy Compilation Module
==========================================

This module provides tools to compile symbolic SymPy expressions into high-performance,
vectorized NumPy functions. It offers specific support for:
1. "Deep" rewriting of custom SymPy functions via the 'expand_definition' hint.
2. Injecting custom numerical implementations (f_numpy) for specific symbols.
3. Auto-detection of @NamedFunction classes with 'f_numpy' implementations.
4. Automatic vectorization (converting inputs to NumPy arrays).
5. Inspectable source code via the generated function's docstring.
"""

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

    Parameters
    ----------
    expr : sympy.Expr or convertible
        SymPy expression to compile.
    args : Optional[Iterable[sympy.Symbol]], optional
        Symbols to treat as function arguments. If None, uses all free symbols sorted alphabetically.
    f_numpy : Optional[Dict[sympy.Symbol, Callable[..., Any]]], optional
        Custom mapping from SymPy Symbols to NumPy-compatible functions.
    vectorize : bool, default True
        If True, broadcasts inputs using NumPy operations.
    expand_definition : bool, default True
        If True, applies `sympy.expand(deep=True)` to the expression.

    Returns
    -------
    Callable[..., Any]
        Generated NumPy-compatible function.
    """
    # 1) Accept Python scalars/etc.
    try:
        expr = sympy.sympify(expr)
    except Exception as e:
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

    # 3) Identify Custom Functions (@NamedFunction support)
    # Scan for Function atoms whose class provides a static 'f_numpy' implementation.
    # We must register these so the printer knows them and the exec scope has them.
    auto_detected_funcs = set()
    for atom in expr.atoms(sympy.Function):
        cls = atom.func
        if hasattr(cls, 'f_numpy'):
            auto_detected_funcs.add(cls)

    # Ensure no name collisions between functions and arguments
    detected_names = {cls.__name__ for cls in auto_detected_funcs}
    arg_names_set = {a.name for a in args_tuple}
    collisions = detected_names & arg_names_set
    if collisions:
        raise ValueError(
            f"The following functions conflict with argument names: {collisions}. "
            "Please rename the arguments or the functions."
        )

    # 4) Prepare Printer settings
    # Explicit user mappings
    f_numpy_map = dict(f_numpy) if f_numpy is not None else {}
    for sym, fn in f_numpy_map.items():
        if not isinstance(sym, sympy.Symbol):
            raise TypeError(f"f_numpy keys must be SymPy Symbols, got {type(sym)}")
            
    # Allow NamedFunction classes to be printed by their name (e.g., 'G(x)' -> 'G(x)')
    printer_user_funcs = {name: name for name in detected_names}
    
    # We must verify explicit f_numpy keys don't overlap with args
    if set(f_numpy_map.keys()) & set(args_tuple):
        overlap = ", ".join(sorted(s.name for s in (set(f_numpy_map.keys()) & set(args_tuple))))
        raise ValueError(
            f"f_numpy keys overlap with args ({overlap}). This would overwrite argument values."
        )

    # Initialize Printer with knowledge of our custom functions
    printer = NumPyPrinter(settings={"user_functions": printer_user_funcs})

    arg_names = [a.name for a in args_tuple]
    
    # Generate the code string
    try:
        expr_code = printer.doprint(expr)
    except Exception as e:
        # Fallback error handling if something remains unsupported
        raise ValueError(f"Failed to convert expression to NumPy code: {e}") from e

    is_constant = (len(expr.free_symbols) == 0)

    lines: list[str] = []
    lines.append("def _generated(" + ", ".join(arg_names) + "):")
    
    if vectorize:
        for nm in arg_names:
            lines.append(f"    {nm} = numpy.asarray({nm})")

    # Inject explicit custom numeric mappings (Symbol -> Function)
    for sym in f_numpy_map.keys():
        lines.append(f"    {sym.name} = _f_numpy_explicit['{sym.name}']")

    # 5) Broadcast constants or return expression
    if vectorize and is_constant and len(arg_names) > 0:
        lines.append(f"    _shape = numpy.broadcast({', '.join(arg_names)}).shape")
        lines.append(f"    return ({expr_code}) + numpy.zeros(_shape)")
    else:
        lines.append(f"    return {expr_code}")

    src = "\n".join(lines)

    # 6) Construct Execution Scope
    # We inject:
    #   - numpy
    #   - Explicit f_numpy mappings (as _f_numpy_explicit)
    #   - Auto-detected NamedFunction implementations (by class name)
    glb: Dict[str, Any] = {
        "numpy": numpy,
        "_f_numpy_explicit": {k.name: v for k, v in f_numpy_map.items()},
    }
    
    # Inject auto-detected function implementations
    for cls in auto_detected_funcs:
        glb[cls.__name__] = cls.f_numpy

    loc: Dict[str, Any] = {}
    
    # compile
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