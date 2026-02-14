"""
numpify: Compile SymPy expressions to NumPy-callable Python functions
====================================================================

Purpose
-------
Turn a SymPy expression into a callable Python function that evaluates using NumPy.

This module is intentionally small and "batteries included" for interactive research
workflows where you want:

- explicit argument order,
- fast vectorized evaluation via NumPy broadcasting,
- support for *custom* SymPy functions that carry a NumPy implementation (``f_numpy``),
- and inspectable generated source.

Supported Python versions
-------------------------
- Python >= 3.10

Dependencies
------------
- NumPy (required)
- SymPy (required)

Public API
----------
- :func:`numpify`
- :func:`numpify_cached`

How custom functions are handled
--------------------------------
SymPy's NumPy code printer cannot natively print arbitrary user-defined SymPy Functions.
When ``expr`` contains an unknown function call such as ``G(x)``, SymPy raises a
``PrintMethodNotImplementedError`` by default.

This module enables SymPy's ``allow_unknown_functions`` option so unknown functions are
printed as plain calls (``G(x)``). We then provide runtime bindings so that the name
``G`` resolves to a callable.

Bindings are resolved in this order:

1. Explicit bindings provided via the ``f_numpy`` argument (for function classes).
2. Auto-detection: for each function ``F`` appearing in the expression, if
   ``callable(getattr(F, "f_numpy", None))`` then that callable is used.

If an unknown function remains unbound, :func:`numpify` raises a clear error before code
generation.

Examples
--------
>>> import numpy as np
>>> import sympy as sp
>>> from numpify import numpify
>>> x = sp.Symbol("x")

Constant compiled with broadcasting:
>>> f = numpify(5, vars=x)
>>> float(f(0))
5.0
>>> f(np.array([1, 2, 3]))
array([5., 5., 5.])

Symbol binding (treat `a` as an injected constant):
>>> a = sp.Symbol("a")
>>> g = numpify(a * x, vars=x, f_numpy={a: 2.0})
>>> g(np.array([1, 2, 3]))
array([2., 4., 6.])

Logging
-------
This module uses Python's standard :mod:`logging` library and is silent by default.
To enable debug logging in a notebook session:

>>> import logging
>>> import numpify
>>> logging.basicConfig(level=logging.DEBUG)
>>> logging.getLogger(numpify.__name__).setLevel(logging.DEBUG)

If you import this file as part of a package (e.g. ``gu_toolkit.numpify``), use that
module name instead.
"""

from __future__ import annotations

from functools import lru_cache
import builtins
import inspect
import keyword

import logging
import time
import textwrap
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple, TypeAlias, Union, cast

import numpy as np
import sympy as sp
from sympy.core.function import FunctionClass
from sympy.printing.numpy import NumPyPrinter


__all__ = [
    "numpify",
    "numpify_cached",
    "DYNAMIC_PARAMETER",
    "UNFREEZE",
    "ParameterContext",
    "NumericFunction",
    "NumpifiedFunction",
]


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


_SymBindingKey = sp.Symbol
_FuncBindingKey = Union[FunctionClass, sp.Function]
_BindingKey = Union[_SymBindingKey, _FuncBindingKey]
_SymBindings = Dict[str, Any]
_FuncBindings = Dict[str, Callable[..., Any]]


class _Sentinel:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name


DYNAMIC_PARAMETER = _Sentinel("DYNAMIC_PARAMETER")
UNFREEZE = _Sentinel("UNFREEZE")


ParameterContext: TypeAlias = Mapping[sp.Symbol, Any]


_VarsInput = Union[
    sp.Symbol,
    Iterable[sp.Symbol | Mapping[str, sp.Symbol]],
    Mapping[Union[int, str], sp.Symbol],
]


class _VarsView:
    """Backwards-compatible vars accessor.

    - Iterable/sequence view yields positional symbols (legacy behavior).
    - Callable view (`obj.vars()`) returns the round-trip vars specification.
    """

    __slots__ = ("_positional", "_roundtrip")

    def __init__(self, positional: tuple[sp.Symbol, ...], roundtrip: Any):
        self._positional = positional
        self._roundtrip = roundtrip

    def __iter__(self):
        return iter(self._positional)

    def __len__(self) -> int:
        return len(self._positional)

    def __getitem__(self, idx: Any) -> Any:
        return self._positional[idx]

    def __bool__(self) -> bool:
        return bool(self._positional)

    def __call__(self) -> Any:
        return self._roundtrip

    def __repr__(self) -> str:
        return repr(self._positional)


class NumericFunction:
    """Compiled SymPy->NumPy callable with optional frozen/dynamic bindings."""

    __slots__ = (
        "_fn",
        "symbolic",
        "call_signature",
        "source",
        "_vars_spec",
        "_keyed_symbols",
        "_key_for_symbol",
        "_symbol_for_key",
        "_vars_view",
        "name_for_symbol",
        "symbol_for_name",
        "_parameter_context",
        "_frozen",
        "_dynamic",
    )

    def __init__(
        self,
        fn: Callable[..., Any],
        vars: _VarsInput | None = None,
        symbolic: sp.Basic | None = None,
        call_signature: tuple[tuple[sp.Symbol, str], ...] | None = None,
        source: str = "",
        *,
        keyed_symbols: tuple[tuple[str, sp.Symbol], ...] | None = None,
        vars_spec: Any = None,
        parameter_context: ParameterContext | None = None,
        frozen: Mapping[sp.Symbol, Any] | None = None,
        dynamic: Iterable[sp.Symbol] | None = None,
    ) -> None:
        if call_signature is None:
            normalized = _normalize_vars(symbolic if isinstance(symbolic, sp.Basic) else sp.Integer(0), vars)
            reserved = set(dir(builtins)) | {"numpy", "_sym_bindings"}
            call_signature = _build_call_signature(normalized["all"], reserved)
            keyed_symbols = normalized["keyed"]
            vars_spec = normalized["spec"]
        if keyed_symbols is None:
            keyed_symbols = tuple()
        if vars_spec is None:
            vars_spec = tuple(sym for sym, _ in call_signature)

        self._fn = fn
        self.symbolic = symbolic
        self.call_signature = call_signature
        self.source = source
        self._vars_spec = vars_spec
        self._keyed_symbols = keyed_symbols
        self._key_for_symbol = {sym: key for key, sym in keyed_symbols}
        self._symbol_for_key = {key: sym for key, sym in keyed_symbols}
        self._vars_view = _VarsView(tuple(sym for sym, _ in call_signature if sym not in self._key_for_symbol), self._vars_spec)
        self.name_for_symbol = {sym: name for sym, name in call_signature}
        self.symbol_for_name = {name: sym for sym, name in call_signature}
        self._parameter_context = parameter_context
        self._frozen: dict[sp.Symbol, Any] = dict(frozen or {})
        self._dynamic: set[sp.Symbol] = set(dynamic or ())

    def _clone(self) -> "NumericFunction":
        return NumericFunction(
            fn=self._fn,
            symbolic=self.symbolic,
            call_signature=self.call_signature,
            source=self.source,
            keyed_symbols=self._keyed_symbols,
            vars_spec=self._vars_spec,
            parameter_context=self._parameter_context,
            frozen=self._frozen,
            dynamic=self._dynamic,
        )

    def _resolve_key(self, key: sp.Symbol | str) -> sp.Symbol:
        if isinstance(key, sp.Symbol):
            if key not in self.name_for_symbol:
                raise KeyError(f"Unknown symbol key: {key!r}")
            return key
        if isinstance(key, str):
            if key in self._symbol_for_key:
                return self._symbol_for_key[key]
            if key not in self.symbol_for_name:
                raise KeyError(f"Unknown var name: {key!r}")
            return self.symbol_for_name[key]
        raise TypeError(f"Parameter key must be Symbol or str, got {type(key).__name__}")

    def _normalize_bindings(
        self,
        bindings: Mapping[sp.Symbol | str, Any] | Iterable[tuple[sp.Symbol | str, Any]] | None,
        kwargs: Mapping[str, Any],
    ) -> dict[sp.Symbol, Any]:
        items: list[tuple[sp.Symbol | str, Any]] = []
        if bindings is None:
            pass
        elif isinstance(bindings, Mapping):
            items.extend(bindings.items())
        else:
            items.extend(tuple(bindings))
        items.extend(kwargs.items())

        resolved: dict[sp.Symbol, Any] = {}
        for key, value in items:
            sym = self._resolve_key(key)
            if sym in resolved:
                var_name = self.name_for_symbol[sym]
                raise ValueError(f"Duplicate binding for symbol {sym!r} (var '{var_name}')")
            resolved[sym] = value
        return resolved

    def __call__(self, *positional_args: Any, **keyed_args: Any) -> Any:
        if not self._frozen and not self._dynamic:
            if keyed_args:
                full_args = list(positional_args)
                for key, _sym in self._keyed_symbols:
                    if key not in keyed_args:
                        raise TypeError(f"Missing keyed argument: {key!r}")
                    full_args.append(keyed_args[key])
                extra = set(keyed_args) - {k for k, _ in self._keyed_symbols}
                if extra:
                    raise TypeError(f"Unknown keyed argument(s): {', '.join(sorted(extra))}")
                return self._fn(*full_args)
            return self._fn(*positional_args)

        full_values: list[Any] = []
        free_idx = 0
        missing: list[str] = []

        for sym, _ in self.call_signature:
            var_name = self.name_for_symbol[sym]
            if sym in self._frozen:
                full_values.append(self._frozen[sym])
                continue

            if sym in self._dynamic:
                if self._parameter_context is None:
                    raise ValueError(
                        f"Dynamic var {sym!r} ('{var_name}') requires parameter_context at call time"
                    )
                if sym not in self._parameter_context:
                    raise KeyError(
                        f"parameter_context is missing symbol {sym!r} ('{var_name}')"
                    )
                full_values.append(self._parameter_context[sym])
                continue

            if sym in self._symbol_for_key:
                key_name = self._key_for_symbol[sym]
                if key_name not in keyed_args:
                    missing.append(f"{sym!r} ('{key_name}')")
                else:
                    full_values.append(keyed_args[key_name])
                continue

            if free_idx >= len(positional_args):
                missing.append(f"{sym!r} ('{var_name}')")
            else:
                full_values.append(positional_args[free_idx])
                free_idx += 1

        if missing:
            raise TypeError("Missing positional argument(s): " + ", ".join(missing))
        if free_idx != len(positional_args):
            raise TypeError(
                f"Too many positional arguments: expected {free_idx}, got {len(positional_args)}"
            )
        extra = set(keyed_args) - set(self._symbol_for_key)
        if extra:
            raise TypeError(f"Unknown keyed argument(s): {', '.join(sorted(extra))}")

        return self._fn(*full_values)

    @property
    def vars(self) -> _VarsView:
        return self._vars_view

    @property
    def all_vars(self) -> tuple[sp.Symbol, ...]:
        return tuple(sym for sym, _ in self.call_signature)

    @property
    def var_names(self) -> tuple[str, ...]:
        return tuple(name for _, name in self.call_signature)

    def freeze(self, bindings: Mapping[sp.Symbol | str, Any] | Iterable[tuple[sp.Symbol | str, Any]] | None = None, /, **kwargs: Any) -> "NumericFunction":
        updates = self._normalize_bindings(bindings, kwargs)
        out = self._clone()
        for sym, value in updates.items():
            if value is DYNAMIC_PARAMETER:
                out._dynamic.add(sym)
                out._frozen.pop(sym, None)
            elif value is UNFREEZE:
                out._dynamic.discard(sym)
                out._frozen.pop(sym, None)
            else:
                out._frozen[sym] = value
                out._dynamic.discard(sym)
        return out

    def unfreeze(self, *keys: sp.Symbol | str) -> "NumericFunction":
        if not keys:
            bound_symbols = tuple(sym for sym in self.all_vars if sym in self._frozen or sym in self._dynamic)
            return self.freeze({sym: UNFREEZE for sym in bound_symbols})
        return self.freeze({k: UNFREEZE for k in keys})

    def set_parameter_context(self, ctx: ParameterContext) -> "NumericFunction":
        out = self._clone()
        out._parameter_context = ctx
        return out

    def remove_parameter_context(self) -> "NumericFunction":
        out = self._clone()
        out._parameter_context = None
        return out

    @property
    def free_vars(self) -> tuple[sp.Symbol, ...]:
        return tuple(sym for sym in self.all_vars if sym not in self._frozen and sym not in self._dynamic)

    @property
    def free_var_signature(self) -> tuple[tuple[sp.Symbol, str], ...]:
        return tuple((sym, self.name_for_symbol[sym]) for sym in self.free_vars)

    @property
    def is_live(self) -> bool:
        return self._parameter_context is not None

    @property
    def __signature__(self) -> inspect.Signature:
        """Return a meaningful call signature for currently-free positional vars."""
        params = [
            inspect.Parameter(name, inspect.Parameter.POSITIONAL_ONLY)
            for _, name in self.free_var_signature
        ]
        return inspect.Signature(parameters=params)

    def __repr__(self) -> str:
        vars_str = ", ".join(name for _, name in self.call_signature)
        return f"NumericFunction({self.symbolic!r}, vars=({vars_str}))"


class NumpifiedFunction(NumericFunction):
    """Compatibility constructor for :class:`NumericFunction`."""

    def __init__(self, fn: Callable[..., Any], vars: _VarsInput | None = None, symbolic: sp.Basic | None = None, call_signature: tuple[tuple[sp.Symbol, str], ...] | None = None, source: str = "", **kwargs: Any) -> None:
        super().__init__(fn=fn, vars=vars, symbolic=symbolic, call_signature=call_signature, source=source, **kwargs)


def numpify(
    expr: Any,
    *,
    vars: _VarsInput | None = None,
    f_numpy: Optional[Mapping[_BindingKey, Any]] = None,
    vectorize: bool = True,
    expand_definition: bool = True,
    cache: bool = True,
) -> NumericFunction:
    """Compile a SymPy expression into a NumPy-evaluable function.

    By default this uses the same LRU-backed cache as :func:`numpify_cached`.
    Pass ``cache=False`` to force a fresh compile.
    """
    if cache:
        return numpify_cached(
            expr,
            vars=vars,
            f_numpy=f_numpy,
            vectorize=vectorize,
            expand_definition=expand_definition,
        )
    return _numpify_uncached(
        expr,
        vars=vars,
        f_numpy=f_numpy,
        vectorize=vectorize,
        expand_definition=expand_definition,
    )


def _is_valid_parameter_name(name: str) -> bool:
    return bool(name) and name.isidentifier() and not keyword.iskeyword(name)


def _mangle_base_name(name: str) -> str:
    cleaned = "".join(ch if (ch == "_" or ch.isalnum()) else "_" for ch in name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}__"
    return cleaned


def _build_call_signature(vars_tuple: tuple[sp.Symbol, ...], reserved_names: set[str]) -> tuple[tuple[sp.Symbol, str], ...]:
    used = set(reserved_names)
    out: list[tuple[sp.Symbol, str]] = []
    for idx, sym in enumerate(vars_tuple):
        base = sym.name if _is_valid_parameter_name(sym.name) else _mangle_base_name(sym.name)
        candidate = base
        suffix = 0
        while candidate in used or not _is_valid_parameter_name(candidate):
            candidate = f"{base}__{suffix}"
            suffix += 1
        used.add(candidate)
        out.append((sym, candidate))
    return tuple(out)


def _numpify_uncached(
    expr: Any,
    *,
    vars: _VarsInput | None = None,
    f_numpy: Optional[Mapping[_BindingKey, Any]] = None,
    vectorize: bool = True,
    expand_definition: bool = True,
) -> NumericFunction:
    """Compile a SymPy expression into a NumPy-evaluable Python function (uncached).

    Parameters
    ----------
    expr:
        A SymPy expression or anything convertible via :func:`sympy.sympify`.
    vars:
        Symbols treated as *positional arguments* of the compiled function.

        - If None (default), uses all free symbols of ``expr`` sorted by ``sympy.default_sort_key``.
        - If a single Symbol, that symbol is the only argument.
        - If an iterable, argument order is preserved.

    f_numpy:
        Optional bindings for:
        - **Symbols** (constants/objects injected by name into the generated function body).
          Example: ``{a: 2.0}`` binds the symbol ``a`` to the value ``2.0``.
        - **SymPy function classes** (or applications) to NumPy-callable implementations.
          Example: ``{G: G.f_numpy}`` binds ``G(x)`` to the callable.

        In addition, if a function class ``F`` appears in ``expr`` and has a callable
        attribute ``F.f_numpy``, it is auto-bound.

    vectorize:
        If True, each argument is converted via ``numpy.asarray`` to enable broadcasting.
        If False, arguments are left as-is (scalar evaluation).

    expand_definition:
        If True, attempts to rewrite custom functions via
        ``expr.rewrite("expand_definition")`` (repeated to a fixed point), and then applies
        ``sympy.expand(..., deep=True)``.

        If a function is opaque (its rewrite returns itself), the function call remains
        in the expression and must be bound via ``f_numpy`` or ``F.f_numpy``.

    Returns
    -------
    NumpifiedFunction
        A generated callable wrapper with expression metadata and source text.

    Raises
    ------
    TypeError
        If ``vars`` is not a Symbol or an iterable of Symbols.
        If a function binding is provided but the value is not callable.
    ValueError
        If ``expr`` contains unbound symbols or unbound unknown functions.
        If symbol bindings overlap with argument symbols.

    Notes
    -----
    This function uses ``exec`` to define the generated function. Avoid calling it on
    untrusted expressions.
    """
    # 1) Normalize expr to SymPy.
    try:
        expr_sym = sp.sympify(expr)
    except Exception as e:
        raise TypeError(f"numpify expects a SymPy-compatible expression, got {type(expr)}") from e
    if not isinstance(expr_sym, sp.Basic):
        raise TypeError(f"numpify expects a SymPy expression, got {type(expr_sym)}")
    expr = cast(sp.Basic, expr_sym)

    # 2) Normalize vars.
    normalized_vars = _normalize_vars(expr, vars)
    vars_tuple = normalized_vars["all"]
    keyed_symbols = normalized_vars["keyed"]
    vars_spec = normalized_vars["spec"]

    log_debug = logger.isEnabledFor(logging.DEBUG)
    t_total0: float | None = time.perf_counter() if log_debug else None
    if log_debug:
        logger.debug("numpify: detected vars=%s", [a.name for a in vars_tuple])

    # 3) Optionally expand custom definitions.
    if expand_definition:
        expr = _rewrite_expand_definition(expr)
        expr = sp.expand(expr, deep=True)

    # 4) Parse bindings.
    sym_bindings, func_bindings = _parse_bindings(expr, f_numpy)

    # 5) Validate free symbols are accounted for (either vars or symbol bindings).
    free_names = {s.name for s in expr.free_symbols}
    var_names_set = {a.name for a in vars_tuple}
    missing_names = free_names - var_names_set - set(sym_bindings.keys())
    if missing_names:
        missing_str = ", ".join(sorted(missing_names))
        vars_str = ", ".join(a.name for a in vars_tuple)
        raise ValueError(
            "Expression contains unbound symbols: "
            f"{missing_str}. Provide them in vars=({vars_str}) or bind via f_numpy={{symbol: value}}."
        )

    # 6) Prevent accidental overwrites: symbol bindings cannot overlap with vars.
    overlap = set(a.name for a in vars_tuple) & set(sym_bindings.keys())
    if overlap:
        raise ValueError(
            "Symbol bindings overlap with vars (would overwrite argument values): "
            + ", ".join(sorted(overlap))
        )

    # 7) Create printer (allow unknown functions to print as plain calls).
    printer = NumPyPrinter(settings={"user_functions": {}, "allow_unknown_functions": True})

    # 8) Preflight: any function that prints as a *bare* call must be bound.
    _require_bound_unknown_functions(expr, printer, func_bindings)

    # 9) Build call signature and generate expression code/source.
    reserved_names = set(keyword.kwlist) | set(dir(builtins)) | {"numpy", "np", "_sym_bindings"}
    reserved_names |= set(sym_bindings.keys()) | set(func_bindings.keys())
    call_signature = _build_call_signature(vars_tuple, reserved_names)
    arg_names = [name for _, name in call_signature]
    replacement = {sym: sp.Symbol(name) for sym, name in call_signature}
    expr_codegen = expr.xreplace(replacement)

    # "Lambdification"-like code generation step: SymPy -> NumPy expression string.
    t_codegen0: float | None = time.perf_counter() if log_debug else None
    expr_code = printer.doprint(expr_codegen)
    t_codegen_s = (time.perf_counter() - t_codegen0) if t_codegen0 is not None else None
    is_constant = (len(expr.free_symbols) == 0)

    lines: list[str] = []
    lines.append("def _generated(" + ", ".join(arg_names) + "):")

    if vectorize:
        for nm in arg_names:
            lines.append(f"    {nm} = numpy.asarray({nm})")

    # Inject symbol bindings by name
    for nm in sorted(sym_bindings.keys()):
        lines.append(f"    {nm} = _sym_bindings[{nm!r}]")

    if vectorize and is_constant and len(arg_names) > 0:
        lines.append(f"    _shape = numpy.broadcast({', '.join(arg_names)}).shape")
        lines.append(f"    return ({expr_code}) + numpy.zeros(_shape)")
    else:
        lines.append(f"    return {expr_code}")

    src = "\n".join(lines)

    # Runtime globals dict compilation (kept separate for timing / debugging).
    t_dict0: float | None = time.perf_counter() if log_debug else None
    glb: Dict[str, Any] = {
        "numpy": np,
        "_sym_bindings": sym_bindings,
        **func_bindings,  # function names like "G" -> callable
    }
    t_dict_s = (time.perf_counter() - t_dict0) if t_dict0 is not None else None

    loc: Dict[str, Any] = {}

    t_exec0: float | None = time.perf_counter() if log_debug else None
    exec(src, glb, loc)
    t_exec_s = (time.perf_counter() - t_exec0) if t_exec0 is not None else None
    fn = cast(Callable[..., Any], loc["_generated"])

    fn.__doc__ = textwrap.dedent(
        f"""
        Auto-generated NumPy function from SymPy expression.

        expr: {repr(expr)}
        vars: {arg_names}

        Source:
        {src}
        """
    ).strip()

    if log_debug:
        t_total_s = (time.perf_counter() - t_total0) if t_total0 is not None else None
        logger.debug(
            "numpify timings (ms): codegen=%.2f dict=%.2f exec=%.2f total=%.2f",
            1000.0 * (t_codegen_s or 0.0),
            1000.0 * (t_dict_s or 0.0),
            1000.0 * (t_exec_s or 0.0),
            1000.0 * (t_total_s or 0.0),
        )

    return NumericFunction(fn=fn, symbolic=expr, call_signature=call_signature, source=src, keyed_symbols=keyed_symbols, vars_spec=vars_spec)


def _freeze_vars_spec(spec: Any) -> Any:
    if isinstance(spec, tuple):
        return ("T", tuple(_freeze_vars_spec(x) for x in spec))
    if isinstance(spec, dict):
        items = sorted(((k, _freeze_vars_spec(v)) for k, v in spec.items()), key=lambda item: (type(item[0]).__name__, repr(item[0])))
        return ("D", tuple(items))
    return ("V", spec)


def _thaw_vars_spec(spec_key: Any) -> Any:
    tag, payload = spec_key
    if tag == "T":
        return tuple(_thaw_vars_spec(x) for x in payload)
    if tag == "D":
        return {k: _thaw_vars_spec(v) for k, v in payload}
    if tag == "V":
        return payload
    raise ValueError(f"Unknown vars spec key tag: {tag!r}")


def _normalize_vars(expr: sp.Basic, vars: _VarsInput | None) -> dict[str, Any]:
    """Normalize vars into positional/keyed symbols and a round-trip spec."""
    if vars is None:
        vars_tuple: Tuple[sp.Symbol, ...] = tuple(sorted(expr.free_symbols, key=sp.default_sort_key))
        return {"all": vars_tuple, "keyed": tuple(), "spec": vars_tuple, "spec_key": _freeze_vars_spec(vars_tuple)}

    if isinstance(vars, sp.Symbol):
        spec = (vars,)
        return {"all": (vars,), "keyed": tuple(), "spec": spec, "spec_key": _freeze_vars_spec(spec)}

    positional: list[sp.Symbol] = []
    keyed: list[tuple[str, sp.Symbol]] = []

    def _as_symbol(value: Any) -> sp.Symbol:
        sym = sp.sympify(value)
        if not isinstance(sym, sp.Symbol):
            raise TypeError(f"vars must contain only SymPy Symbols, got {type(sym)}")
        return sym

    if isinstance(vars, Mapping):
        int_entries = [(k, v) for k, v in vars.items() if isinstance(k, int)]
        non_int_entries = [(k, v) for k, v in vars.items() if not isinstance(k, int)]
        if int_entries:
            ordered_int_keys = sorted(k for k, _ in int_entries)
            expected = list(range(len(ordered_int_keys)))
            if ordered_int_keys != expected:
                raise ValueError("Integer vars keys must be contiguous and start at 0")
            by_key = {k: _as_symbol(v) for k, v in int_entries}
            positional.extend(by_key[i] for i in expected)
        for k, v in non_int_entries:
            if not isinstance(k, str):
                raise TypeError("Non-integer vars mapping keys must be strings")
            keyed.append((k, _as_symbol(v)))
        all_symbols = tuple(positional + [sym for _, sym in keyed])
        seen = set()
        for sym in all_symbols:
            if sym in seen:
                raise ValueError(f"Duplicate symbol in vars: {sym!r}")
            seen.add(sym)
        spec = dict(vars)
        return {"all": all_symbols, "keyed": tuple(keyed), "spec": spec, "spec_key": _freeze_vars_spec(spec)}

    try:
        items = tuple(vars)
    except TypeError as e:
        raise TypeError("vars must be a SymPy Symbol, mapping, or iterable") from e

    tail_mapping: Mapping[Any, Any] | None = None
    if items and isinstance(items[-1], Mapping):
        tail_mapping = cast(Mapping[Any, Any], items[-1])
        items = items[:-1]

    for item in items:
        positional.append(_as_symbol(item))

    if tail_mapping is not None:
        for k, v in tail_mapping.items():
            if isinstance(k, int):
                raise ValueError("Integer keys are not allowed in tuple+mapping vars form")
            if not isinstance(k, str):
                raise TypeError("Keyed vars names must be strings")
            keyed.append((k, _as_symbol(v)))
        spec = tuple((*items, dict(tail_mapping)))
    else:
        spec = tuple(items)

    all_symbols = tuple(positional + [sym for _, sym in keyed])
    seen = set()
    for sym in all_symbols:
        if sym in seen:
            raise ValueError(f"Duplicate symbol in vars: {sym!r}")
        seen.add(sym)
    return {"all": all_symbols, "keyed": tuple(keyed), "spec": spec, "spec_key": _freeze_vars_spec(spec)}


def _rewrite_expand_definition(expr: sp.Basic, *, max_passes: int = 10) -> sp.Basic:
    """Rewrite using the 'expand_definition' target until stable (or max_passes)."""
    current = expr
    for _ in range(max_passes):
        nxt = current.rewrite("expand_definition")
        if nxt == current:
            break
        current = cast(sp.Basic, nxt)
    return current


def _parse_bindings(expr: sp.Basic, f_numpy: Optional[Mapping[_BindingKey, Any]]) -> Tuple[_SymBindings, _FuncBindings]:
    """Split user-provided bindings into symbol and function bindings, plus auto-bindings."""
    sym_bindings: _SymBindings = {}
    func_bindings: _FuncBindings = {}

    if f_numpy:
        for key, value in f_numpy.items():
            if isinstance(key, sp.Symbol):
                sym_bindings[key.name] = value
                continue

            if isinstance(key, sp.Function):
                name = key.func.__name__
                if not callable(value):
                    raise TypeError(f"Function binding for {name} must be callable, got {type(value)}")
                func_bindings[name] = cast(Callable[..., Any], value)
                continue

            if isinstance(key, FunctionClass):
                name = key.__name__
                if not callable(value):
                    raise TypeError(f"Function binding for {name} must be callable, got {type(value)}")
                func_bindings[name] = cast(Callable[..., Any], value)
                continue

            raise TypeError(
                "f_numpy keys must be SymPy Symbols or SymPy function objects/classes. "
                f"Got {type(key)}."
            )

    # Auto-bind NamedFunction-style implementations (F.f_numpy) when present.
    for app in expr.atoms(sp.Function):
        impl = getattr(app.func, "f_numpy", None)
        if callable(impl) and app.func.__name__ not in func_bindings:
            func_bindings[app.func.__name__] = cast(Callable[..., Any], impl)

    return sym_bindings, func_bindings


def _require_bound_unknown_functions(expr: sp.Basic, printer: NumPyPrinter, func_bindings: Mapping[str, Callable[..., Any]]) -> None:
    """Ensure any *bare* printed function calls have runtime bindings."""
    missing: set[str] = set()

    for app in expr.atoms(sp.Function):
        name = app.func.__name__
        try:
            code = printer.doprint(app).strip()
        except Exception:
            continue

        if code.startswith(f"{name}(") and name not in func_bindings:
            missing.add(name)

    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(
            "Expression contains unknown SymPy function(s) that require a NumPy implementation: "
            f"{missing_str}. Define `<F>.f_numpy` on the function class (e.g. via @NamedFunction), "
            "or pass `f_numpy={F: callable}` to numpify."
        )


# ---------------------------------------------------------------------------
# Cached compilation
# ---------------------------------------------------------------------------

_NUMPIFY_CACHE_MAXSIZE = 256


def _freeze_value_marker(value: Any) -> tuple[str, Any]:
    """Return a hashable marker for *value*.

    We prefer using the value itself when it is hashable (stable semantics).
    If it is unhashable (e.g. NumPy arrays, dicts), fall back to object identity.

    Notes
    -----
    - Using ``id(value)`` means cache hits are session-local and depend on the
      specific object instance. This is usually what you want for injected
      constants like arrays.
    """
    try:
        hash(value)
    except Exception:
        return ("ID", id(value))
    else:
        return ("H", value)


def _freeze_f_numpy_key(f_numpy: Optional[Mapping[_BindingKey, Any]]) -> tuple[tuple[Any, ...], ...]:
    """Normalize ``f_numpy`` to a hashable key for caching.

    The key is a sorted tuple of entries. Each entry includes:

    - a *normalized binding key* (symbol/function name identity)
    - a *value marker* (hashable value when possible, otherwise ``id(value)``)

    This function is intentionally conservative: it aims to prevent incorrect
    cache hits when bindings differ.
    """
    if not f_numpy:
        return tuple()

    frozen: list[tuple[Any, ...]] = []
    for k, v in f_numpy.items():
        if isinstance(k, sp.Symbol):
            k_norm = ("S", k.name)
        elif isinstance(k, sp.Function):
            # Bindings for applications behave like bindings for their function class.
            fc = k.func
            k_norm = ("F", getattr(fc, "__module__", ""), getattr(fc, "__qualname__", fc.__name__))
        elif isinstance(k, FunctionClass):
            k_norm = ("F", getattr(k, "__module__", ""), getattr(k, "__qualname__", k.__name__))
        else:
            # Should not happen: numpify() validates keys.
            k_norm = ("K", repr(k))

        v_mark = _freeze_value_marker(v)
        frozen.append((k_norm, v_mark))

    frozen.sort(key=lambda item: item[0])
    return tuple(tuple(x) for x in frozen)


class _FrozenFNumPy:
    """Small hashable wrapper around an ``f_numpy`` mapping.

    This exists solely so that :func:`functools.lru_cache` can cache compiled
    callables even when the mapping contains unhashable values (like NumPy arrays).

    The cache key is derived from a normalized, hashable view of the mapping.
    """

    __slots__ = ("mapping", "_key")

    def __init__(self, mapping: Optional[Mapping[_BindingKey, Any]]):
        """Copy and normalize ``f_numpy`` mapping for cache-key construction."""
        self.mapping: dict[_BindingKey, Any] = {} if mapping is None else dict(mapping)
        self._key = _freeze_f_numpy_key(self.mapping)

    def __hash__(self) -> int:  # pragma: no cover
        """Return hash of the frozen normalized mapping key."""
        return hash(self._key)

    def __eq__(self, other: object) -> bool:  # pragma: no cover
        """Compare two frozen wrappers by their normalized binding keys."""
        return isinstance(other, _FrozenFNumPy) and self._key == other._key


@lru_cache(maxsize=_NUMPIFY_CACHE_MAXSIZE)
def _numpify_cached_impl(
    expr: sp.Basic,
    vars_tuple: Tuple[sp.Symbol, ...],
    vars_spec_key: Any,
    frozen: _FrozenFNumPy,
    vectorize: bool,
    expand_definition: bool,
) -> NumericFunction:
    """Compile an expression on cache misses for :func:`numpify_cached`."""
    # NOTE: This function body only runs on cache *misses*.
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "numpify_cached: cache MISS (vars=%s, vectorize=%s, expand_definition=%s)",
            [a.name for a in vars_tuple],
            vectorize,
            expand_definition,
        )
    # Delegate to the uncached compiler for actual compilation.
    return _numpify_uncached(
        expr,
        vars=_thaw_vars_spec(vars_spec_key),
        f_numpy=frozen.mapping,
        vectorize=vectorize,
        expand_definition=expand_definition,
    )


def numpify_cached(
    expr: Any,
    *,
    vars: _VarsInput | None = None,
    f_numpy: Optional[Mapping[_BindingKey, Any]] = None,
    vectorize: bool = True,
    expand_definition: bool = True,
) -> NumericFunction:
    """Cached version of :func:`numpify`.

    This is a convenience wrapper for interactive sessions where the same SymPy
    expression is compiled repeatedly.

    Cache key
    ---------
    The cache key includes:

    - the SymPy expression (after :func:`sympy.sympify`),
    - the normalized vars tuple ``vars``,
    - a normalized, hashable view of ``f_numpy``,
    - and the options ``vectorize`` / ``expand_definition``.

    Parameters
    ----------
    expr, vars, f_numpy, vectorize, expand_definition:
        Same meaning as in :func:`numpify`.

    Returns
    -------
    Callable[..., Any]
        The compiled callable, reused across cache hits.

    Notes
    -----
    - If you mutate objects referenced by ``f_numpy`` (e.g. change entries of a
      NumPy array), cached callables will see the mutated object because the
      compiled function captures the object by reference.
    - If you need a fresh compile, call :func:`numpify` with ``cache=False`` or clear the
      cache via ``numpify_cached.cache_clear()``.
    """
    # Normalize to SymPy and vars tuple exactly as numpify() does.
    expr_sym = cast(sp.Basic, sp.sympify(expr))
    if not isinstance(expr_sym, sp.Basic):
        raise TypeError(f"numpify_cached expects a SymPy expression, got {type(expr_sym)}")

    normalized_vars = _normalize_vars(expr_sym, vars)
    vars_tuple = normalized_vars["all"]
    vars_spec_key = normalized_vars["spec_key"]
    frozen = _FrozenFNumPy(f_numpy)

    return _numpify_cached_impl(
        expr_sym,
        vars_tuple,
        vars_spec_key,
        frozen,
        vectorize,
        expand_definition,
    )


# Expose cache controls on the public wrapper.
numpify_cached.cache_info = _numpify_cached_impl.cache_info  # type: ignore[attr-defined]
numpify_cached.cache_clear = _numpify_cached_impl.cache_clear  # type: ignore[attr-defined]
