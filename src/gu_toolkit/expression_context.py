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

from .identifier_policy import (
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
from .mathlive_transport import (
    MathJSONParseError,
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
    """Public semantic-math helper class for SymbolSpec.
    
    Full API
    --------
    ``SymbolSpec``
    
    Parameters
    ----------
    Constructor parameters follow the Python signature for this class.
    
    Returns
    -------
    SymbolSpec
        New ``SymbolSpec`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        obj = SymbolSpec(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(SymbolSpec)`` and inspect neighboring APIs in the same module.
    """

    name: str
    symbol: sp.Symbol
    latex_expr: str


@dataclass(frozen=True)
class FunctionSpec:
    """Public semantic-math helper class for FunctionSpec.
    
    Full API
    --------
    ``FunctionSpec``
    
    Parameters
    ----------
    Constructor parameters follow the Python signature for this class.
    
    Returns
    -------
    FunctionSpec
        New ``FunctionSpec`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        obj = FunctionSpec(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(FunctionSpec)`` and inspect neighboring APIs in the same module.
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
    """Public semantic-math helper class for ExpressionContext.
    
    Full API
    --------
    ``ExpressionContext``
    
    Parameters
    ----------
    Constructor parameters follow the Python signature for this class.
    
    Returns
    -------
    ExpressionContext
        New ``ExpressionContext`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        obj = ExpressionContext(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
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
        """Public semantic-math helper on ``ExpressionContext`` for from_symbols.
        
        Full API
        --------
        ``obj.from_symbols(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.from_symbols(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
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
        """Public semantic-math helper on ``ExpressionContext`` for from_expression.
        
        Full API
        --------
        ``obj.from_expression(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.from_expression(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
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
        """Public semantic-math helper on ``ExpressionContext`` for copy.
        
        Full API
        --------
        ``obj.copy(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.copy(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """
        return ExpressionContext(symbols=dict(self.symbols), functions=dict(self.functions))

    def register_named_functions(self) -> "ExpressionContext":
        """Public semantic-math helper on ``ExpressionContext`` for register_named_functions.
        
        Full API
        --------
        ``obj.register_named_functions(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.register_named_functions(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """
        try:
            from .NamedFunction import get_named_function_registry
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
        """Public semantic-math helper on ``ExpressionContext`` for register_symbol.
        
        Full API
        --------
        ``obj.register_symbol(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.register_symbol(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
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
        """Public semantic-math helper on ``ExpressionContext`` for register_function.
        
        Full API
        --------
        ``obj.register_function(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.register_function(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
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
        """Public semantic-math helper on ``ExpressionContext`` for register_expression.
        
        Full API
        --------
        ``obj.register_expression(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.register_expression(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """
        other = ExpressionContext.from_expression(expr, include_named_functions=False)
        self.symbols.update(other.symbols)
        self.functions.update(other.functions)
        return self

    def local_dict(self) -> dict[str, Any]:
        """Public semantic-math helper on ``ExpressionContext`` for local_dict.
        
        Full API
        --------
        ``obj.local_dict(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.local_dict(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """
        mapping: dict[str, Any] = {}
        for spec in self.symbols.values():
            mapping[spec.name] = spec.symbol
        for spec in self.functions.values():
            mapping[spec.name] = spec.function
        return mapping

    def symbol_name_map(self, expr: Any) -> dict[sp.Symbol, str]:
        """Public semantic-math helper on ``ExpressionContext`` for symbol_name_map.
        
        Full API
        --------
        ``obj.symbol_name_map(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.symbol_name_map(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """
        explicit = {spec.symbol: spec.latex_expr for spec in self.symbols.values()}
        return build_symbol_names(expr, explicit=explicit)

    def render_latex(self, expr: Any) -> str:
        """Public semantic-math helper on ``ExpressionContext`` for render_latex.
        
        Full API
        --------
        ``obj.render_latex(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.render_latex(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """
        return render_latex(expr, symbol_names=self.symbol_name_map(expr))

    def known_identifiers(self) -> tuple[str, ...]:
        """Public semantic-math helper on ``ExpressionContext`` for known_identifiers.
        
        Full API
        --------
        ``obj.known_identifiers(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.known_identifiers(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """
        names = set(self.symbols) | set(self.functions)
        return tuple(sorted(names))

    def inline_shortcuts(self) -> dict[str, str]:
        """Public semantic-math helper on ``ExpressionContext`` for inline_shortcuts.
        
        Full API
        --------
        ``obj.inline_shortcuts(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.inline_shortcuts(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """
        mapping: dict[str, str] = {}
        for spec in self.symbols.values():
            mapping[spec.name] = spec.latex_expr
        for spec in self.functions.values():
            mapping[spec.name] = spec.latex_head
        return mapping

    def menu_items(self) -> list[dict[str, str]]:
        """Public semantic-math helper on ``ExpressionContext`` for menu_items.
        
        Full API
        --------
        ``obj.menu_items(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.menu_items(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
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
        """Public semantic-math helper on ``ExpressionContext`` for transport_manifest.
        
        Full API
        --------
        ``obj.transport_manifest(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.transport_manifest(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """

        return build_mathlive_transport_manifest(self, field_role=field_role)

    def parse_identifier(self, text: str, *, role: str = "identifier", math_json: Any | None = None) -> str:
        """Public semantic-math helper on ``ExpressionContext`` for parse_identifier.
        
        Full API
        --------
        ``obj.parse_identifier(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.parse_identifier(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """
        if math_json is not None:
            try:
                return mathjson_to_identifier(math_json, context=self, role=role)
            except MathJSONParseError as exc:
                if not str(text or "").strip():
                    raise ValueError(f"Could not parse {role}: {exc}") from exc

        try:
            return parse_identifier(text)
        except IdentifierError as exc:
            raise ValueError(f"Could not parse {role}: {exc}") from exc

    def parse_expression(self, text: str, *, role: str = "expression", math_json: Any | None = None) -> Expr:
        """Public semantic-math helper on ``ExpressionContext`` for parse_expression.
        
        Full API
        --------
        ``obj.parse_expression(...)``
        
        Parameters
        ----------
        This member accepts the parameters declared in its Python signature.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        Optional arguments follow the defaults declared in the Python signature when present.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.expression_context`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.parse_expression(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionContext)`` and inspect neighboring APIs in the same module.
        """
        source = str(text or "").strip()

        if math_json is not None:
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
