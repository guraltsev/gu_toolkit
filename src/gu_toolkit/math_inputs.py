"""Semantic notebook widgets for identifier and expression entry.

These widgets are the public, figure-independent boundary for MathLive-backed
math authoring in the toolkit. Figure editors compose them, but the widgets and
context transport live in the general semantic-math layer.
"""

from __future__ import annotations

from typing import Any

from ._mathlive_widget import MathLiveField
from .expression_context import ExpressionContext

__all__ = ["ExpressionInput", "IdentifierInput"]


class _SemanticMathInput(MathLiveField):
    """Common base for context-aware semantic math inputs."""

    def __init__(
        self,
        *args: object,
        context: ExpressionContext | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._context = ExpressionContext()
        self.smart_mode = False
        self.set_context(context)

    @property
    def context(self) -> ExpressionContext:
        """Public semantic-math helper on ``_SemanticMathInput`` for context.
        
        Full API
        --------
        ``obj.context(...)``
        
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
        This API lives in ``gu_toolkit.math_inputs`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.context(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(_SemanticMathInput)`` and inspect neighboring APIs in the same module.
        """
        return self._context

    def _refresh_semantic_context(self) -> None:
        """Refresh the transport snapshot sent to the MathLive backend."""

        self.semantic_context = self._context.transport_manifest(field_role=self.field_role)
        self.inline_shortcuts = dict(self._context.inline_shortcuts())
        self.menu_items = list(self._context.menu_items())
        self.known_identifiers = list(self._context.symbols.keys())
        self.known_functions = list(self._context.functions.keys())

    def set_context(self, context: ExpressionContext | None) -> None:
        """Public semantic-math helper on ``_SemanticMathInput`` for set_context.
        
        Full API
        --------
        ``obj.set_context(...)``
        
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
        This API lives in ``gu_toolkit.math_inputs`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.set_context(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(_SemanticMathInput)`` and inspect neighboring APIs in the same module.
        """
        self._context = context.copy() if context is not None else ExpressionContext()
        self._refresh_semantic_context()


class IdentifierInput(_SemanticMathInput):
    """Public semantic-math helper class for IdentifierInput.
    
    Full API
    --------
    ``IdentifierInput``
    
    Parameters
    ----------
    Constructor parameters follow the Python signature for this class.
    
    Returns
    -------
    IdentifierInput
        New ``IdentifierInput`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.math_inputs`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        obj = IdentifierInput(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(IdentifierInput)`` and inspect neighboring APIs in the same module.
    """

    def __init__(self, *args: object, context: ExpressionContext | None = None, **kwargs: object) -> None:
        kwargs.setdefault("aria_label", "Identifier input")
        kwargs.setdefault("field_role", "identifier")
        super().__init__(*args, context=context, **kwargs)

    def parse_value(self, *, context: ExpressionContext | None = None, role: str = "identifier") -> str:
        """Public semantic-math helper on ``IdentifierInput`` for parse_value.
        
        Full API
        --------
        ``obj.parse_value(...)``
        
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
        This API lives in ``gu_toolkit.math_inputs`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.parse_value(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(IdentifierInput)`` and inspect neighboring APIs in the same module.
        """
        ctx = context if context is not None else self._context
        return ctx.parse_identifier(self.value, role=role, math_json=self.math_json)


class ExpressionInput(_SemanticMathInput):
    """Public semantic-math helper class for ExpressionInput.
    
    Full API
    --------
    ``ExpressionInput``
    
    Parameters
    ----------
    Constructor parameters follow the Python signature for this class.
    
    Returns
    -------
    ExpressionInput
        New ``ExpressionInput`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.math_inputs`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        obj = ExpressionInput(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(ExpressionInput)`` and inspect neighboring APIs in the same module.
    """

    def __init__(self, *args: object, context: ExpressionContext | None = None, **kwargs: object) -> None:
        kwargs.setdefault("aria_label", "Expression input")
        kwargs.setdefault("field_role", "expression")
        super().__init__(*args, context=context, **kwargs)

    def parse_value(self, *, context: ExpressionContext | None = None, role: str = "expression") -> Any:
        """Public semantic-math helper on ``ExpressionInput`` for parse_value.
        
        Full API
        --------
        ``obj.parse_value(...)``
        
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
        This API lives in ``gu_toolkit.math_inputs`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
        
        Examples
        --------
        Basic use::
        
            result = obj.parse_value(...)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
        - In a notebook or REPL, run ``help(ExpressionInput)`` and inspect neighboring APIs in the same module.
        """
        ctx = context if context is not None else self._context
        return ctx.parse_expression(self.value, role=role, math_json=self.math_json)
