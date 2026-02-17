"""Immutable snapshots of Figure parameter state.

A snapshot captures a deep-copied mapping of ``Symbol -> metadata`` so code can
perform deterministic calculations without depending on mutable widget state.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Dict

from sympy.core.symbol import Symbol


class ParameterValueSnapshot(Mapping[Symbol, Any]):
    """Immutable symbol-keyed view of parameter values with name lookup support.

    Lookup accepts the original :class:`sympy.Symbol` keys and also accepts
    unambiguous symbol-name strings (for notebook ergonomics). Iteration and
    ``keys()`` remain symbol-based to preserve explicit symbolic workflows.
    """

    def __init__(self, entries: Mapping[Symbol, Mapping[str, Any]]) -> None:
        """Deep-copy value entries while preserving insertion order."""
        self._values: Dict[Symbol, Any] = {
            symbol: deepcopy(entry["value"]) for symbol, entry in entries.items()
        }

    def _resolve_symbol(self, key: Symbol | str) -> Symbol:
        """Resolve symbol-or-string keys to a concrete symbol or raise KeyError."""
        if isinstance(key, Symbol):
            return key
        if isinstance(key, str):
            matches = [symbol for symbol in self._values if symbol.name == key]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                options = ", ".join(repr(symbol) for symbol in matches)
                raise KeyError(
                    f"Ambiguous parameter name {key!r}; matches: {options}. "
                    "Use a Symbol key for explicit access."
                )
            raise KeyError(
                f"Unknown parameter name {key!r}. "
                "Use one of the registered symbols (or an unambiguous symbol name)."
            )
        raise KeyError(f"Unsupported key type {type(key).__name__}; use Symbol or str.")

    def __getitem__(self, key: Symbol | str) -> Any:
        """Return a detached parameter value for symbol or unambiguous name."""
        symbol = self._resolve_symbol(key)
        return deepcopy(self._values[symbol])

    def __iter__(self) -> Iterator[Symbol]:
        """Iterate symbols in insertion order."""
        return iter(self._values)

    def __len__(self) -> int:
        """Return the number of parameter entries in the snapshot."""
        return len(self._values)

    def __repr__(self) -> str:
        """Return developer-friendly representation of stored values."""
        return f"ParameterValueSnapshot({self._values!r})"


class ParameterSnapshot(Mapping[Symbol, Mapping[str, Any]]):
    """Immutable ordered snapshot of parameter values and optional metadata.

    Parameters
    ----------
    entries : Mapping[sympy.Symbol, Mapping[str, Any]]
        Source mapping keyed by parameter symbols.
    """

    def __init__(self, entries: Mapping[Symbol, Mapping[str, Any]]) -> None:
        """Copy source entries deeply while preserving insertion order."""
        self._entries: Dict[Symbol, Dict[str, Any]] = {
            symbol: deepcopy(dict(entry)) for symbol, entry in entries.items()
        }

    def _resolve_symbol(self, key: Symbol | str) -> Symbol:
        """Resolve symbol-or-string keys to a concrete symbol or raise KeyError."""
        if isinstance(key, Symbol):
            return key
        if isinstance(key, str):
            matches = [symbol for symbol in self._entries if symbol.name == key]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                options = ", ".join(repr(symbol) for symbol in matches)
                raise KeyError(
                    f"Ambiguous parameter name {key!r}; matches: {options}. "
                    "Use a Symbol key for explicit access."
                )
            raise KeyError(
                f"Unknown parameter name {key!r}. "
                "Use one of the registered symbols (or an unambiguous symbol name)."
            )
        raise KeyError(f"Unsupported key type {type(key).__name__}; use Symbol or str.")

    def __getitem__(self, key: Symbol | str) -> Mapping[str, Any]:
        """Return read-only metadata for a symbol or unambiguous symbol name."""
        symbol = self._resolve_symbol(key)
        return MappingProxyType(deepcopy(self._entries[symbol]))

    def __iter__(self) -> Iterator[Symbol]:
        """Iterate symbols in insertion order."""
        return iter(self._entries)

    def __len__(self) -> int:
        """Return the number of parameter entries in the snapshot."""
        return len(self._entries)

    def value_map(self) -> ParameterValueSnapshot:
        """Return an immutable ``Symbol -> value`` snapshot.

        Returns
        -------
        ParameterValueSnapshot
            Immutable value-only snapshot with symbol iteration and optional
            unambiguous string-name lookup.

        Examples
        --------
        >>> import sympy as sp
        >>> a = sp.Symbol("a")
        >>> snap = ParameterSnapshot({a: {"value": 1.5, "min": 0.0}})
        >>> snap.value_map()[a]
        1.5
        """
        return ParameterValueSnapshot(self._entries)

    def __eq__(self, other: object) -> bool:
        """Compare snapshots by ordered item content."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return list(self.items()) == list(other.items())

    def __repr__(self) -> str:
        """Return developer-friendly representation of stored payload."""
        return f"ParameterSnapshot({self._entries!r})"
