"""Shared helpers for string-authoritative parameter identity.

The toolkit now treats the string form of a parameter (``symbol.name``) as the
canonical identifier across parameter registries, snapshots, and numeric
binding APIs. Symbol objects remain accepted for ergonomics, but they are first
normalized to their name before lookup or storage decisions are made.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Sequence
from typing import TypeAlias

import sympy as sp
from sympy.core.symbol import Symbol

ParameterKey: TypeAlias = str | Symbol
ParameterKeyOrKeys: TypeAlias = ParameterKey | Sequence[ParameterKey]


def parameter_name(key: ParameterKey, *, role: str = "parameter") -> str:
    """Return the canonical string identifier for *key*.

    Parameters
    ----------
    key:
        String parameter name or SymPy symbol.
    role:
        Human-readable label used in error messages.
    """
    if isinstance(key, str):
        return key
    if isinstance(key, Symbol):
        return key.name
    raise TypeError(
        f"{role} key must be a string or sympy.Symbol, got {type(key).__name__}"
    )


def parameter_symbol(key: ParameterKey, *, role: str = "parameter") -> Symbol:
    """Return a representative SymPy symbol for *key*.

    String keys are upgraded to plain ``sympy.Symbol(name)`` objects. Existing
    symbols are returned unchanged so their display/assumption metadata can be
    preserved when they are the first symbol registered for a name.
    """
    if isinstance(key, Symbol):
        return key
    if isinstance(key, str):
        return sp.Symbol(key)
    raise TypeError(
        f"{role} key must be a string or sympy.Symbol, got {type(key).__name__}"
    )


def normalize_parameter_sequence(
    keys: ParameterKeyOrKeys,
    *,
    role: str = "parameters",
) -> tuple[tuple[tuple[str, Symbol], ...], bool]:
    """Normalize one-or-many parameter keys to unique ``(name, symbol)`` pairs.

    The returned sequence preserves first-seen order and keeps the first symbol
    encountered for each canonical name. The boolean flag reports whether the
    caller supplied a single logical key.
    """
    if isinstance(keys, (str, Symbol)):
        raw_items = [keys]
        single = True
    else:
        raw_items = list(keys)
        single = False

    ordered: OrderedDict[str, Symbol] = OrderedDict()
    for raw_key in raw_items:
        name = parameter_name(raw_key, role=role)
        ordered.setdefault(name, parameter_symbol(raw_key, role=role))

    return tuple(ordered.items()), single


def group_symbols_by_name(symbols: Iterable[Symbol]) -> dict[str, tuple[Symbol, ...]]:
    """Group symbols by canonical parameter name while preserving input order."""
    grouped: OrderedDict[str, list[Symbol]] = OrderedDict()
    for symbol in symbols:
        grouped.setdefault(symbol.name, []).append(symbol)
    return {name: tuple(group) for name, group in grouped.items()}


def expand_parameter_keys_to_symbols(
    keys: ParameterKeyOrKeys,
    candidates: Iterable[Symbol],
    *,
    role: str = "parameters",
) -> tuple[Symbol, ...]:
    """Resolve parameter keys against candidate symbols using canonical names.

    Each requested key expands to every candidate symbol that shares the same
    canonical name. This keeps expression/numeric backends fully bound even when
    distinct SymPy symbols with different assumptions share one authoritative
    parameter name.

    If a key has no match among ``candidates``, a representative symbol is
    created from the key itself so explicit-but-unused parameters still round
    trip in the same way as the legacy symbol-only API.
    """
    candidate_groups = group_symbols_by_name(candidates)
    requested, _single = normalize_parameter_sequence(keys, role=role)

    ordered: list[Symbol] = []
    seen: set[Symbol] = set()
    for name, original_symbol in requested:
        matched = candidate_groups.get(name)
        if matched:
            for symbol in matched:
                if symbol not in seen:
                    ordered.append(symbol)
                    seen.add(symbol)
            continue
        if original_symbol not in seen:
            ordered.append(original_symbol)
            seen.add(original_symbol)

    return tuple(ordered)
