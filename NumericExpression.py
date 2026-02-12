"""Numeric-expression views built on top of numpified callables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

import sympy as sp
from sympy.core.symbol import Symbol

from .numpify import DYNAMIC_PARAMETER, BoundNumpifiedFunction, NumpifiedFunction, ParameterContext

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class PlotView:
    """Live view of a plot's numeric evaluation based on parameter context."""

    _numpified: NumpifiedFunction
    _provider: ParameterContext

    def __call__(self, x: "np.ndarray") -> "np.ndarray":
        """Evaluate using current provider-backed parameter values."""
        return self._numpified.set_parameter_context(self._provider).freeze({
            sym: DYNAMIC_PARAMETER for sym in self._numpified.parameters[1:]
        })(x)

    def freeze(self, values: dict[Symbol, Any]) -> BoundNumpifiedFunction:
        """Create a snapshot-frozen expression from explicit values."""
        return self._numpified.freeze(values)

    def unbind(self) -> NumpifiedFunction:
        """Return the underlying unbound numpified function."""
        return self._numpified

    @property
    def expr(self) -> sp.Basic:
        """Return underlying symbolic expression."""
        return self._numpified.expr

    @property
    def args(self) -> tuple[Symbol, ...]:
        """Return ordered function argument symbols."""
        return self._numpified.args
