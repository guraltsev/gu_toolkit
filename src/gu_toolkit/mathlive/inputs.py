"""Semantic notebook widgets for identifier and expression entry.

These widgets are the public, figure-independent boundary for MathLive-backed
math authoring in the toolkit. Figure editors compose them, but the widgets and
context transport live in the general semantic-math layer.
"""

from __future__ import annotations

from typing import Any

from .widget import MathLiveField
from .context import ExpressionContext

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
        self._trait_change_serial = 0
        self._value_change_serial = 0
        self._math_json_change_serial = 0
        self.observe(self._record_value_change, names="value")
        self.observe(self._record_math_json_change, names="math_json")
        self._seed_transport_change_order()
        self.smart_mode = False
        self.set_context(context)

    @property
    def context(self) -> ExpressionContext:
        """Return the ``ExpressionContext`` currently mirrored into the widget's synced state.
        
        Full API
        --------
        ``widget.context -> ExpressionContext``
        
        Parameters
        ----------
        This property does not accept call arguments. Read it to inspect the registry currently mirrored into the widget's synced state.
        
        Returns
        -------
        ExpressionContext
            The widget's current semantic context. The returned context is the source of truth used to populate ``semantic_context``, ``inline_shortcuts``, ``menu_items``, and known-name traits.
        
        Optional arguments
        ------------------
        This property has no call-time optional arguments because it is an attribute-style read of the current semantic context.
        
        Architecture note
        -----------------
        The context is stored on the shared semantic-input base class because both ``IdentifierInput`` and ``ExpressionInput`` need the same registry-to-widget synchronization logic.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import IdentifierInput
        
            widget = IdentifierInput()
            widget.context
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionInput, IdentifierInput
        
            help(ExpressionInput)
            help(IdentifierInput.parse_value)
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_mathlive_inputs.py`` and ``tests/semantic_math/test_expression_context.py``.
        """
        return self._context

    def _next_trait_change_serial(self) -> int:
        self._trait_change_serial += 1
        return self._trait_change_serial

    def _record_value_change(self, _change: dict[str, Any]) -> None:
        self._value_change_serial = self._next_trait_change_serial()

    def _record_math_json_change(self, _change: dict[str, Any]) -> None:
        self._math_json_change_serial = self._next_trait_change_serial()

    def _seed_transport_change_order(self) -> None:
        if self.value:
            self._value_change_serial = self._next_trait_change_serial()
        if self.math_json is not None:
            self._math_json_change_serial = self._next_trait_change_serial()

    def _current_math_json_payload(self) -> Any | None:
        payload = self.math_json
        if payload is None:
            return None

        current_value = str(self.value or "").strip()
        transport_source_value = str(self.transport_source_value or "").strip()

        if transport_source_value:
            return payload if transport_source_value == current_value else None

        if (
            self._math_json_change_serial
            and self._value_change_serial
            and self._math_json_change_serial < self._value_change_serial
        ):
            return None

        return payload

    def _refresh_semantic_context(self) -> None:
        """Refresh the transport snapshot sent to the MathLive backend."""

        self.semantic_context = self._context.transport_manifest(field_role=self.field_role)
        self.inline_shortcuts = dict(self._context.inline_shortcuts())
        self.menu_items = list(self._context.menu_items())
        self.known_identifiers = list(self._context.symbols.keys())
        self.known_functions = list(self._context.functions.keys())

    def set_context(self, context: ExpressionContext | None) -> None:
        """Replace the widget's semantic context and refresh the synced frontend manifest.
        
        Full API
        --------
        ``widget.set_context(context: ExpressionContext | None) -> None``
        
        Parameters
        ----------
        context : ExpressionContext | None
            ``ExpressionContext`` (or context-like object) that should resolve registered semantic names.
        
        Returns
        -------
        None
            ``None``. The method clones the supplied context (or creates an empty one) and refreshes the frontend-facing semantic metadata.
        
        Optional arguments
        ------------------
        - ``context=None``: replace the current context with a fresh empty ``ExpressionContext`` before resynchronizing widget state.
        
        Architecture note
        -----------------
        This mutator lives on the shared semantic-input base class because both public widgets need to clone the new context and refresh the same frontend-facing semantic metadata.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionContext, IdentifierInput
        
            widget = IdentifierInput()
            widget.set_context(ExpressionContext.from_symbols(["x"], include_named_functions=False))
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionInput, IdentifierInput
        
            help(ExpressionInput)
            help(IdentifierInput.parse_value)
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_mathlive_inputs.py`` and ``tests/semantic_math/test_expression_context.py``.
        """
        self._context = context.copy() if context is not None else ExpressionContext()
        self._refresh_semantic_context()


class IdentifierInput(_SemanticMathInput):
    """MathLive-backed widget for entering one canonical identifier.
    
    Full API
    --------
    ``IdentifierInput(*args: object, context: ExpressionContext | None = None, **kwargs: object)``
    
    Key members: ``widget.context``, ``widget.set_context(...)``, and ``widget.parse_value()``.
    
    Parameters
    ----------
    *args : object
        Positional arguments forwarded to ``MathLiveField``/``AnyWidget``.
    
    context : ExpressionContext | None, optional
        Optional semantic context that should define which identifiers remain atomic and which functions are callable.
    
    **kwargs : object
        Keyword arguments forwarded to ``MathLiveField``. Common examples are ``value=``, ``placeholder=``, ``read_only=``, and ``math_json=``.
    
    Returns
    -------
    IdentifierInput
        Widget instance specialized for identifier entry. It defaults ``field_role`` to ``"identifier"`` and exposes ``context``, ``set_context()``, and ``parse_value()``.
    
    Optional arguments
    ------------------
    - ``context=None``: start with an empty ``ExpressionContext`` and let callers register names later.
    - ``**kwargs``: forwarded to ``MathLiveField`` and may set synced traits such as ``value``, ``placeholder``, ``read_only``, or ``math_json``.
    - The constructor also defaults ``aria_label`` to ``"Identifier input"`` and ``field_role`` to ``"identifier"`` unless you override them.
    
    Architecture note
    -----------------
    This class lives in ``gu_toolkit.mathlive.inputs`` and specializes ``MathLiveField`` for the single-identifier workflow. It does not own parsing rules itself; instead it delegates to ``ExpressionContext.parse_identifier()`` so widget behavior matches the rest of the semantic-math stack.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.mathlive import IdentifierInput
    
        widget = IdentifierInput(value=r"\\theta")
    
    Discovery-oriented use::
    
        from gu_toolkit.mathlive import ExpressionInput, IdentifierInput
    
        help(ExpressionInput)
        help(IdentifierInput.parse_value)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_mathlive_inputs.py`` and ``tests/semantic_math/test_expression_context.py``.
    """

    def __init__(self, *args: object, context: ExpressionContext | None = None, **kwargs: object) -> None:
        kwargs.setdefault("aria_label", "Identifier input")
        kwargs.setdefault("field_role", "identifier")
        super().__init__(*args, context=context, **kwargs)

    def parse_value(self, *, context: ExpressionContext | None = None, role: str = "identifier") -> str:
        """Parse the widget's current value as a canonical identifier, preferring synchronized MathJSON when available.
        
        Full API
        --------
        ``widget.parse_value(*, context: 'ExpressionContext | None' = None, role: 'str' = 'identifier') -> 'str'``
        
        Parameters
        ----------
        context : ExpressionContext | None, optional
            ``ExpressionContext`` (or context-like object) that should resolve registered semantic names.
        
        role : str, optional
            Human-readable noun used in error messages when validation or parsing fails.
        
        Returns
        -------
        str
            Canonical identifier spelling parsed from the widget's current state. When ``math_json`` is present **and still synchronized with the current visible text** it is preferred over plain text so MathLive can preserve semantic structure without returning stale transport.
        
        Optional arguments
        ------------------
        - ``context=None``: ``ExpressionContext`` (or context-like object) that should resolve registered semantic names.
        - ``role='identifier'``: Human-readable noun used in error messages when validation or parsing fails.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.inputs``, the notebook-facing widget layer. It mirrors an ``ExpressionContext`` into synced widget traits and delegates parsing/transport to the semantic-math backend.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import IdentifierInput
        
            widget = IdentifierInput(value=r"\\theta")
            widget.parse_value()
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionInput, IdentifierInput
        
            help(ExpressionInput)
            help(IdentifierInput.parse_value)
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_mathlive_inputs.py`` and ``tests/semantic_math/test_expression_context.py``.
        """
        ctx = context if context is not None else self._context
        return ctx.parse_identifier(self.value, role=role, math_json=self._current_math_json_payload())


class ExpressionInput(_SemanticMathInput):
    """MathLive-backed widget for entering a SymPy expression that uses semantic names.
    
    Full API
    --------
    ``ExpressionInput(*args: object, context: ExpressionContext | None = None, **kwargs: object)``
    
    Key members: ``widget.context``, ``widget.set_context(...)``, and ``widget.parse_value()``.
    
    Parameters
    ----------
    *args : object
        Positional arguments forwarded to ``MathLiveField``/``AnyWidget``.
    
    context : ExpressionContext | None, optional
        Optional semantic context that should define which names the widget may treat as registered symbols/functions.
    
    **kwargs : object
        Keyword arguments forwarded to ``MathLiveField``. Common examples are ``value=``, ``placeholder=``, ``read_only=``, and ``math_json=``.
    
    Returns
    -------
    ExpressionInput
        Widget instance specialized for expression entry. It defaults ``field_role`` to ``"expression"`` and exposes ``context``, ``set_context()``, and ``parse_value()``.
    
    Optional arguments
    ------------------
    - ``context=None``: start with an empty ``ExpressionContext`` and let callers register names later.
    - ``**kwargs``: forwarded to ``MathLiveField`` and may set synced traits such as ``value``, ``placeholder``, ``read_only``, or ``math_json``.
    - The constructor also defaults ``aria_label`` to ``"Expression input"`` and ``field_role`` to ``"expression"`` unless you override them.
    
    Architecture note
    -----------------
    This class lives in ``gu_toolkit.mathlive.inputs`` and specializes ``MathLiveField`` for general expressions. It delegates parsing and transport decisions to ``ExpressionContext.parse_expression()`` so widget behavior matches the rest of the semantic-math stack.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.mathlive import ExpressionInput
    
        widget = ExpressionInput(value="x + 1")
    
    Discovery-oriented use::
    
        from gu_toolkit.mathlive import ExpressionInput, IdentifierInput
    
        help(ExpressionInput)
        help(IdentifierInput.parse_value)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_mathlive_inputs.py`` and ``tests/semantic_math/test_expression_context.py``.
    """

    def __init__(self, *args: object, context: ExpressionContext | None = None, **kwargs: object) -> None:
        kwargs.setdefault("aria_label", "Expression input")
        kwargs.setdefault("field_role", "expression")
        super().__init__(*args, context=context, **kwargs)

    def parse_value(self, *, context: ExpressionContext | None = None, role: str = "expression") -> Any:
        """Parse the widget's current value as a SymPy expression, preferring synchronized MathJSON when available.
        
        Full API
        --------
        ``widget.parse_value(*, context: 'ExpressionContext | None' = None, role: 'str' = 'expression') -> 'Any'``
        
        Parameters
        ----------
        context : ExpressionContext | None, optional
            ``ExpressionContext`` (or context-like object) that should resolve registered semantic names.
        
        role : str, optional
            Human-readable noun used in error messages when validation or parsing fails.
        
        Returns
        -------
        Any
            Parsed SymPy expression produced from the widget's current state. When ``math_json`` is present **and still synchronized with the current visible text** it is preferred over plain text so MathLive can preserve semantic structure without returning stale transport.
        
        Optional arguments
        ------------------
        - ``context=None``: ``ExpressionContext`` (or context-like object) that should resolve registered semantic names.
        - ``role='expression'``: Human-readable noun used in error messages when validation or parsing fails.
        
        Architecture note
        -----------------
        This API lives in ``gu_toolkit.mathlive.inputs``, the notebook-facing widget layer. It mirrors an ``ExpressionContext`` into synced widget traits and delegates parsing/transport to the semantic-math backend.
        
        Examples
        --------
        Basic use::
        
            from gu_toolkit.mathlive import ExpressionInput
        
            widget = ExpressionInput(value="x + 1")
            widget.parse_value()
        
        Discovery-oriented use::
        
            from gu_toolkit.mathlive import ExpressionInput, IdentifierInput
        
            help(ExpressionInput)
            help(IdentifierInput.parse_value)
        
        Learn more / explore
        --------------------
        - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
        - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
        - Showcase notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
        - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
        - Focused tests: ``tests/semantic_math/test_mathlive_inputs.py`` and ``tests/semantic_math/test_expression_context.py``.
        """
        ctx = context if context is not None else self._context
        return ctx.parse_expression(self.value, role=role, math_json=self._current_math_json_payload())
