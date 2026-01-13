"""Module: SmartParameters.py

DESIGN OVERVIEW:
===============
This module provides a small **reactive parameter** core for Jupyter/JupyterLab.

The core abstraction is :class:`SmartParameter`, which stores:
- an immutable `id`,
- a numeric `value` with optional bounds (`min_val`, `max_val`),
- a weakref-backed callback list.

Key Simplifications:
--------------------
1. **Strict Signatures**: Callbacks MUST accept `**kwargs` to handle forward
   compatibility (e.g., `def cb(param, **kwargs): ...`).
2. **Idempotency**: Registering the same callback (function or bound method)
   multiple times is safe; it returns the existing token.
3. **Registry**: A dictionary subclass that auto-creates parameters on access.

API REFERENCE:
==============
SmartParameter
    Reactive scalar-like value with coercion/clamping and callback dispatch.

SmartParameterRegistry
    Dictionary subclass that auto-vivifies SmartParameters.

CallbackToken
    Opaque handle for registered callbacks.
"""

from __future__ import annotations

__all__ = [
    "CallbackToken",
    "CallbackError",
    "SmartParameter",
    "SmartParameterRegistry",
]

# Notebook-toolkit metadata
__gu_exports__ = __all__
__gu_priority__ = 200
__gu_enabled = True

import uuid
import warnings
import weakref
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, Optional, Tuple, TypeVar, cast, Union

_UNSET: object = object()


@dataclass(frozen=True)
class CallbackToken:
    """Opaque, hashable handle identifying a registered callback."""
    token: str


@dataclass(frozen=True)
class CallbackError:
    """Record of an exception raised by a callback during notification."""
    token: CallbackToken
    label: str
    exception: BaseException
    traceback: str


def _new_token() -> CallbackToken:
    return CallbackToken(uuid.uuid4().hex)


def _coerce_optional_float(name: str, val: Any) -> Optional[float]:
    """Coerce a bound value to Optional[float] with a helpful error."""
    if val is None:
        return None
    try:
        return float(val)
    except Exception as e:
        raise TypeError(f"{name} must be a float or None, got {val!r}") from e


def _callable_label(cb: Callable[..., Any]) -> str:
    """Create a human-readable label for a callable (used for error reporting)."""
    # 1. Bound Method
    if hasattr(cb, "__self__") and getattr(cb, "__self__", None) is not None:
        self_obj = getattr(cb, "__self__")
        func = getattr(cb, "__func__", cb)
        cls_name = getattr(type(self_obj), "__qualname__", type(self_obj).__name__)
        fn_name = getattr(func, "__name__", "<method>")
        return f"{cls_name}.{fn_name}"

    # 2. Function or Class
    mod = getattr(cb, "__module__", "")
    qn = getattr(cb, "__qualname__", None) or getattr(cb, "__name__", str(cb))
    return f"{mod}.{qn}" if mod else qn


class _CallbackEntry:
    """Internal weakref-backed callback entry.

    Handles the complexity of weakly referencing bound methods vs plain functions
    to support idempotent registration.
    """

    __slots__ = ("_kind", "_weak_method", "_self_ref", "_func", "_ref")

    def __init__(self, callback: Callable[..., Any]) -> None:
        if hasattr(callback, "__self__") and getattr(callback, "__self__", None) is not None:
            # Bound method
            self._kind = "weakmethod"
            self._weak_method: weakref.WeakMethod[Any] = weakref.WeakMethod(cast(Any, callback))
            self._self_ref = weakref.ref(getattr(callback, "__self__"))
            self._func = getattr(callback, "__func__")
        else:
            # Plain function/callable
            self._kind = "ref"
            try:
                self._ref: weakref.ref[Callable[..., Any]] = weakref.ref(callback)
            except TypeError as e:
                raise TypeError("Callback must be weak-referenceable (e.g., function or method).") from e

    def get_callable(self) -> Optional[Callable[..., Any]]:
        """Return the live callable or None if collected."""
        if self._kind == "weakmethod":
            return self._weak_method()
        return self._ref()

    def matches(self, callback: Callable[..., Any]) -> bool:
        """Return True if `callback` is identical to the stored one."""
        if self._kind == "weakmethod":
            if not (hasattr(callback, "__self__") and getattr(callback, "__self__", None) is not None):
                return False
            # Check instance identity and function identity
            obj = self._self_ref()
            if obj is None:
                return False  # Dead reference cannot match live callback
            return (getattr(callback, "__self__") is obj) and (getattr(callback, "__func__") is self._func)
        
        # Plain ref match
        return self._ref() is callback


class SmartParameter:
    """Reactive parameter with coercion, clamping, and weakref callbacks.

    Contract:
        - Callbacks MUST accept `**kwargs` (specifically `what_changed`).
        - `what_changed` is a tuple of strings: e.g., `("value",)` or `("min", "max")`.
    """

    def __init__(
        self,
        id: Hashable,
        *,
        type: Callable[[Any], float] = float,
        value: Optional[Any] = None,
        min_val: Optional[Any] = -1.0,
        max_val: Optional[Any] = 1.0,
        default_val: float = 0.0,
        step: Optional[Any] = None,
    ) -> None:
        self.id: Hashable = id
        self.type: Callable[[Any], float] = type
        self.default_val: float = float(default_val)

        # Bounds
        self._min_val: Optional[float] = _coerce_optional_float("min_val", min_val)
        self._max_val: Optional[float] = _coerce_optional_float("max_val", max_val)
        self._validate_bounds(self._min_val, self._max_val)

        # UI Step hint
        if step is None:
            self.step = self._calculate_default_step()
        else:
            self.step = float(step)
            if self.step <= 0:
                raise ValueError(f"step must be > 0, got {step!r}")

        # Callback storage
        self._callbacks_by_token: Dict[CallbackToken, _CallbackEntry] = {}
        self.last_callback_errors: list[CallbackError] = []

        # Value initialization
        initial = self.default_val if value is None else value
        self._value: float = self._coerce_and_clamp(initial)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, new_val: Any) -> None:
        self._set_value_internal(new_val, exclude_token=None, owner_token=None, what_changed=("value",))

    @property
    def min_val(self) -> Optional[float]:
        return self._min_val

    @min_val.setter
    def min_val(self, val: Any) -> None:
        self.set_bounds(min_val=val)

    @property
    def max_val(self) -> Optional[float]:
        return self._max_val

    @max_val.setter
    def max_val(self, val: Any) -> None:
        self.set_bounds(max_val=val)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set(self, new_val: Any, **kwargs: Any) -> None:
        """Set value and forward arbitrary kwargs to callbacks."""
        if "what_changed" in kwargs:
            raise TypeError("`what_changed` is reserved.")
        self._set_value_internal(
            new_val, 
            exclude_token=None, 
            owner_token=None, 
            what_changed=("value",), 
            **kwargs
        )

    def register_callback(self, callback: Callable[..., Any]) -> CallbackToken:
        """Register a callback. Idempotent (returns existing token if present).
        
        Note:
            Callback MUST accept `**kwargs` or signature `(param, **kwargs)`.
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)!r}")

        # Idempotency scan & cleanup
        dead = []
        existing_token: Optional[CallbackToken] = None
        
        for t, entry in self._callbacks_by_token.items():
            if entry.get_callable() is None:
                dead.append(t)
                continue
            if existing_token is None and entry.matches(callback):
                existing_token = t
        
        for t in dead:
            del self._callbacks_by_token[t]

        if existing_token:
            return existing_token

        # Register new
        token = _new_token()
        self._callbacks_by_token[token] = _CallbackEntry(callback)
        return token

    def remove_callback(self, token: CallbackToken) -> None:
        """Remove a callback by token."""
        self._callbacks_by_token.pop(token, None)

    def set_protected(self, new_val: Any, owner_token: CallbackToken, **kwargs: Any) -> None:
        """Set value, excluding the owner from notification."""
        if "what_changed" in kwargs:
            raise TypeError("`what_changed` is reserved.")
        self._set_value_internal(
            new_val,
            exclude_token=owner_token,
            owner_token=owner_token,
            what_changed=("value",),
            **kwargs
        )

    def set_bounds(
        self,
        *,
        min_val: Any = _UNSET,
        max_val: Any = _UNSET,
        owner_token: Optional[CallbackToken] = None,
        **kwargs: Any,
    ) -> None:
        """Atomically update bounds and notify once."""
        if "what_changed" in kwargs:
            raise TypeError("`what_changed` is reserved.")

        new_min = self._min_val if min_val is _UNSET else _coerce_optional_float("min_val", min_val)
        new_max = self._max_val if max_val is _UNSET else _coerce_optional_float("max_val", max_val)

        changed = []
        if new_min != self._min_val:
            changed.append("min")
        if new_max != self._max_val:
            changed.append("max")

        if not changed:
            return

        self._validate_bounds(new_min, new_max)
        self._min_val = new_min
        self._max_val = new_max

        # Clamp value if bounds constricted
        clamped = self._clamp_value(self._value, min_val=self._min_val, max_val=self._max_val)
        if clamped != self._value:
            self._value = clamped
            changed.append("value")

        self._notify(
            exclude_token=owner_token,
            owner_token=owner_token,
            what_changed=tuple(changed),
            **kwargs
        )

    # -------------------------------------------------------------------------
    # Internal Logic
    # -------------------------------------------------------------------------

    def _calculate_default_step(self) -> float:
        if self._min_val is None or self._max_val is None:
            return 0.01
        span = self._max_val - self._min_val
        return span / 200.0 if span > 0 else 0.01

    def _validate_bounds(self, min_val: Optional[float], max_val: Optional[float]) -> None:
        if min_val is not None and max_val is not None and min_val > max_val:
            raise ValueError(f"Invalid bounds: min={min_val} > max={max_val}")

    @staticmethod
    def _clamp_value(value: float, *, min_val: Optional[float], max_val: Optional[float]) -> float:
        v = value
        if min_val is not None:
            v = max(v, min_val)
        if max_val is not None:
            v = min(v, max_val)
        return v

    def _coerce_and_clamp(self, val: Any) -> float:
        try:
            v = float(self.type(val))
        except Exception as e:
            raise TypeError(f"Value {val!r} not coercible to float via {self.type}") from e
        return self._clamp_value(v, min_val=self._min_val, max_val=self._max_val)

    def _set_value_internal(
        self, 
        new_val: Any, 
        exclude_token: Optional[CallbackToken],
        owner_token: Optional[CallbackToken],
        what_changed: Tuple[str, ...],
        **kwargs: Any
    ) -> None:
        self._value = self._coerce_and_clamp(new_val)
        self._notify(
            exclude_token=exclude_token,
            owner_token=owner_token,
            what_changed=what_changed,
            **kwargs
        )

    def _notify(
        self,
        exclude_token: Optional[CallbackToken],
        owner_token: Optional[CallbackToken],
        what_changed: Tuple[str, ...],
        **kwargs: Any
    ) -> None:
        self.last_callback_errors.clear()
        
        # Snapshot for safe iteration
        entries = list(self._callbacks_by_token.items())
        
        for token, entry in entries:
            if exclude_token and token == exclude_token:
                continue

            cb = entry.get_callable()
            if cb is None:
                # Cleanup happens lazily on next register, or we could do it here.
                # For simplicity, we skip. `register_callback` handles cleanup.
                continue

            try:
                cb(self, owner_token=owner_token, what_changed=what_changed, **kwargs)
            except Exception as e:
                self.last_callback_errors.append(CallbackError(
                    token=token,
                    label=_callable_label(cb),
                    exception=e,
                    traceback=traceback.format_exc()
                ))

        if self.last_callback_errors:
            warnings.warn(
                f"{len(self.last_callback_errors)} callback(s) failed for {self.id!r}. "
                "See `last_callback_errors`.",
                RuntimeWarning,
                stacklevel=2
            )

    def __repr__(self) -> str:
        return (f"SmartParameter(id={self.id!r}, value={self.value:.3g}, "
                f"bounds=[{self.min_val}, {self.max_val}])")


class SmartParameterRegistry(Dict[Hashable, SmartParameter]):
    """Auto-vivifying registry for SmartParameters.
    
    Behaves like a dictionary but creates a new SmartParameter whenever a
    missing key is accessed.
    """

    def __missing__(self, key: Hashable) -> SmartParameter:
        param = SmartParameter(id=key)
        self[key] = param
        return param

    def __setitem__(self, key: Hashable, value: SmartParameter) -> None:
        if not isinstance(value, SmartParameter):
            raise TypeError(f"Registry values must be SmartParameter, got {type(value)}")
        if value.id != key:
            raise ValueError(f"Key {key!r} does not match param.id {value.id!r}")
        super().__setitem__(key, value)
    
    def set_value(self, id: Hashable, new_val: Any, **kwargs: Any) -> None:
        """Helper to set value on a parameter by ID."""
        self[id].set(new_val, **kwargs)