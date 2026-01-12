"""Module: SmartParameters.py

DESIGN OVERVIEW:
===============
This module provides a small "reactive parameter" core intended for
Jupyter/JupyterLab usage.

It implements **Stages 1–5** of the project blueprint:

Stage 1:
  - A `SmartParameter` holds metadata (type, bounds, default) and a value.
  - Setting `value` coerces and clamps, then **always** notifies callbacks.

Stage 2:
  - Callback registration returns an opaque `CallbackToken`.
  - Registration is idempotent (re-registering the same callback returns the
    original token).
  - `set_protected(..., owner_token=...)` notifies all callbacks **except** the
    owner identified by the token.

Stage 3:
  - Callbacks are stored using **weak references** (including bound methods via
    `weakref.WeakMethod`).
  - Dead callbacks are automatically ignored and removed during registration and
    notification scans.

Stage 4:
  - Callback invocation supports a flexible signature:
        cb(param, owner_token=..., **kwargs)
    with fallback to:
        cb(param)
  - Callback exceptions are **aggregated** into `last_callback_errors`, and
    notification continues.
  - A single warning is emitted per notify batch when errors occurred.

Stage 5:
  - `SmartParameterRegistry`: a dict-like, auto-vivifying container for
    `SmartParameter` instances, keyed by immutable IDs (e.g. SymPy Symbols).

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
  - Value assignment always notifies (no equality short-circuit).
  - Bounds validation: if both bounds are not None, require min_val <= max_val.
  - Registration is idempotent (by normalized identity), implemented via scans.

Performance notes:
  - `register_callback` is O(n) due to the idempotency scan (by design).
  - Notification is O(n) in the number of live callbacks.

Testing strategy:
  - Use doctests in docstrings for basic coverage.
  - For weakref behavior, include tests that delete callback owners and `gc.collect()`.
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

    The parameter holds a `value`. Assigning to `value`:
      1) coerces via `type` (default: `float`),
      2) clamps to [min_val, max_val] where bounds are not None,
      3) stores the result,
      4) notifies callbacks.

    Callback behavior:
      - Callbacks are weakly referenced (including bound methods).
      - Registering the same callback is idempotent: it returns the same token.
      - `set_protected` can exclude the owner callback identified by `owner_token`.
      - Callback errors are aggregated into `last_callback_errors`, and remaining
        callbacks are still invoked.
    """

    def __init__(
        self,
        id: Hashable,
        *,
        type: Callable[[Any], float] = float,
        value: Optional[Any] = None,
        min_val: Optional[float] = -1.0,
        max_val: Optional[float] = 1.0,
        default_val: float = 0.0,
    ) -> None:
        """Create a parameter."""
        self.id: Hashable = id
        self.type: Callable[[Any], float] = type
        self.min_val: Optional[float] = min_val
        self.max_val: Optional[float] = max_val
        self.default_val: float = float(default_val)

        self._validate_bounds()

        # Weakref-backed storage, idempotency implemented via scans (O(n)).
        self._callbacks_by_token: Dict[CallbackToken, _CallbackEntry] = {}

        # Error aggregation (most recent notify batch).
        self.last_callback_errors: list[CallbackError] = []

        initial = self.default_val if value is None else value
        # Do not notify during initialization.
        self._value: float = self._coerce_and_clamp(initial)

    def _validate_bounds(self) -> None:
        """Validate min/max bounds."""
        if self.min_val is not None and self.max_val is not None and self.min_val > self.max_val:
            raise ValueError(
                f"SmartParameter({self.id!r}) has invalid bounds: "
                f"min_val={self.min_val} > max_val={self.max_val}"
            )

    def _coerce_and_clamp(self, new_val: Any) -> float:
        """Coerce `new_val` via `self.type` and clamp to bounds."""
        try:
            v = float(self.type(new_val))
        except Exception as e:  # pragma: no cover
            raise TypeError(
                f"SmartParameter({self.id!r}) expected value coercible by {self.type}, got {new_val!r}"
            ) from e

        if self.min_val is not None:
            v = max(v, self.min_val)
        if self.max_val is not None:
            v = min(v, self.max_val)
        return v

    @property
    def value(self) -> float:
        """The current value."""
        return self._value

    @value.setter
    def value(self, new_val: Any) -> None:
        """Set the value (coerce+clamp) and notify all callbacks."""
        self._set_value_internal(new_val, exclude_token=None, owner_token=None)

    def set(self, new_val: Any, **kwargs: Any) -> None:
        """Set the value and forward keyword arguments to callbacks.

        This method exists because the `value` property setter cannot accept
        keyword arguments.
        """
        self._set_value_internal(new_val, exclude_token=None, owner_token=None, **kwargs)

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
        """Set the value, notifying all callbacks except the owner."""
        self._set_value_internal(new_val, exclude_token=owner_token, owner_token=owner_token, **kwargs)

    def _set_value_internal(
        self,
        new_val: Any,
        *,
        exclude_token: Optional[CallbackToken],
        owner_token: Optional[CallbackToken],
        **kwargs: Any,
    ) -> None:
        """Internal helper for value assignment and callback notification."""
        self._value = self._coerce_and_clamp(new_val)
        self._notify(exclude_token=exclude_token, owner_token=owner_token, **kwargs)

    def _notify(
        self,
        *,
        exclude_token: Optional[CallbackToken],
        owner_token: Optional[CallbackToken],
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
        **kwargs: Any,
    ) -> None:
        """Invoke callback with best-effort signature compatibility and aggregation."""
        try:
            cb(self, owner_token=owner_token, **kwargs)
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
            f"default_val={self.default_val!r})"
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
