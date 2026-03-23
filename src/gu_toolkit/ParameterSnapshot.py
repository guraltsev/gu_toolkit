"""Immutable snapshots of Figure parameter state.

Parameter snapshots are now *name-authoritative*: the canonical key for a
parameter is its string name (``symbol.name``). Symbol objects remain accepted
for lookup and helper APIs, but they are normalized to their name before the
snapshot resolves an entry.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any

from sympy.core.symbol import Symbol

from .parameter_keys import ParameterKey, parameter_name, parameter_symbol



def _normalize_snapshot_entries(
    entries: Mapping[ParameterKey, Mapping[str, Any]],
    *,
    symbols: Mapping[ParameterKey, Symbol] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Symbol]]:
    """Return deep-copied name-keyed entries plus canonical symbols.

    Duplicate canonical names are rejected because a name-authoritative snapshot
    can only contain one entry per logical parameter.
    """
    normalized_entries: dict[str, dict[str, Any]] = {}
    canonical_symbols: dict[str, Symbol] = {}

    for raw_key, entry in entries.items():
        name = parameter_name(raw_key, role="parameter")
        if name in normalized_entries:
            raise ValueError(
                f"Duplicate parameter name {name!r} in snapshot entries. "
                "Snapshots are keyed by parameter name."
            )
        normalized_entries[name] = deepcopy(dict(entry))
        canonical_symbols[name] = parameter_symbol(raw_key, role="parameter")

    if symbols is not None:
        for raw_key, symbol in symbols.items():
            name = parameter_name(raw_key, role="parameter")
            if name not in normalized_entries:
                raise KeyError(
                    f"Canonical symbol {name!r} does not correspond to a snapshot entry."
                )
            if not isinstance(symbol, Symbol):
                raise TypeError(
                    "Canonical symbols mapping must contain sympy.Symbol values."
                )
            if symbol.name != name:
                raise ValueError(
                    f"Canonical symbol {symbol!r} does not match parameter name {name!r}."
                )
            canonical_symbols[name] = symbol

    return normalized_entries, canonical_symbols


class _ParameterSnapshotBase:
    """Shared name-resolution helpers for parameter snapshots."""

    _symbols_by_name: dict[str, Symbol]

    def _resolve_name(self, key: ParameterKey) -> str:
        name = parameter_name(key, role="parameter")
        if name not in self._symbols_by_name:
            raise KeyError(
                f"Unknown parameter name {name!r}. "
                "Use one of the registered parameter names."
            )
        return name

    def __contains__(self, key: object) -> bool:  # pragma: no cover - trivial
        try:
            name = parameter_name(key, role="parameter")  # type: ignore[arg-type]
        except TypeError:
            return False
        return name in self._symbols_by_name

    def symbol_for_name(self, key: ParameterKey) -> Symbol:
        """Return the canonical symbol recorded for ``key``."""
        return self._symbols_by_name[self._resolve_name(key)]

    @property
    def symbols(self) -> tuple[Symbol, ...]:
        """Return canonical symbols in snapshot order."""
        return tuple(self._symbols_by_name[name] for name in self)  # type: ignore[misc]

    def symbol_items(self):
        """Iterate ``(canonical_symbol, value)`` pairs in snapshot order."""
        for name in self:  # type: ignore[misc]
            yield self._symbols_by_name[name], self[name]  # type: ignore[index]


class ParameterValueSnapshot(_ParameterSnapshotBase, Mapping[str, Any]):
    """Immutable name-keyed view of parameter values.

    Iteration and mapping views expose canonical string names. Symbol keys remain
    accepted as aliases and are resolved through ``symbol.name``.
    """

    def __init__(
        self,
        entries: Mapping[ParameterKey, Mapping[str, Any]],
        *,
        symbols: Mapping[ParameterKey, Symbol] | None = None,
    ) -> None:
        normalized_entries, self._symbols_by_name = _normalize_snapshot_entries(
            entries,
            symbols=symbols,
        )
        self._values: dict[str, Any] = {
            name: deepcopy(entry["value"]) for name, entry in normalized_entries.items()
        }

    def __getitem__(self, key: ParameterKey) -> Any:
        name = self._resolve_name(key)
        return deepcopy(self._values[name])

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"ParameterValueSnapshot({self._values!r})"


class ParameterSnapshot(_ParameterSnapshotBase, Mapping[str, Mapping[str, Any]]):
    """Immutable ordered snapshot of parameter values and optional metadata.

    Parameters
    ----------
    entries : Mapping[str | sympy.Symbol, Mapping[str, Any]]
        Source mapping keyed by canonical parameter name or by a SymPy symbol.
        Symbols are normalized to ``symbol.name``.
    symbols : Mapping[str | sympy.Symbol, sympy.Symbol], optional
        Optional canonical-symbol map used to preserve the representative symbol
        chosen for each parameter name.
    """

    def __init__(
        self,
        entries: Mapping[ParameterKey, Mapping[str, Any]],
        *,
        symbols: Mapping[ParameterKey, Symbol] | None = None,
    ) -> None:
        self._entries, self._symbols_by_name = _normalize_snapshot_entries(
            entries,
            symbols=symbols,
        )

    def __getitem__(self, key: ParameterKey) -> Mapping[str, Any]:
        name = self._resolve_name(key)
        return MappingProxyType(deepcopy(self._entries[name]))

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def value_map(self) -> ParameterValueSnapshot:
        """Return an immutable ``name -> value`` snapshot.

        Symbol inputs remain accepted as aliases for name lookup.
        """
        return ParameterValueSnapshot(self._entries, symbols=self._symbols_by_name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return NotImplemented
        return list(self.items()) == list(other.items())

    def __repr__(self) -> str:
        return f"ParameterSnapshot({self._entries!r})"
