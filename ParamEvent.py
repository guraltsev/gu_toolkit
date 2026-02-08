from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from sympy.core.symbol import Symbol

if TYPE_CHECKING:
    from .ParamRef import ParamRef


@dataclass(frozen=True)
class ParamEvent:
    """Normalized parameter change event."""
    parameter: Symbol
    old: Any
    new: Any
    ref: "ParamRef"
    raw: Any = None
