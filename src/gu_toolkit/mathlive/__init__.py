"""Semantic MathLive widgets, transport helpers, and expression context.

This subpackage is the canonical home for the figure-independent math
authoring stack: widget backend, public widgets, context-aware parsing, and
MathJSON transport helpers. Legacy top-level modules remain as
compatibility re-exports.
"""

from .context import ExpressionContext, FunctionSpec, SymbolSpec
from .inputs import ExpressionInput, IdentifierInput
from .transport import (
    MathJSONParseError,
    build_mathlive_transport_manifest,
    mathjson_to_identifier,
    mathjson_to_sympy,
)
from .widget import MathLiveField

__all__ = [
    "ExpressionContext",
    "ExpressionInput",
    "FunctionSpec",
    "IdentifierInput",
    "MathJSONParseError",
    "MathLiveField",
    "SymbolSpec",
    "build_mathlive_transport_manifest",
    "mathjson_to_identifier",
    "mathjson_to_sympy",
]
