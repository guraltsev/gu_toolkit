"""Module: SmartParameters.py

DESIGN OVERVIEW:
===============
This module provides a small **reactive parameter** core intended for
Jupyter/JupyterLab usage.

The core abstraction is :class:`SmartParameter`, which stores:

- an immutable `id` (often a SymPy Symbol),
- a numeric `value`,
- optional numeric bounds `min_val` / `max_val`,
- a `step` hint (useful for UI widgets),
- a weakref-backed callback list.

The callback system is designed for notebook/widget scenarios:

- Registration is **idempotent**: re-registering the same callable returns the
  original :class:`CallbackToken`.
- Callbacks are stored using **weak references**, including bound methods via
  :class:`weakref.WeakMethod`.
- Notifications continue even if some callbacks raise; exceptions are aggregated
  into :attr:`SmartParameter.last_callback_errors`.

Stage alignment
---------------
This file intentionally supports later stages of the project blueprint as well,
but **Stage 1** requirements are the key contract:

Stage 1 contract:
  - `value`, `min_val`, and `max_val` are dynamic; changing any notifies
    callbacks.
  - Every notification includes `what_changed` as a **tuple** containing all
    fields that changed in that operation, e.g. `("value",)`,
    `("max","value")`, `("min","max")`, `("min","max","value")`.
  - Bounds updates clamp `value` if needed; clamping includes `"value"` in
    `what_changed`.
  - `step` is stored on the parameter and **does not auto-update** when bounds
    change (it is a UI hint, not a derived property).

GOTCHAS (WEAKREFS):
==================
Because callbacks are weakly referenced, an unnamed callback (e.g. a lambda)
with no other references may be garbage-collected and stop firing. In notebooks,
store callback owners (widgets/controllers) in variables so they stay alive.

API REFERENCE:
==============
CallbackToken
    Opaque, hashable handle returned from `SmartParameter.register_callback`.

CallbackError
    Record of a callback exception captured during notification.

SmartParameter
    Reactive scalar-like value with coercion/clamping and callback dispatch.

SmartParameterRegistry
    Auto-vivifying mapping from parameter IDs to `SmartParameter`.

MAINTENANCE GUIDE:
=================
Key invariants:
  - Assigning to `value` always notifies (no equality short-circuit).
  - Bounds validation: if both bounds are not None, require min_val <= max_val.
  - `what_changed` contains **only** fields that actually changed in that
    operation (bounds setters do not notify if setting to the same value and no
    clamping occurs).
  - `step` is validated as float > 0 and does not auto-change.

Performance notes:
  - `register_callback` is O(n) due to the idempotency scan (by design).
  - Notification is O(n) in the number of live callbacks.

Testing strategy:
  - Use doctests in docstrings for basic coverage.
  - For weakref behavior, include tests that delete callback owners and run
    `gc.collect()`.

"""

from __future__ import annotations

__all__ = [
    "CallbackToken",
    "CallbackError",
    "SmartParameter",
    "SmartParameterRegistry",
]

# Notebook-toolkit metadata (used by the user's autoload system).
__gu_exports__ = __all__
__gu_priority__ = 200
__gu_enabled = True

import traceback as _traceback
import uuid
import warnings
import weakref
from collections.abc import Iterable, Iterator, MutableMapping
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, Optional, TypeVar, cast

T = TypeVar("T")

_UNSET: object = object()


@dataclass(frozen=True)
class CallbackToken:
    """Opaque handle identifying a registered callback.

    Notes:
        - The token is intentionally opaque; callers should not depend on its
          internal structure.
        - The token is hashable and can be used as a dict key.
    """

    token: str


def _new_token() -> CallbackToken:
    """Create a fresh callback token."""
    return CallbackToken(uuid.uuid4().hex)


@dataclass(frozen=True)
class CallbackError:
    """Record of an exception raised by a callback during notification."""

    token: CallbackToken
    label: str
    exception: BaseException
    traceback: str


def _is_bound_method(cb: Callable[..., Any]) -> bool:
    """Return True if `cb` looks like a bound method (obj.method)."""
    return hasattr(cb, "__self__") and getattr(cb, "__self__", None) is not None and hasattr(cb, "__func__")


def _callable_label(cb: Callable[..., Any]) -> str:
    """Create a stable, human-readable label for debug/error messages."""
    if _is_bound_method(cb):
        self_obj = getattr(cb, "__self__")
        func_obj = getattr(cb, "__func__")
        cls_name = getattr(self_obj.__class__, "__qualname__", self_obj.__class__.__name__)
        fn_name = getattr(func_obj, "__name__", "<method>")
        return f"{cls_name}.{fn_name}"

    mod = getattr(cb, "__module__", "")
    qn = getattr(cb, "__qualname__", None) or getattr(cb, "__name__", None)
    if qn:
        return f"{mod}.{qn}" if mod else str(qn)

    # Callable object instance.
    cls = cb.__class__
    cls_name = getattr(cls, "__qualname__", cls.__name__)
    return f"{cls_name}.__call__"


def _coerce_optional_float(name: str, val: Any) -> Optional[float]:
    """Coerce a bound value to Optional[float] with a helpful error."""
    if val is None:
        return None
    try:
        return float(val)
    except Exception as e:
        raise TypeError(f"{name} must be a float or None, got {val!r}") from e


def _default_step_for_bounds(min_val: Optional[float], max_val: Optional[float]) -> float:
    """Compute a conservative default `step` from bounds.

    The project blueprint uses `(max-min)/200` when both bounds are finite.
    For unbounded or degenerate ranges, we fall back to `0.01`.
    """
    if min_val is None or max_val is None:
        return 0.01
    span = float(max_val) - float(min_val)
    if span <= 0:
        return 0.01
    return span / 200.0


class _CallbackEntry:
    """Internal weakref-backed callback entry.

    An entry can represent:
      - a bound method (stored via WeakMethod + separate weak self reference),
      - a plain function/callable object (stored via weakref.ref).

    The entry supports:
      - `get_callable()` -> live callable or None
      - `matches(callback)` -> True if this entry represents the same callback
        (normalized identity) for idempotent registration.
    """

    def __init__(self, callback: Callable[..., Any]) -> None:
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)!r}")

        self.label: str = _callable_label(callback)

        if _is_bound_method(callback):
            # Bound method: weakly reference the instance and the underlying function.
            bound = cast(Any, callback)
            self._kind: str = "weakmethod"
            self._weak_method: weakref.WeakMethod[Any] = weakref.WeakMethod(bound)
            self._self_ref: weakref.ref[Any] = weakref.ref(bound.__self__)
            self._func: Any = bound.__func__
        else:
            # Plain function or weakref-able callable object.
            self._kind = "ref"
            try:
                self._ref: weakref.ref[Callable[..., Any]] = weakref.ref(callback)
            except TypeError as e:
                raise TypeError(
                    "callback must support weak references. "
                    "Store callbacks as module-level functions, or ensure "
                    "callable objects define __weakref__."
                ) from e

    def get_callable(self) -> Optional[Callable[..., Any]]:
        """Return a live callable or None if it has been garbage collected."""
        if self._kind == "weakmethod":
            m = self._weak_method()
            return cast(Optional[Callable[..., Any]], m)
        return self._ref()

    def matches(self, callback: Callable[..., Any]) -> bool:
        """Return True if `callback` is the same logical callback as this entry."""
        if self._kind == "weakmethod":
            if not _is_bound_method(callback):
                return False
            obj = self._self_ref()
            if obj is None:
                return False
            bound = cast(Any, callback)
            return bound.__self__ is obj and bound.__func__ is self._func

        # Plain ref entry: identity match on the live object.
        live = self._ref()
        return live is callback


class SmartParameter:
    """A reactive parameter with coercion, clamping, and weakref callbacks.

    The parameter holds a `value`. Setting `value`:

      1) coerces via `type` (default: `float`),
      2) clamps to [min_val, max_val] where bounds are not None,
      3) stores the result,
      4) notifies callbacks with `what_changed=("value",)`.

    Bounds `min_val` and `max_val` are also reactive. Changing either:

      - validates bounds (`min_val <= max_val` if both not None),
      - clamps `value` if needed,
      - notifies with `what_changed` containing the bound that changed and
        `"value"` if clamping occurred.

    `set_bounds(min_val=..., max_val=...)` updates both bounds atomically and
    sends **exactly one** notification.

    Callback behavior:
      - Callbacks are weakly referenced (including bound methods).
      - Registering the same callback is idempotent: it returns the same token.
      - `set_protected` and `set_bounds(..., owner_token=...)` can exclude the
        owner callback identified by the token.
      - Callback errors are aggregated into `last_callback_errors`, and remaining
        callbacks are still invoked.

    Examples
    --------
    Basic `what_changed` semantics:

    >>> p = SmartParameter(id="a", min_val=0, max_val=1, value=0.5)
    >>> events: list[tuple[str, ...]] = []
    >>> def cb(param: SmartParameter, **kw: Any) -> None:
    ...     events.append(kw["what_changed"])
    >>> _ = p.register_callback(cb)
    >>> p.value = 2
    >>> p.value
    1.0
    >>> events[-1]
    ('value',)

    Changing bounds that clamps the current value includes `"value"`:

    >>> events.clear()
    >>> p.max_val = 0.2
    >>> p.value
    0.2
    >>> events[-1]
    ('max', 'value')

    Atomic bounds update reports both bounds (and value if clamped):

    >>> old_step = p.step
    >>> events.clear()
    >>> p.set_bounds(min_val=-1, max_val=0.1)
    >>> p.value
    0.1
    >>> events[-1]
    ('min', 'max', 'value')
    >>> p.step == old_step
    True
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
        """
        Create a parameter.

        Args:
            id:
                Immutable identifier for the parameter (e.g. a SymPy Symbol).
            type:
                Coercion function applied to values before conversion to float.
            value:
                Initial value. If None, uses `default_val`.
            min_val, max_val:
                Optional bounds. If both are not None, must satisfy `min_val <= max_val`.
            default_val:
                Default numeric value used when `value` is None.
            step:
                UI hint for "increment size". If None, defaults to `(max-min)/200` when
                both bounds are finite, else `0.01`.

        Raises:
            ValueError:
                If the provided bounds are inconsistent.
            TypeError:
                If coercion to floats fails for bounds/value/step.
        """
        self.id: Hashable = id
        self.type: Callable[[Any], float] = type

        self._min_val: Optional[float] = _coerce_optional_float("min_val", min_val)
        self._max_val: Optional[float] = _coerce_optional_float("max_val", max_val)
        self._validate_bounds(self._min_val, self._max_val)

        if step is None:
            self.step = _default_step_for_bounds(self._min_val, self._max_val)
        else:
            self.step = float(step)
            if not (self.step > 0):
                raise ValueError(f"step must be > 0, got {step!r}")

        self.default_val: float = float(default_val)

        # Weakref-backed storage, idempotency implemented via scans (O(n)).
        self._callbacks_by_token: Dict[CallbackToken, _CallbackEntry] = {}

        # Error aggregation (most recent notify batch).
        self.last_callback_errors: list[CallbackError] = []

        initial = self.default_val if value is None else value
        # Do not notify during initialization.
        self._value: float = self._coerce_and_clamp(initial)

    # -------------------------------------------------------------------------
    # Reactive properties (Stage 1 contract)
    # -------------------------------------------------------------------------

    @property
    def min_val(self) -> Optional[float]:
        """Lower bound for `value`, or None for unbounded."""
        return self._min_val

    @min_val.setter
    def min_val(self, new_min: Optional[Any]) -> None:
        self.set_bounds(min_val=new_min)

    @property
    def max_val(self) -> Optional[float]:
        """Upper bound for `value`, or None for unbounded."""
        return self._max_val

    @max_val.setter
    def max_val(self, new_max: Optional[Any]) -> None:
        self.set_bounds(max_val=new_max)

    @property
    def value(self) -> float:
        """The current value."""
        return self._value

    @value.setter
    def value(self, new_val: Any) -> None:
        """Set the value (coerce+clamp) and notify all callbacks."""
        self._set_value_internal(new_val, exclude_token=None, owner_token=None, what_changed=("value",))

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set(self, new_val: Any, **kwargs: Any) -> None:
        """Set the value and forward keyword arguments to callbacks.

        Notes:
            The `value` property setter cannot accept keyword arguments, so this
            method exists for cases where callbacks need extra metadata such as
            `source="slider"`.

        Args:
            new_val: New value.
            **kwargs: Arbitrary metadata forwarded to callbacks.

        Raises:
            TypeError: If the caller provides `what_changed` (reserved).
        """
        if "what_changed" in kwargs:
            raise TypeError("`what_changed` is managed by SmartParameter; do not pass it to set().")
        self._set_value_internal(new_val, exclude_token=None, owner_token=None, what_changed=("value",), **kwargs)

    def register_callback(self, callback: Callable[..., Any]) -> CallbackToken:
        """Register a callback (weakly referenced), idempotent by scan."""
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)!r}")

        dead: list[CallbackToken] = []

        # Idempotency scan (O(n) by design), piggybacking cleanup of dead entries.
        for token, entry in self._callbacks_by_token.items():
            if entry.get_callable() is None:
                dead.append(token)
                continue
            if entry.matches(callback):
                for t in dead:
                    self._callbacks_by_token.pop(t, None)
                return token

        for t in dead:
            self._callbacks_by_token.pop(t, None)

        token = _new_token()
        self._callbacks_by_token[token] = _CallbackEntry(callback)
        return token

    def remove_callback(self, token: CallbackToken) -> None:
        """Remove a callback by token. Missing tokens are ignored."""
        self._callbacks_by_token.pop(token, None)

    def set_protected(self, new_val: Any, owner_token: CallbackToken, **kwargs: Any) -> None:
        """Set the value, notifying all callbacks except the owner.

        Raises:
            TypeError: If the caller provides `what_changed` (reserved).
        """
        if "what_changed" in kwargs:
            raise TypeError("`what_changed` is managed by SmartParameter; do not pass it to set_protected().")
        self._set_value_internal(
            new_val,
            exclude_token=owner_token,
            owner_token=owner_token,
            what_changed=("value",),
            **kwargs,
        )

    def set_bounds(
        self,
        *,
        min_val: Any = _UNSET,
        max_val: Any = _UNSET,
        owner_token: Optional[CallbackToken] = None,
        **kwargs: Any,
    ) -> None:
        """Update bounds (atomically) and notify once.

        This is the recommended way to update both bounds together (e.g. from a
        widget settings panel).

        Args:
            min_val:
                New minimum bound, or None for unbounded. If omitted, the minimum
                is unchanged.
            max_val:
                New maximum bound, or None for unbounded. If omitted, the maximum
                is unchanged.
            owner_token:
                If provided, the callback registered with this token is excluded
                from notification (useful for two-way widget bindings).
            **kwargs:
                Arbitrary metadata forwarded to callbacks.

        Raises:
            ValueError: If the resulting bounds are invalid.
            TypeError: If coercion to floats fails.
        """
        if "what_changed" in kwargs:
            raise TypeError("`what_changed` is managed by SmartParameter; do not pass it to set_bounds().")

        new_min = self._min_val if min_val is _UNSET else _coerce_optional_float("min_val", min_val)
        new_max = self._max_val if max_val is _UNSET else _coerce_optional_float("max_val", max_val)

        changed: list[str] = []
        if new_min != self._min_val:
            changed.append("min")
        if new_max != self._max_val:
            changed.append("max")

        if not changed:
            return

        self._validate_bounds(new_min, new_max)

        self._min_val = new_min
        self._max_val = new_max

        # Clamp current value, and record if clamping changes it.
        clamped = self._clamp_value(self._value, min_val=self._min_val, max_val=self._max_val)
        if clamped != self._value:
            self._value = clamped
            changed.append("value")

        self._notify(
            exclude_token=owner_token,
            owner_token=owner_token,
            what_changed=tuple(changed),
            **kwargs,
        )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_bounds(min_val: Optional[float], max_val: Optional[float]) -> None:
        """Validate min/max bounds."""
        if min_val is not None and max_val is not None and min_val > max_val:
            raise ValueError(f"Invalid bounds: min_val={min_val} > max_val={max_val}")

    @staticmethod
    def _clamp_value(value: float, *, min_val: Optional[float], max_val: Optional[float]) -> float:
        """Clamp a float to optional bounds."""
        v = float(value)
        if min_val is not None:
            v = max(v, float(min_val))
        if max_val is not None:
            v = min(v, float(max_val))
        return v

    def _coerce_and_clamp(self, new_val: Any) -> float:
        """Coerce `new_val` via `self.type` and clamp to bounds."""
        try:
            v = float(self.type(new_val))
        except Exception as e:  # pragma: no cover
            raise TypeError(
                f"SmartParameter({self.id!r}) expected value coercible by {self.type}, got {new_val!r}"
            ) from e

        return self._clamp_value(v, min_val=self._min_val, max_val=self._max_val)

    def _set_value_internal(
        self,
        new_val: Any,
        *,
        exclude_token: Optional[CallbackToken],
        owner_token: Optional[CallbackToken],
        what_changed: tuple[str, ...],
        **kwargs: Any,
    ) -> None:
        """Internal helper for value assignment and callback notification."""
        self._value = self._coerce_and_clamp(new_val)
        self._notify(exclude_token=exclude_token, owner_token=owner_token, what_changed=what_changed, **kwargs)

    def _notify(
        self,
        *,
        exclude_token: Optional[CallbackToken],
        owner_token: Optional[CallbackToken],
        what_changed: tuple[str, ...],
        **kwargs: Any,
    ) -> None:
        """Notify callbacks (weakref-aware, error-aggregating)."""
        self.last_callback_errors = []
        dead: list[CallbackToken] = []

        # Snapshot to allow callbacks to mutate registration safely.
        items: Iterable[tuple[CallbackToken, _CallbackEntry]] = tuple(self._callbacks_by_token.items())

        for token, entry in items:
            if exclude_token is not None and token == exclude_token:
                continue

            cb = entry.get_callable()
            if cb is None:
                dead.append(token)
                continue

            self._invoke_callback(
                token=token,
                label=entry.label,
                cb=cb,
                owner_token=owner_token,
                what_changed=what_changed,
                **kwargs,
            )

        for t in dead:
            self._callbacks_by_token.pop(t, None)

        if self.last_callback_errors:
            warnings.warn(
                f"{len(self.last_callback_errors)} callback(s) raised exceptions for "
                f"SmartParameter({self.id!r}). Inspect `param.last_callback_errors` for details.",
                RuntimeWarning,
                stacklevel=2,
            )

    def _invoke_callback(
        self,
        *,
        token: CallbackToken,
        label: str,
        cb: Callable[..., Any],
        owner_token: Optional[CallbackToken],
        what_changed: tuple[str, ...],
        **kwargs: Any,
    ) -> None:
        """Invoke callback with best-effort signature compatibility and aggregation."""
        try:
            cb(self, owner_token=owner_token, what_changed=what_changed, **kwargs)
            return
        except TypeError as e:
            if self._is_signature_mismatch(e):
                try:
                    cb(self)
                    return
                except Exception as e2:
                    self._record_callback_error(token, label, e2)
                    return
            self._record_callback_error(token, label, e)
            return
        except Exception as e:
            self._record_callback_error(token, label, e)
            return

    @staticmethod
    def _is_signature_mismatch(exc: TypeError) -> bool:
        """Best-effort detection that a TypeError came from a call signature mismatch.

        This is intentionally conservative: we only treat common "call-site"
        errors as mismatches (e.g. unexpected kwargs), and otherwise assume the
        callback raised the TypeError itself.
        """
        msg = str(exc)
        if "unexpected keyword argument" in msg or "got an unexpected keyword argument" in msg:
            return True
        if "missing" in msg and "required positional argument" in msg:
            return True
        if "positional argument" in msg and "were given" in msg:
            return True
        if "takes" in msg and "positional" in msg and "were given" in msg:
            return True
        return False

    def _record_callback_error(self, token: CallbackToken, label: str, exc: BaseException) -> None:
        """Append a `CallbackError` record for an exception."""
        self.last_callback_errors.append(
            CallbackError(
                token=token,
                label=label,
                exception=exc,
                traceback=_traceback.format_exc(),
            )
        )

    def __repr__(self) -> str:
        return (
            f"SmartParameter(id={self.id!r}, value={self.value!r}, "
            f"min_val={self.min_val!r}, max_val={self.max_val!r}, "
            f"step={self.step!r}, default_val={self.default_val!r})"
        )


class SmartParameterRegistry(MutableMapping[Hashable, SmartParameter]):
    """Dict-like registry of `SmartParameter`, auto-vivifying on access."""

    def __init__(self, param_factory: Optional[Callable[[Hashable], SmartParameter]] = None) -> None:
        self._data: Dict[Hashable, SmartParameter] = {}
        self._param_factory: Optional[Callable[[Hashable], SmartParameter]] = param_factory

    def __getitem__(self, key: Hashable) -> SmartParameter:
        if key in self._data:
            return self._data[key]
        param = self._param_factory(key) if self._param_factory is not None else SmartParameter(id=key)
        self._data[key] = param
        return param

    def __setitem__(self, key: Hashable, value: SmartParameter) -> None:
        if not isinstance(value, SmartParameter):
            raise TypeError(f"Registry values must be SmartParameter, got {type(value)!r}")
        if value.id != key:
            raise ValueError(
                "SmartParameterRegistry keys must match parameter.id. "
                f"Got key={key!r}, param.id={value.id!r}"
            )
        self._data[key] = value

    def __delitem__(self, key: Hashable) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def get_param(self, id: Hashable) -> SmartParameter:
        """Return an existing parameter or auto-create a new one."""
        return self[id]

    def set_value(self, id: Hashable, new_val: Any, **kwargs: Any) -> None:
        """Set a parameter value, forwarding kwargs to callbacks."""
        self[id].set(new_val, **kwargs)

    def set_protected(self, id: Hashable, new_val: Any, owner_token: CallbackToken, **kwargs: Any) -> None:
        """Protected set on a parameter by id."""
        self[id].set_protected(new_val, owner_token=owner_token, **kwargs)
