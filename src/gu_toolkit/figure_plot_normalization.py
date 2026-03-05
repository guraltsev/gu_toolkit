"""Plot input normalization helpers for :class:`gu_toolkit.Figure.Figure`.

Purpose
-------
This module isolates callable/expression input normalization used by
``Figure.plot``. It converts accepted plot-call forms into a canonical tuple
that Figure can orchestrate without embedding deep branching logic.

Architecture
------------
The normalizer is intentionally stateless and side-effect free. It is designed
as a focused boundary between user-facing plotting API grammar and the
coordinator layer. This keeps normalization behavior unit-testable independent
from widget/rendering concerns.

Examples
--------
>>> import sympy as sp
>>> from gu_toolkit.figure_plot_normalization import normalize_plot_inputs
>>> x, a = sp.symbols("x a")
>>> plot_var, expr, numeric_fn, params = normalize_plot_inputs(a * x, x)
>>> plot_var == x
True
>>> params == (a,)
True

Discoverability
---------------
If you need runtime plotting behavior after normalization, inspect
``figure_plot.py`` and ``Figure.py``.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeAlias

import sympy as sp
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

from .numpify import NumericFunction, _normalize_vars

PlotVarsSpec: TypeAlias = (
    Symbol | Sequence[Symbol | Mapping[str, Symbol]] | Mapping[int | str, Symbol]
)


def coerce_symbol(value: Any, *, role: str) -> Symbol:
    """Return ``value`` as a SymPy symbol or raise a clear ``TypeError``."""
    if isinstance(value, Symbol):
        return value
    raise TypeError(
        f"plot() expects {role} to be a sympy.Symbol, got {type(value).__name__}"
    )


def rebind_numeric_function_vars(
    numeric_fn: NumericFunction,
    *,
    vars_spec: Any,
    source_callable: Callable[..., Any] | None = None,
) -> NumericFunction:
    """Return ``numeric_fn`` rebound to ``vars_spec`` order.

    Rebinding is used when callable-first plotting receives an explicit
    ``vars=`` declaration or an inferred plot-variable replacement.
    """
    fn = source_callable if source_callable is not None else numeric_fn._fn
    return NumericFunction(
        fn,
        vars=vars_spec,
        symbolic=numeric_fn.symbolic,
        source=numeric_fn.source,
    )


def normalize_plot_inputs(
    first: Any,
    second: Any,
    *,
    vars: PlotVarsSpec | None = None,
    id_hint: str | None = None,
) -> tuple[Symbol, Expr, NumericFunction | None, tuple[Symbol, ...]]:
    """Normalize callable-first ``plot()`` inputs.

    Returns
    -------
    tuple
        ``(plot_var, symbolic_expr, numeric_fn_or_none, parameter_symbols)``.
    """
    vars_spec: Any = None
    if vars is not None:
        normalized = _normalize_vars(sp.Integer(0), vars)
        vars_tuple = tuple(normalized["all"])
        if not vars_tuple:
            raise ValueError("plot() vars must not be empty when provided")
        vars_spec = normalized["spec"]
    else:
        vars_tuple = None

    f = first
    var_or_range = second

    numeric_fn: NumericFunction | None = None
    source_callable: Callable[..., Any] | None = None
    expr: Expr
    call_symbols: tuple[Symbol, ...]

    if isinstance(f, Expr):
        expr = f
        call_symbols = tuple(sorted(expr.free_symbols, key=lambda s: s.sort_key()))
    elif isinstance(f, NumericFunction):
        numeric_fn = f
        source_callable = f._fn
        call_symbols = tuple(f.free_vars)
        symbolic = f.symbolic
        if isinstance(symbolic, Expr):
            expr = symbolic
        else:
            fallback_name = id_hint or "f"
            expr = sp.Symbol(f"{fallback_name}_numeric")
    elif callable(f):
        source_callable = f
        sig = inspect.signature(f)
        positional = [
            p
            for p in sig.parameters.values()
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        if any(
            p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for p in sig.parameters.values()
        ):
            raise TypeError(
                "plot() callable does not support *args/**kwargs signatures"
            )
        call_symbols = tuple(sp.Symbol(p.name) for p in positional)
        numeric_fn = NumericFunction(
            f, vars=vars_spec if vars_spec is not None else call_symbols
        )
        if vars_spec is not None:
            call_symbols = tuple(numeric_fn.free_vars)
        expr = sp.Symbol(id_hint or getattr(f, "__name__", "f"))
    else:
        raise TypeError(
            "plot() expects first argument to be a SymPy expression, NumericFunction, or callable."
        )

    if vars_tuple is not None:
        bound_symbols = vars_tuple
        if numeric_fn is not None:
            numeric_fn = rebind_numeric_function_vars(
                numeric_fn,
                vars_spec=vars_spec if vars_spec is not None else bound_symbols,
                source_callable=source_callable,
            )
    else:
        bound_symbols = call_symbols

    if isinstance(var_or_range, tuple):
        if len(var_or_range) != 3:
            raise ValueError(
                "plot() range tuple must have shape (var, min, max), e.g. (x, -4, 4)"
            )
        plot_var = coerce_symbol(var_or_range[0], role="range tuple variable")
    elif var_or_range is None:
        if len(bound_symbols) == 1:
            plot_var = bound_symbols[0]
        else:
            raise ValueError(
                "plot() could not infer plotting variable for callable-first usage. "
                "Pass an explicit symbol or range tuple, e.g. plot(f, x) or plot(f, (x, -4, 4))."
            )
    else:
        plot_var = coerce_symbol(var_or_range, role="plot variable")

    if plot_var not in bound_symbols:
        if len(bound_symbols) == 1:
            bound_symbols = (plot_var,)
            if numeric_fn is not None:
                numeric_fn = rebind_numeric_function_vars(
                    numeric_fn,
                    vars_spec=bound_symbols,
                    source_callable=source_callable,
                )
        else:
            raise ValueError(
                f"plot() variable {plot_var!r} is not present in callable variables {bound_symbols!r}. "
                "Use vars=... to declare callable variable order explicitly."
            )

    parameters = tuple(sym for sym in bound_symbols if sym != plot_var)
    return plot_var, expr, numeric_fn, parameters
