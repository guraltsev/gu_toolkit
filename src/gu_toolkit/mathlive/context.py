"""Context-aware symbolic parsing and rendering helpers.

``ExpressionContext`` collects the symbol and function names that should remain
atomic during parsing and that should use semantic display names when rendered.
The context is intentionally lightweight so UI layers and notebook helpers can
share the same naming rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

import sympy as sp
from sympy.core.expr import Expr
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from ..identifiers.policy import (
    IdentifierError,
    build_symbol_names,
    function_head_to_latex,
    identifier_to_latex,
    parse_identifier,
    render_latex,
    rewrite_wrapped_identifier_calls,
    scan_identifier_segment,
    semantic_function,
    strip_math_delimiters,
    symbol,
    symbol_latex_override,
    validate_identifier,
)
from .transport import (
    MathJSONParseError,
    _is_empty_mathjson_payload,
    build_mathlive_transport_manifest,
    mathjson_to_identifier,
    mathjson_to_sympy,
)

__all__ = [
    "ExpressionContext",
    "FunctionSpec",
    "SymbolSpec",
]


_PARSE_EXPR_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)
_LATEX_FUNCTION_ALIASES = {"ln": "log"}
_BUILTIN_FUNCTION_NAMES = {
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "csc",
    "sinh",
    "cosh",
    "tanh",
    "log",
    "exp",
    "sqrt",
}
_LATEX_SPACING_COMMANDS = (r"\,", r"\;", r"\!", r"\quad", r"\qquad")


@dataclass(frozen=True)
class SymbolSpec:
    """Immutable record describing one registered symbol inside an ``ExpressionContext``.
    
    Full API
    --------
    ``SymbolSpec(name: 'str', symbol: 'sp.Symbol', latex_expr: 'str') -> None``
    
    Parameters
    ----------
    name : str
        Canonical symbol name stored in the context registry.
    
    symbol : sp.Symbol
        Actual ``sympy.Symbol`` instance that should be used during parsing and expression building.
    
    latex_expr : str
        Display LaTeX that should represent the symbol in notebook rendering and MathLive menus.
    
    Returns
    -------
    SymbolSpec
        Immutable registry record bundling the canonical name, the actual ``sympy.Symbol`` instance, and the display LaTeX that should represent it.
    
    Optional arguments
    ------------------
    This record has no optional fields. Build it when you already know the canonical symbol name, the actual ``sympy.Symbol`` instance, and the display LaTeX you want the frontend to show.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import symbol
        from gu_toolkit.mathlive.context import SymbolSpec
    
        x = symbol("x")
        SymbolSpec(name="x", symbol=x, latex_expr="x")
    
    Discovery-oriented use::
    
        from gu_toolkit.mathlive import ExpressionContext
    
        help(ExpressionContext)
        dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
    """

    name: str
    symbol: sp.Symbol
    latex_expr: str


@dataclass(frozen=True)
class FunctionSpec:
    """Immutable record describing one registered semantic function head inside an ``ExpressionContext``.
    
    Full API
    --------
    ``FunctionSpec(name: 'str', function: 'type[sp.Function]', latex_head: 'str', arity: 'int | None' = None) -> None``
    
    Parameters
    ----------
    name : str
        Canonical function name stored in the context registry.
    
    function : type[sp.Function]
        Callable SymPy function class that should be invoked when the canonical name parses as a call head.
    
    latex_head : str
        Display LaTeX for the function head in rendering, menus, and templates.
    
    arity : int | None, optional
        Optional fixed number of positional arguments. ``None`` means the frontend should not assume a fixed arity.
    
    Returns
    -------
    FunctionSpec
        Immutable registry record bundling the canonical function name, the callable SymPy function class, its display head, and optional arity metadata.
    
    Optional arguments
    ------------------
    - ``arity=None``: leave arity unspecified when the frontend should not assume a fixed number of arguments.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers.policy import semantic_function
        from gu_toolkit.mathlive.context import FunctionSpec
    
        Force_t = semantic_function("Force_t")
        FunctionSpec(name="Force_t", function=Force_t, latex_head=r"\\operatorname{Force}_{t}")
    
    Discovery-oriented use::
    
        from gu_toolkit.mathlive import ExpressionContext
    
        help(ExpressionContext)
        dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
    """

    name: str
    function: type[sp.Function]
    latex_head: str
    arity: int | None = None


@dataclass
class _NormalizedExpression:
    text: str
    explicit_identifiers: set[str] = field(default_factory=set)


@dataclass
class ExpressionContext:
    """Registry of canonical symbols and functions used to parse, render, and transport semantic math input.
    
    Full API
    --------
    ``ExpressionContext(symbols: dict[str, SymbolSpec] = ..., functions: dict[str, FunctionSpec] = ...)``
    
    Most users next inspect ``ExpressionContext.from_symbols()``, ``register_symbol()``,
    ``register_function()``, ``parse_expression()``, and ``transport_manifest()``.
    
    Parameters
    ----------
    symbols : dict[str, SymbolSpec], optional
        Optional starting ``name -> SymbolSpec`` registry. Most callers prefer ``ExpressionContext.from_symbols()`` over constructing these dictionaries by hand.
    
    functions : dict[str, FunctionSpec], optional
        Optional starting ``name -> FunctionSpec`` registry. Most callers prefer ``ExpressionContext.from_symbols()`` or ``register_function()``.
    
    Returns
    -------
    ExpressionContext
        Registry object that keeps symbol parsing, expression parsing, LaTeX rendering, and MathJSON transport aligned around the same canonical names.
    
    Optional arguments
    ------------------
    Both constructor dictionaries are optional. In user code, ``ExpressionContext.from_symbols(...)`` is usually clearer than constructing ``SymbolSpec``/``FunctionSpec`` dictionaries by hand.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.mathlive import ExpressionContext
    
        ctx = ExpressionContext.from_symbols(["velocity"], include_named_functions=False)
        ctx.parse_expression("velocity + x")
    
    Discovery-oriented use::
    
        from gu_toolkit.mathlive import ExpressionContext
    
        help(ExpressionContext)
        dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
    """

    symbols: dict[str, SymbolSpec] = field(default_factory=dict)
    functions: dict[str, FunctionSpec] = field(default_factory=dict)

    @classmethod
    def from_symbols(
        cls,
        symbols: Iterable[str | sp.Symbol] = (),
        *,
        functions: Iterable[Any] = (),
        include_named_functions: bool = True,
    ) -> "ExpressionContext":
        """Build a context seeded from canonical symbols and semantic function heads.
        
        Full API
        --------
        ``ExpressionContext.from_symbols(symbols: 'Iterable[str | sp.Symbol]' = (), *, functions: 'Iterable[Any]' = (), include_named_functions: 'bool' = True) -> "'ExpressionContext'"``
        
        Parameters
        ----------
        symbols : Iterable[str | sp.Symbol], optional
            Canonical names or ``sympy.Symbol`` objects that should be treated as atomic symbols when parsing and rendering.
        
        functions : Iterable[Any], optional
            Semantic callable heads to register alongside the symbols. Items may be strings, semantic function classes, or already-built ``FunctionSpec`` objects.
        
        include_named_functions : bool, optional
            Whether to merge in every function currently exposed through the global ``NamedFunction`` registry. Pass ``False`` when you want the context to contain only the functions named explicitly in ``functions=``.
        
        Returns
        -------
        ExpressionContext
            Fresh context populated with the requested symbols and functions and, by default, any functions registered through ``NamedFunction``.
        
        Optional arguments
        ------------------
        - ``symbols=()``: Canonical names or ``sympy.Symbol`` objects that should be treated as atomic symbols when parsing and rendering.
        - ``functions=()``: Semantic callable heads to register alongside the symbols.
        - ``include_named_functions=True``: Merge the global ``NamedFunction`` registry in addition to the explicit ``functions=`` list.
        
        Architecture note
        -----------------
        Symbols and functions are tracked separately on purpose: ``velocity`` is an atomic symbol name, while ``Force(x)`` has a callable head plus arguments. Parsing, rendering, and transport need that distinction, so this constructor asks for ``symbols=`` and ``functions=`` separately. If you already have a SymPy expression, prefer ``from_expression(...)`` to infer both categories from the tree. If you are building a context incrementally, use ``register_symbol(...)`` and ``register_function(...)``.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ExpressionContext.from_symbols(
                ["velocity", "theta__x"],
                functions=["Force_t"],
                include_named_functions=False,
            )
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        ctx = cls()
        for sym in symbols:
            ctx.register_symbol(sym)
        for func in functions:
            ctx.register_function(func)
        if include_named_functions:
            ctx.register_named_functions()
        return ctx

    @classmethod
    def from_expression(
        cls,
        expr: Any,
        *,
        include_named_functions: bool = True,
    ) -> "ExpressionContext":
        """Infer a context from the free symbols and semantic functions already present in an expression.
        
        Full API
        --------
        ``ExpressionContext.from_expression(expr: 'Any', *, include_named_functions: 'bool' = True) -> "'ExpressionContext'"``
        
        Parameters
        ----------
        expr : Any
            Expression to inspect for free symbols and semantic function applications.
        
        include_named_functions : bool, optional
            Whether the returned context should also import the current global ``NamedFunction`` registry in addition to whatever the expression contains.
        
        Returns
        -------
        ExpressionContext
            Fresh context containing the free symbols and semantic function heads discovered in the supplied expression.
        
        Optional arguments
        ------------------
        - ``include_named_functions=True``: Whether the returned context should also import the current global ``NamedFunction`` registry in addition to whatever the expression contains.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.identifiers import symbol
            from gu_toolkit.mathlive import ExpressionContext
        
            x = symbol("x")
            ExpressionContext.from_expression(x + 1, include_named_functions=False)
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        ctx = cls.from_symbols((), include_named_functions=include_named_functions)
        try:
            sym_expr = sp.sympify(expr)
        except Exception:
            return ctx
        for sym in getattr(sym_expr, "free_symbols", set()):
            if isinstance(sym, sp.Symbol):
                ctx.register_symbol(sym)
        for application in sym_expr.atoms(sp.Function):
            func = getattr(application, "func", None)
            if func is None:
                continue
            if hasattr(func, "__gu_name__"):
                ctx.register_function(func)
        return ctx

    def copy(self) -> "ExpressionContext":
        """Return a shallow copy of the symbol and function registries held by this context.
        
        Full API
        --------
        ``ExpressionContext.copy() -> "'ExpressionContext'"``
        
        Parameters
        ----------
        This API does not define user-supplied parameters.
        
        Returns
        -------
        ExpressionContext
            New context with copied ``symbols`` and ``functions`` dictionaries. The contained ``SymbolSpec`` and ``FunctionSpec`` records are reused because they are immutable.
        
        Optional arguments
        ------------------
        This API has no optional parameters.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext.from_symbols(["x"], include_named_functions=False)
            clone = ctx.copy()
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        return ExpressionContext(symbols=dict(self.symbols), functions=dict(self.functions))

    def register_named_functions(self) -> "ExpressionContext":
        """Import and register every function currently present in the ``NamedFunction`` registry.
        
        Full API
        --------
        ``ExpressionContext.register_named_functions() -> "'ExpressionContext'"``
        
        Parameters
        ----------
        This API does not define user-supplied parameters.
        
        Returns
        -------
        ExpressionContext
            ``self`` so calls can be chained after importing the current ``NamedFunction`` registry.
        
        Optional arguments
        ------------------
        This API has no optional parameters.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext()
            ctx.register_named_functions()
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        try:
            from ..NamedFunction import get_named_function_registry
        except Exception:
            return self
        for func in get_named_function_registry().values():
            self.register_function(func)
        return self

    def register_symbol(
        self,
        value: str | sp.Symbol | SymbolSpec,
        *,
        latex_expr: str | None = None,
    ) -> sp.Symbol:
        """Add a canonical symbol and its display form to the context registry.
        
        Full API
        --------
        ``ExpressionContext.register_symbol(value: 'str | sp.Symbol | SymbolSpec', *, latex_expr: 'str | None' = None) -> 'sp.Symbol'``
        
        Parameters
        ----------
        value : str | sp.Symbol | SymbolSpec
            Canonical symbol name, ``sympy.Symbol``, or prebuilt ``SymbolSpec`` to store in the registry.
        
        latex_expr : str | None, optional
            Optional display-LaTeX override to associate with the symbol when ``value`` is not already a ``SymbolSpec``.
        
        Returns
        -------
        sp.Symbol
            Registered SymPy symbol. The matching ``SymbolSpec`` is stored in ``self.symbols`` under its canonical name.
        
        Optional arguments
        ------------------
        - ``latex_expr=None``: Optional display-LaTeX override to associate with the symbol when ``value`` is not already a ``SymbolSpec``.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext()
            ctx.register_symbol("theta__x")
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        if isinstance(value, SymbolSpec):
            spec = value
        else:
            if isinstance(value, sp.Symbol):
                sym = value
                name = validate_identifier(sym.name, role="symbol")
            else:
                name = validate_identifier(str(value), role="symbol")
                sym = symbol(name)
            display = latex_expr or symbol_latex_override(sym) or identifier_to_latex(name)
            spec = SymbolSpec(name=name, symbol=sym, latex_expr=display)
        self.symbols[spec.name] = spec
        return spec.symbol

    def register_function(
        self,
        value: str | type[sp.Function] | FunctionSpec,
        *,
        latex_head: str | None = None,
        arity: int | None = None,
    ) -> type[sp.Function]:
        """Add a canonical semantic function head and its display form to the context registry.
        
        Full API
        --------
        ``ExpressionContext.register_function(value: 'str | type[sp.Function] | FunctionSpec', *, latex_head: 'str | None' = None, arity: 'int | None' = None) -> 'type[sp.Function]'``
        
        Parameters
        ----------
        value : str | type[sp.Function] | FunctionSpec
            Canonical function name, semantic function class, or prebuilt ``FunctionSpec`` to store in the registry.
        
        latex_head : str | None, optional
            Optional display-LaTeX override for the function head when ``value`` is not already a ``FunctionSpec``.
        
        arity : int | None, optional
            Optional fixed arity metadata stored in the resulting ``FunctionSpec``.
        
        Returns
        -------
        type[sp.Function]
            Registered semantic function class. The matching ``FunctionSpec`` is stored in ``self.functions`` under its canonical name.
        
        Optional arguments
        ------------------
        - ``latex_head=None``: Optional display-LaTeX override for the function head when ``value`` is not already a ``FunctionSpec``.
        - ``arity=None``: Optional fixed arity metadata stored in the resulting ``FunctionSpec``.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext()
            ctx.register_function("Force_t")
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        if isinstance(value, FunctionSpec):
            spec = value
        else:
            if isinstance(value, str):
                name = validate_identifier(value, role="function")
                func = semantic_function(name, latex_head=latex_head)
            else:
                func = value
                raw_name = getattr(func, "__gu_name__", getattr(func, "__name__", str(func)))
                name = validate_identifier(str(raw_name), role="function")
            head = latex_head or getattr(func, "__gu_latex__", None) or function_head_to_latex(name)
            if arity is None:
                raw_arity = getattr(func, "nargs", None)
                if isinstance(raw_arity, int):
                    arity = raw_arity
            spec = FunctionSpec(name=name, function=func, latex_head=head, arity=arity)
        self.functions[spec.name] = spec
        return spec.function

    def register_expression(self, expr: Any) -> "ExpressionContext":
        """Merge the symbols and semantic function heads found in an expression into the context.
        
        Full API
        --------
        ``ExpressionContext.register_expression(expr: 'Any') -> "'ExpressionContext'"``
        
        Parameters
        ----------
        expr : Any
            Expression, symbol, or SymPy-compatible value to inspect, render, or parse against.
        
        Returns
        -------
        ExpressionContext
            ``self`` after merging any free symbols and semantic function heads found in the supplied expression.
        
        Optional arguments
        ------------------
        This API has no optional parameters.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.identifiers import symbol
            from gu_toolkit.mathlive import ExpressionContext
        
            x = symbol("x")
            ctx = ExpressionContext()
            ctx.register_expression(x + 1)
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        other = ExpressionContext.from_expression(expr, include_named_functions=False)
        self.symbols.update(other.symbols)
        self.functions.update(other.functions)
        return self

    def local_dict(self) -> dict[str, Any]:
        """Return the parse dictionary that maps registered canonical names to SymPy objects.
        
        Full API
        --------
        ``ExpressionContext.local_dict() -> 'dict[str, Any]'``
        
        Parameters
        ----------
        This API does not define user-supplied parameters.
        
        Returns
        -------
        dict[str, Any]
            Dictionary suitable for ``parse_expr(..., local_dict=...)`` so registered names resolve as atomic symbols or callable function heads.
        
        Optional arguments
        ------------------
        This API has no optional parameters.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext.from_symbols(["x"], include_named_functions=False)
            ctx.local_dict()["x"]
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        mapping: dict[str, Any] = {}
        for spec in self.symbols.values():
            mapping[spec.name] = spec.symbol
        for spec in self.functions.values():
            mapping[spec.name] = spec.function
        return mapping

    def symbol_name_map(self, expr: Any) -> dict[sp.Symbol, str]:
        """Build the explicit ``symbol_names`` mapping used to render an expression with this context's display names.
        
        Full API
        --------
        ``ExpressionContext.symbol_name_map(expr: 'Any') -> 'dict[sp.Symbol, str]'``
        
        Parameters
        ----------
        expr : Any
            Expression, symbol, or SymPy-compatible value to inspect, render, or parse against.
        
        Returns
        -------
        dict[sp.Symbol, str]
            SymPy ``symbol_names`` mapping derived from this context's registered symbol display forms and any overrides already attached to the expression.
        
        Optional arguments
        ------------------
        This API has no optional parameters.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.identifiers import symbol
            from gu_toolkit.mathlive import ExpressionContext
        
            theta_x = symbol("theta__x")
            ctx = ExpressionContext.from_symbols([theta_x], include_named_functions=False)
            ctx.symbol_name_map(theta_x)
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        explicit = {spec.symbol: spec.latex_expr for spec in self.symbols.values()}
        return build_symbol_names(expr, explicit=explicit)

    def render_latex(self, expr: Any) -> str:
        """Render an expression using this context's semantic symbol registry.
        
        Full API
        --------
        ``ExpressionContext.render_latex(expr: 'Any') -> 'str'``
        
        Parameters
        ----------
        expr : Any
            Expression, symbol, or SymPy-compatible value to inspect, render, or parse against.
        
        Returns
        -------
        str
            LaTeX string for the expression, produced by ``sympy.latex(...)`` after the context supplies semantic ``symbol_names`` metadata and function-head hooks.
        
        Optional arguments
        ------------------
        This API has no optional parameters.
        
        Architecture note
        -----------------
        This is a convenience wrapper, not a competing LaTeX engine. ``ExpressionContext.render_latex(...)`` delegates to ``gu_toolkit.identifiers.render_latex(...)``, which in turn calls ``sympy.latex(...)`` with ``self.symbol_name_map(expr)`` so registered symbol display names and semantic function hooks reach SymPy's printer.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.identifiers import symbol
            from gu_toolkit.mathlive import ExpressionContext
        
            theta_x = symbol("theta__x")
            ctx = ExpressionContext.from_symbols([theta_x], include_named_functions=False)
            ctx.render_latex(theta_x + 1)
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        return render_latex(expr, symbol_names=self.symbol_name_map(expr))

    def known_identifiers(self) -> tuple[str, ...]:
        """Return the sorted union of registered symbol names and function names.
        
        Full API
        --------
        ``ExpressionContext.known_identifiers() -> 'tuple[str, ...]'``
        
        Parameters
        ----------
        This API does not define user-supplied parameters.
        
        Returns
        -------
        tuple[str, ...]
            Sorted tuple containing every canonical symbol name and function name registered in the context.
        
        Optional arguments
        ------------------
        This API has no optional parameters.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext.from_symbols(["x"], functions=["Force_t"], include_named_functions=False)
            ctx.known_identifiers()
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        names = set(self.symbols) | set(self.functions)
        return tuple(sorted(names))

    def inline_shortcuts(self) -> dict[str, str]:
        """Return the shortcut map sent to MathLive for registered symbols and function heads.
        
        Full API
        --------
        ``ExpressionContext.inline_shortcuts() -> 'dict[str, str]'``
        
        Parameters
        ----------
        This API does not define user-supplied parameters.
        
        Returns
        -------
        dict[str, str]
            Mapping from canonical names to the LaTeX snippets the frontend should insert when users choose a registered symbol or function.
        
        Optional arguments
        ------------------
        This API has no optional parameters.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext.from_symbols(["x"], functions=["Force_t"], include_named_functions=False)
            ctx.inline_shortcuts()
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        mapping: dict[str, str] = {}
        for spec in self.symbols.values():
            mapping[spec.name] = spec.latex_expr
        for spec in self.functions.values():
            mapping[spec.name] = spec.latex_head
        return mapping

    def menu_items(self) -> list[dict[str, str]]:
        """Return the menu entries sent to MathLive for registered symbols and function heads.
        
        Full API
        --------
        ``ExpressionContext.menu_items() -> 'list[dict[str, str]]'``
        
        Parameters
        ----------
        This API does not define user-supplied parameters.
        
        Returns
        -------
        list[dict[str, str]]
            Sorted list of frontend menu-item dictionaries describing each registered symbol and function.
        
        Optional arguments
        ------------------
        This API has no optional parameters.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext.from_symbols(["x"], functions=["Force_t"], include_named_functions=False)
            ctx.menu_items()
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        items: list[dict[str, str]] = []
        for spec in sorted(self.symbols.values(), key=lambda item: item.name.lower()):
            items.append(
                {
                    "kind": "symbol",
                    "id": f"symbol:{spec.name}",
                    "name": spec.name,
                    "label": spec.name,
                    "latex": spec.latex_expr,
                }
            )
        for spec in sorted(self.functions.values(), key=lambda item: item.name.lower()):
            items.append(
                {
                    "kind": "function",
                    "id": f"function:{spec.name}",
                    "name": spec.name,
                    "label": spec.name,
                    "latex": spec.latex_head,
                    "template": f"{spec.latex_head}(#0)",
                }
            )
        return items

    def transport_manifest(self, *, field_role: str = "math") -> dict[str, Any]:
        """Build the JSON-safe semantic context manifest sent to the MathLive frontend.
        
        Full API
        --------
        ``ExpressionContext.transport_manifest(*, field_role: 'str' = 'math') -> 'dict[str, Any]'``
        
        Parameters
        ----------
        field_role : str, optional
            Frontend hint describing what the widget is editing, for example ``"identifier"``, ``"expression"``, or ``"math"``.
        
        Returns
        -------
        dict[str, Any]
            Derived frontend snapshot with top-level ``version``, ``fieldRole``, ``symbols``, and ``functions`` keys. Symbol entries expose ``name``/``latex`` metadata; function entries expose ``name``/``latexHead``/``template`` metadata.
        
        Optional arguments
        ------------------
        - ``field_role='math'``: Frontend hint describing what the widget is editing, for example ``"identifier"``, ``"expression"``, or ``"math"``.
        
        Architecture note
        -----------------
        This method stays on ``ExpressionContext`` because the context owns the symbol/function registry. The method delegates to ``build_mathlive_transport_manifest()`` so widgets and tests can share the same manifest-building rules. Treat the result as a derived frontend transport contract, not as the primary Python authoring interface; most users should inspect ``self.symbols`` and ``self.functions`` first.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext.from_symbols(["x"], functions=["Force_t"], include_named_functions=False)
            ctx.transport_manifest(field_role="expression")
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """

        return build_mathlive_transport_manifest(self, field_role=field_role)

    def parse_identifier(self, text: str, *, role: str = "identifier", math_json: Any | None = None) -> str:
        """Parse identifier input using this context and, when available, the accompanying MathJSON payload.
        
        Full API
        --------
        ``ExpressionContext.parse_identifier(text: 'str', *, role: 'str' = 'identifier', math_json: 'Any | None' = None) -> 'str'``
        
        Parameters
        ----------
        text : str
            User-supplied identifier or expression text. The text may already be canonical or may use one of the supported display-LaTeX spellings.
        
        role : str, optional
            Human-readable noun used in error messages when validation or parsing fails.
        
        math_json : Any | None, optional
            Structured MathJSON payload emitted by MathLive. When valid and non-empty, it is preferred over plain text because it preserves semantic structure.
        
        Returns
        -------
        str
            Canonical identifier spelling produced from ``text`` or, when provided, from the accompanying MathJSON payload.
        
        Optional arguments
        ------------------
        - ``role='identifier'``: Human-readable noun used in error messages when validation or parsing fails.
        - ``math_json=None``: Structured MathJSON payload emitted by MathLive. When valid and non-empty, it is preferred over plain text because it preserves semantic structure.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext()
            ctx.parse_identifier(r"\\theta")
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        source = str(text or "").strip()

        if math_json is not None and not _is_empty_mathjson_payload(math_json):
            try:
                return mathjson_to_identifier(math_json, context=self, role=role)
            except MathJSONParseError as exc:
                if not source:
                    raise ValueError(f"Could not parse {role}: {exc}") from exc

        if not source:
            raise ValueError(f"{role} is required.")

        try:
            return parse_identifier(source)
        except IdentifierError as exc:
            raise ValueError(f"Could not parse {role}: {exc}") from exc

    def parse_expression(self, text: str, *, role: str = "expression", math_json: Any | None = None) -> Expr:
        """Parse expression input using this context and, when available, the accompanying MathJSON payload.
        
        Full API
        --------
        ``ExpressionContext.parse_expression(text: 'str', *, role: 'str' = 'expression', math_json: 'Any | None' = None) -> 'Expr'``
        
        Parameters
        ----------
        text : str
            User-supplied identifier or expression text. The text may already be canonical or may use one of the supported display-LaTeX spellings.
        
        role : str, optional
            Human-readable noun used in error messages when validation or parsing fails.
        
        math_json : Any | None, optional
            Structured MathJSON payload emitted by MathLive. When valid and non-empty, it is preferred over plain text because it preserves semantic structure.
        
        Returns
        -------
        Expr
            SymPy expression parsed from ``text`` or, when provided and valid, from the accompanying MathJSON payload.
        
        Optional arguments
        ------------------
        - ``role='expression'``: Human-readable noun used in error messages when validation or parsing fails.
        - ``math_json=None``: Structured MathJSON payload emitted by MathLive. When valid and non-empty, it is preferred over plain text because it preserves semantic structure.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.context``, the reusable registry between identifier policy and notebook widgets. It owns semantic name registration so parsing, rendering, and transport all consult the same context rather than hidden global state.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            ctx = ExpressionContext.from_symbols(["velocity"], include_named_functions=False)
            ctx.parse_expression("velocity + x")
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionContext
        
            help(ExpressionContext)
            dir(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_expression_context.py`` and ``tests/semantic_math/test_mathlive_inputs.py``.
        """
        source = str(text or "").strip()

        if math_json is not None and not _is_empty_mathjson_payload(math_json):
            try:
                parsed = mathjson_to_sympy(math_json, context=self)
            except MathJSONParseError as exc:
                if not source:
                    raise ValueError(f"Could not parse {role}: {exc}") from exc
            else:
                if isinstance(parsed, Expr):
                    return parsed
                raise ValueError(f"Parsed {role} is not a SymPy expression.")

        if not source:
            raise ValueError(f"{role} is required.")

        normalized = _normalize_expression_text(source)
        protected_text, local_dict = _protect_known_names(
            normalized.text,
            context=self,
            explicit_identifiers=normalized.explicit_identifiers,
        )
        try:
            parsed = parse_expr(
                protected_text,
                local_dict=local_dict,
                transformations=_PARSE_EXPR_TRANSFORMS,
                evaluate=True,
            )
        except Exception as exc:
            raise ValueError(f"Could not parse {role}: {exc}") from exc
        if not isinstance(parsed, Expr):
            raise ValueError(f"Parsed {role} is not a SymPy expression.")
        return parsed


def _extract_braced_group(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise ValueError("Expected '{' while parsing LaTeX input.")
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise ValueError("Unbalanced braces in LaTeX input.")


def _rewrite_group_command(text: str, command: str, *, arity: int) -> str:
    result: list[str] = []
    index = 0
    while index < len(text):
        if not text.startswith(command, index):
            result.append(text[index])
            index += 1
            continue

        cursor = index + len(command)
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1

        groups: list[str] = []
        try:
            for _ in range(arity):
                group_text, cursor = _extract_braced_group(text, cursor)
                groups.append(group_text)
                while cursor < len(text) and text[cursor].isspace():
                    cursor += 1
        except ValueError:
            result.append(text[index])
            index += 1
            continue

        if command == r"\frac":
            result.append(f"(({groups[0]})/({groups[1]}))")
        elif command == r"\sqrt":
            result.append(f"sqrt({groups[0]})")
        else:  # pragma: no cover - defensive fallback
            result.append(" ".join(groups))
        index = cursor
    return "".join(result)


def _normalize_expression_text(text: str) -> _NormalizedExpression:
    source = strip_math_delimiters(str(text or "")).strip()
    if not source:
        return _NormalizedExpression(text="", explicit_identifiers=set())

    for command in _LATEX_SPACING_COMMANDS:
        source = source.replace(command, " ")
    source = source.replace(r"\left", "").replace(r"\right", "")
    source = source.replace(r"\cdot", " * ").replace(r"\times", " * ").replace("·", " * ")
    source = _rewrite_group_command(source, r"\frac", arity=2)
    source = _rewrite_group_command(source, r"\sqrt", arity=1)
    source = rewrite_wrapped_identifier_calls(source)

    result: list[str] = []
    explicit_identifiers: set[str] = set()
    index = 0
    previous_emits_atom = False

    while index < len(source):
        scanned = scan_identifier_segment(source, index)
        if scanned is None:
            char = source[index]
            if char in "}]":
                char = ")"
            elif char in "[{":
                char = "("
            result.append(char)
            previous_emits_atom = char.isalnum() or char == ")" or char == "_"
            index += 1
            continue

        token = scanned.canonical
        token = _LATEX_FUNCTION_ALIASES.get(token, token)
        if previous_emits_atom and token and token[0].isalnum():
            result.append(" ")
        result.append(token)
        if scanned.explicit and token not in _BUILTIN_FUNCTION_NAMES and token != "pi":
            explicit_identifiers.add(token)
        previous_emits_atom = True
        index = scanned.end

    normalized = "".join(result)
    normalized = re.sub(r"\s+", " ", normalized)
    return _NormalizedExpression(text=normalized.strip(), explicit_identifiers=explicit_identifiers)


def _replace_name_tokens(
    text: str,
    *,
    name: str,
    placeholder: str,
    function_call: bool,
) -> str:
    if function_call:
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?=\s*\()")
    else:
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    return pattern.sub(placeholder, text)


def _protect_known_names(
    text: str,
    *,
    context: ExpressionContext,
    explicit_identifiers: set[str],
) -> tuple[str, dict[str, Any]]:
    rewritten = text
    local_dict: dict[str, Any] = {}
    counter = 0

    def bind(value: Any, *, prefix: str) -> str:
        nonlocal counter
        placeholder = f"GU{prefix}{counter}"
        counter += 1
        local_dict[placeholder] = value
        return placeholder

    protected_function_names = set(context.functions)
    protected_symbol_names = set(context.symbols)

    explicit_function_names = {
        name
        for name in explicit_identifiers
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?=\s*\()", rewritten)
    }
    protected_function_names.update(explicit_function_names)

    for name in sorted(protected_function_names, key=len, reverse=True):
        if name in context.functions:
            func = context.functions[name].function
        else:
            func = semantic_function(name)
        placeholder = bind(func, prefix="FUNC")
        rewritten = _replace_name_tokens(
            rewritten,
            name=name,
            placeholder=placeholder,
            function_call=True,
        )

    protected_symbol_names.update(explicit_identifiers - explicit_function_names)
    for name in sorted(protected_symbol_names, key=len, reverse=True):
        if name in context.symbols:
            sym = context.symbols[name].symbol
        else:
            sym = symbol(name)
        placeholder = bind(sym, prefix="SYM")
        rewritten = _replace_name_tokens(
            rewritten,
            name=name,
            placeholder=placeholder,
            function_call=False,
        )

    return rewritten, local_dict
