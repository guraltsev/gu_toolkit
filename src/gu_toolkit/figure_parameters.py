"""Parameter manager for Figure.

Parameter identity is name-authoritative: the canonical key for a parameter is
its string name (``symbol.name``). SymPy symbols remain accepted throughout the
API, but are normalized to their name before lookup, storage, or snapshotting.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Hashable, Iterator, Mapping
from typing import Any

from ._widget_stubs import widgets
import sympy as sp
from sympy.core.symbol import Symbol

from .ParameterSnapshot import ParameterSnapshot, ParameterValueSnapshot
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .Slider import FloatSlider
from .parameter_keys import (
    ParameterKey,
    ParameterKeyOrKeys,
    normalize_parameter_sequence,
    parameter_name,
    parameter_symbol,
)


class _ParameterContextView(Mapping[str, Any]):
    """Live name-keyed view over parameter values.

    Symbol keys remain accepted as aliases. Iteration exposes canonical string
    names because parameter names are the authoritative identifiers.
    """

    def __init__(self, refs: Mapping[str, ParamRef]) -> None:
        self._refs = refs

    def __getitem__(self, key: ParameterKey) -> Any:
        return self._refs[parameter_name(key, role="parameter")].value

    def __iter__(self) -> Iterator[str]:
        return iter(self._refs)

    def __len__(self) -> int:
        return len(self._refs)

    def __contains__(self, key: object) -> bool:  # pragma: no cover - simple
        try:
            name = parameter_name(key, role="parameter")  # type: ignore[arg-type]
        except TypeError:
            return False
        return name in self._refs


class _RenderParameterContext(Mapping[str, Any]):
    """Stable snapshot-backed parameter provider reused across render passes."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def replace(self, values: Mapping[ParameterKey, Any]) -> None:
        """Replace the stored snapshot with a detached copy of ``values``."""
        self._values.clear()
        for raw_key, value in values.items():
            self._values[parameter_name(raw_key, role="parameter")] = value

    def __getitem__(self, key: ParameterKey) -> Any:
        return self._values[parameter_name(key, role="parameter")]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __contains__(self, key: object) -> bool:  # pragma: no cover - simple
        try:
            name = parameter_name(key, role="parameter")  # type: ignore[arg-type]
        except TypeError:
            return False
        return name in self._values

    def __repr__(self) -> str:
        return f"_RenderParameterContext({self._values!r})"


# SECTION: ParameterManager (The Model for Parameters) [id: ParameterManager]
# =============================================================================


class ParameterManager(Mapping[str, ParamRef]):
    """Manage parameter controls, refs, snapshots, and hooks.

    Public lookup is name-authoritative: ``fig.parameters["a"]`` and
    ``fig.parameters[sp.Symbol("a")]`` address the same logical entry.
    """

    def __init__(
        self,
        render_callback: Callable[[str, ParamEvent], None],
        layout_box: widgets.Box,
        modal_host: widgets.Box | None = None,
    ) -> None:
        self._refs: dict[str, ParamRef] = {}
        self._symbols: dict[str, Symbol] = {}
        self._parameter_context_view = _ParameterContextView(self._refs)
        self._render_parameter_context = _RenderParameterContext()
        self._controls: list[Any] = []
        self._hooks: dict[Hashable, Callable[[ParamEvent], Any]] = {}
        self._hook_counter: int = 0
        self._render_callback = render_callback
        self._layout_box = layout_box
        self._modal_host = modal_host

    def _resolve_name(self, key: ParameterKey) -> str:
        name = parameter_name(key, role="parameter")
        if name not in self._refs:
            raise KeyError(name)
        return name

    @staticmethod
    def _lookup_control_ref(
        refs: Mapping[object, ParamRef],
        *,
        name: str,
        symbol: Symbol,
    ) -> ParamRef:
        """Extract the control ref for ``name`` from a custom control mapping."""
        if name in refs:
            ref = refs[name]
        elif symbol in refs:
            ref = refs[symbol]
        else:
            matches: list[ParamRef] = []
            for raw_key, ref_candidate in refs.items():
                try:
                    raw_name = parameter_name(raw_key, role="parameter")  # type: ignore[arg-type]
                except TypeError:
                    continue
                if raw_name == name:
                    matches.append(ref_candidate)
            if not matches:
                raise KeyError(
                    f"Control did not provide a ref for parameter {name!r}."
                )
            if len(matches) > 1 and len({id(ref) for ref in matches}) > 1:
                raise KeyError(
                    f"Control provided multiple refs for parameter name {name!r}."
                )
            ref = matches[0]

        ref_symbol = getattr(ref, "parameter", symbol)
        if isinstance(ref_symbol, Symbol) and ref_symbol.name != name:
            raise ValueError(
                f"Control ref parameter {ref_symbol!r} does not match requested name {name!r}."
            )
        return ref

    def parameter(
        self,
        symbols: ParameterKeyOrKeys,
        *,
        control: Any | None = None,
        **control_kwargs: Any,
    ) -> ParamRef | dict[str, ParamRef]:
        """Create or reuse parameter references for the given keys.

        Parameters may be supplied as strings or SymPy symbols. The canonical
        storage key is always the string name.
        """
        requested, single = normalize_parameter_sequence(symbols, role="parameter")

        existing = [(name, symbol) for name, symbol in requested if name in self._refs]
        missing = [(name, symbol) for name, symbol in requested if name not in self._refs]

        if control is not None and existing:
            for name, _symbol in existing:
                if self._refs[name].widget is not control:
                    raise ValueError(
                        f"Parameter {name!r} is already bound to a different control."
                    )

        defaults = {"value": 0.0, "min": -1.0, "max": 1.0, "step": 0.01}

        if control is None:
            for name, symbol in missing:
                config = {**defaults, **control_kwargs}
                new_control = FloatSlider(
                    description=f"${sp.latex(symbol)}$",
                    value=float(config["value"]),
                    min=float(config["min"]),
                    max=float(config["max"]),
                    step=float(config["step"]),
                )
                self._attach_modal_host(new_control)
                refs = new_control.make_refs([symbol])
                ref = self._lookup_control_ref(refs, name=name, symbol=symbol)
                ref.observe(self._on_param_change)
                self._refs[name] = ref
                self._symbols.setdefault(name, symbol)
                if new_control not in self._controls:
                    self._controls.append(new_control)
                    self._layout_box.children += (new_control,)
        elif missing:
            self._attach_modal_host(control)
            refs = control.make_refs([symbol for _, symbol in missing])
            for name, symbol in missing:
                ref = self._lookup_control_ref(refs, name=name, symbol=symbol)
                ref.observe(self._on_param_change)
                self._refs[name] = ref
                self._symbols.setdefault(name, symbol)
            if control not in self._controls:
                self._controls.append(control)
                self._layout_box.children += (control,)

        for name, symbol in requested:
            ref = self._refs[name]
            self._symbols.setdefault(name, symbol)
            for attr_name, value in control_kwargs.items():
                setattr(ref, attr_name, value)

        if single:
            return self._refs[requested[0][0]]
        return {name: self._refs[name] for name, _ in requested}

    def _attach_modal_host(self, control: Any) -> None:
        """Attach modal host to controls that support it."""
        if self._modal_host is None:
            return
        attach_fn = getattr(control, "set_modal_host", None)
        if callable(attach_fn):
            attach_fn(self._modal_host)

    def snapshot(
        self, *, full: bool = False
    ) -> ParameterValueSnapshot | ParameterSnapshot:
        """Return parameter values or a full immutable metadata snapshot."""
        entries: dict[str, dict[str, Any]] = {}
        for name, ref in self._refs.items():
            entry: dict[str, Any] = {"value": ref.value}
            caps = list(ref.capabilities)
            entry["capabilities"] = caps
            for cap_name in caps:
                entry[cap_name] = getattr(ref, cap_name)
            entries[name] = entry

        snapshot = ParameterSnapshot(entries, symbols=self._symbols)
        if full:
            return snapshot
        return snapshot.value_map()

    @property
    def parameter_context(self) -> Mapping[str, Any]:
        """Live name-keyed view for numeric evaluation contexts."""
        return self._parameter_context_view

    @property
    def render_parameter_context(self) -> Mapping[str, Any]:
        """Stable snapshot-backed mapping used during actual renders."""
        return self._render_parameter_context

    def refresh_render_parameter_context(self) -> Mapping[str, Any]:
        """Capture current live values into the reusable render provider."""
        self._render_parameter_context.replace(
            {name: ref.value for name, ref in self._refs.items()}
        )
        return self._render_parameter_context

    @property
    def has_params(self) -> bool:
        """Whether any parameters have been created."""
        return len(self._refs) > 0

    def add_hook(
        self,
        callback: Callable[[ParamEvent | None], Any],
        hook_id: Hashable | None = None,
    ) -> Hashable:
        """Register a parameter change hook."""
        if hook_id is None:
            self._hook_counter += 1
            hook_id = f"hook:{self._hook_counter}"
        elif isinstance(hook_id, str):
            match = re.fullmatch(r"hook:(\d+)", hook_id)
            if match is not None:
                self._hook_counter = max(self._hook_counter, int(match.group(1)))
        self._hooks[hook_id] = callback
        return hook_id

    def fire_hook(self, hook_id: Hashable, event: ParamEvent | None) -> None:
        """Fire a specific hook with a ParamEvent."""
        callback = self._hooks.get(hook_id)
        if callback is None:
            return
        callback(event)

    def _on_param_change(self, event: ParamEvent) -> None:
        """Handle parameter changes by triggering the render callback."""
        self._render_callback("param_change", event)

    def get_hooks(self) -> dict[Hashable, Callable]:
        """Return a shallow copy of the registered hook dictionary."""
        return self._hooks.copy()

    def __getitem__(self, key: ParameterKey) -> ParamRef:
        """Return the param ref for ``key`` (string-authoritative)."""
        return self._refs[self._resolve_name(key)]

    def __contains__(self, key: object) -> bool:  # pragma: no cover - simple
        try:
            name = parameter_name(key, role="parameter")  # type: ignore[arg-type]
        except TypeError:
            return False
        return name in self._refs

    def items(self) -> Iterator[tuple[str, ParamRef]]:
        """Iterate over ``(name, ParamRef)`` pairs."""
        return iter(self._refs.items())

    def keys(self) -> Iterator[str]:
        """Iterate over canonical parameter names."""
        return iter(self._refs.keys())

    def symbols(self) -> tuple[Symbol, ...]:
        """Return canonical symbols in insertion order."""
        return tuple(self._symbols[name] for name in self._refs)

    def symbol_for_name(self, key: ParameterKey) -> Symbol:
        """Return the representative symbol registered for ``key``."""
        name = self._resolve_name(key)
        return self._symbols[name]

    def values(self) -> Iterator[ParamRef]:
        """Iterate over parameter refs."""
        return iter(self._refs.values())

    def get(self, key: ParameterKey, default: Any = None) -> Any:
        """Return a param ref if present; otherwise return ``default``."""
        try:
            name = parameter_name(key, role="parameter")
        except TypeError:
            return default
        return self._refs.get(name, default)

    def __iter__(self) -> Iterator[str]:
        """Iterate over canonical parameter names."""
        return iter(self._refs)

    def __len__(self) -> int:
        """Return the number of stored parameter refs."""
        return len(self._refs)

    def widget(self, symbol: ParameterKey) -> Any:
        """Return the widget/control for ``symbol`` or parameter name."""
        return self[self._resolve_name(symbol)].widget

    def widgets(self) -> list[Any]:
        """Return unique widgets/controls suitable for display."""
        return list(self._controls)


# =============================================================================
