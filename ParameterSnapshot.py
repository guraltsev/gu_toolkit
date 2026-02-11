from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Dict

from sympy.core.symbol import Symbol


class ParameterSnapshot(Mapping[Symbol, Mapping[str, Any]]):
    """Immutable ordered snapshot of parameter values and optional metadata."""

    def __init__(self, entries: Mapping[Symbol, Mapping[str, Any]]) -> None:
        # Preserve insertion order from source mapping while copying content.
        self._entries: Dict[Symbol, Dict[str, Any]] = {
            symbol: deepcopy(dict(entry)) for symbol, entry in entries.items()
        }

    def __getitem__(self, key: Symbol) -> Mapping[str, Any]:
        # Return a read-only mapping so callers cannot mutate snapshot state.
        return MappingProxyType(deepcopy(self._entries[key]))

    def __iter__(self) -> Iterator[Symbol]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def values_only(self) -> Dict[Symbol, Any]:
        """Return an ordered mapping of ``Symbol -> value`` from this snapshot."""
        return {symbol: entry["value"] for symbol, entry in self._entries.items()}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return NotImplemented
        return list(self.items()) == list(other.items())

    def __repr__(self) -> str:
        return f"ParameterSnapshot({self._entries!r})"
