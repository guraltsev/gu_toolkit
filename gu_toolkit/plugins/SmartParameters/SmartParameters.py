"""Module: SmartParameters.py

DESIGN OVERVIEW:
===============
This module provides a minimal "reactive parameter" primitive.

It implements **Stage 1 & Stage 2** of the project blueprint:

Stage 1:
  - A `SmartParameter` holds metadata (type, bounds, default) and a value.
  - Setting `value` coerces and clamps, then **always** notifies callbacks.

Stage 2:
  - Callback registration returns an opaque `CallbackToken`.
  - Callbacks are stored with *strong references* (weakrefs are Stage 3).
  - Registration is idempotent by scanning current callbacks for identity.
  - `set_protected(..., owner_token=...)` notifies all callbacks except the
    one registered under `owner_token`.

Important non-goals for these stages:
  - No weak-reference cleanup (Stage 3)
  - No callback error aggregation / warnings (Stage 4)
  - No `SmartParameterRegistry` auto-vivifying mapping (Stage 5)

API REFERENCE:
==============
CallbackToken
    Opaque, hashable handle returned from `SmartParameter.register_callback`.

SmartParameter
    Reactive scalar-like value with coercion/clamping and callback dispatch.

MAINTENANCE GUIDE:
=================
Key invariants:
  - `value` assignment always calls callbacks (no equality short-circuit).
  - Bounds validation: if both bounds are not None, require min_val <= max_val.
  - Idempotency: re-registering the same callback object returns same token.

Performance notes:
  - `register_callback` is O(n) due to the idempotency scan (by design).
  - This is acceptable because registrations happen rarely compared to value
    updates.

Testing strategy:
  - Use the doctests in `SmartParameter` docstrings for basic coverage.
  - Add pytest tests later when Stage 3+ introduces weakrefs and aggregation.
"""

from __future__ import annotations

__all__ = [
    "CallbackToken",
    "SmartParameter",
]

__gu_exports__ = __all__
__gu_priority__ = 200
__gu_enabled=True



import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, Iterable, Optional, TypeVar

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


class SmartParameter:
    """A reactive parameter with coercion, clamping, and callbacks.

    The parameter holds a `value`. Assigning to `value`:
      1) coerces via `type` (default: `float`),
      2) clamps to [min_val, max_val] where bounds are not None,
      3) stores the result,
      4) notifies callbacks.

    Callback behavior implemented here corresponds to Stage 2:
      - callbacks are stored strongly (no weakrefs yet),
      - registering the same callback object is idempotent,
      - `set_protected` can exclude the callback identified by `owner_token`.

    Examples:
        Coercion and clamping:
        >>> p = SmartParameter(id="a", min_val=-1.0, max_val=1.0, default_val=0.0)
        >>> p.value
        0.0
        >>> p.value = 10
        >>> p.value
        1.0
        >>> p.value = -5
        >>> p.value
        -1.0

        Always notify (even if value stays the same):
        >>> calls: list[float] = []
        >>> def cb(param: SmartParameter, **_: Any) -> None:
        ...     calls.append(param.value)
        >>> tok = p.register_callback(cb)
        >>> p.value = 0
        >>> p.value = 0
        >>> calls[-2:]
        [0.0, 0.0]

        Idempotent registration:
        >>> tok2 = p.register_callback(cb)
        >>> tok2 == tok
        True

        Protected set excludes owner callback:
        >>> calls.clear()
        >>> p.set_protected(0.5, owner_token=tok)
        >>> calls
        []

        Removing a callback:
        >>> p.remove_callback(tok)
        >>> p.value = 0.25
        >>> calls
        []

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
        """Create a parameter.

        Args:
            id: Immutable/hashable parameter identifier.
            type: Coercion function used for incoming values.
            value: Initial value. If None, initializes to `default_val`.
            min_val: Optional lower bound. None means unbounded below.
            max_val: Optional upper bound. None means unbounded above.
            default_val: Default numeric value.

        Raises:
            ValueError: If min_val > max_val (when both are not None).
            TypeError: If the initial value cannot be coerced.
        """

        self.id: Hashable = id
        self.type: Callable[[Any], float] = type
        self.min_val: Optional[float] = min_val
        self.max_val: Optional[float] = max_val
        self.default_val: float = float(default_val)

        self._validate_bounds()

        # Stage 2 storage: strong references only.
        self._callbacks_by_token: Dict[CallbackToken, Callable[..., Any]] = {}

        initial = self.default_val if value is None else value
        # Do not notify during initialization.
        self._value: float = self._coerce_and_clamp(initial)

    def _validate_bounds(self) -> None:
        """Validate min/max bounds."""

        if self.min_val is not None and self.max_val is not None:
            if self.min_val > self.max_val:
                raise ValueError(
                    f"SmartParameter({self.id!r}) has invalid bounds: "
                    f"min_val={self.min_val} > max_val={self.max_val}"
                )

    def _coerce_and_clamp(self, new_val: Any) -> float:
        """Coerce `new_val` via `self.type` and clamp to bounds."""

        try:
            v = float(self.type(new_val))
        except Exception as e:  # pragma: no cover (exact exception depends on `type`)
            raise TypeError(
                f"SmartParameter({self.id!r}) expected value coercible by {self.type}, "
                f"got {new_val!r}"
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

    def register_callback(self, callback: Callable[..., Any]) -> CallbackToken:
        """Register a callback.

        Registration is idempotent by *identity*:
        re-registering the same callback object returns the same token.

        Args:
            callback: Callable invoked when the parameter value changes.

        Returns:
            CallbackToken for later removal and for protected updates.

        Raises:
            TypeError: If callback is not callable.

        Notes:
            - Stage 2 stores callbacks with strong references.
            - Stage 3 will switch this storage to weak references.
        """

        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)!r}")

        # Idempotency scan (O(n) by design).
        for token, existing in self._callbacks_by_token.items():
            if existing is callback:
                return token

        token = _new_token()
        self._callbacks_by_token[token] = callback
        return token

    def remove_callback(self, token: CallbackToken) -> None:
        """Remove a callback by token.

        Missing tokens are ignored.
        """

        self._callbacks_by_token.pop(token, None)

    def set_protected(
        self,
        new_val: Any,
        owner_token: CallbackToken,
        **kwargs: Any,
    ) -> None:
        """Set the value, notifying all callbacks except the owner.

        Args:
            new_val: New value to assign.
            owner_token: The token of the callback to *exclude* from notification.
            **kwargs: Forwarded to callbacks that accept `owner_token` / kwargs.

        Notes:
            - Exclusion is token-based.
            - If `owner_token` is unknown, exclusion effectively excludes none.
        """

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
        """Notify callbacks.

        Stage 1/2 behavior:
            - No error aggregation: exceptions propagate.
            - Strong refs only.

        Forward compatibility:
            - We *attempt* to call callbacks with the richer signature
              `cb(param, owner_token=..., **kwargs)`. If this fails due to
              signature mismatch, we fall back to `cb(param)`.
        """

        # Make a stable snapshot in case callbacks modify registration.
        items: Iterable[tuple[CallbackToken, Callable[..., Any]]] = tuple(self._callbacks_by_token.items())
        for token, cb in items:
            if exclude_token is not None and token == exclude_token:
                continue
            self._invoke_callback(cb, owner_token=owner_token, **kwargs)

    def _invoke_callback(self, cb: Callable[..., Any], *, owner_token: Optional[CallbackToken], **kwargs: Any) -> None:
        """Invoke callback with best-effort signature compatibility."""

        # Forward-compatible default: always try the richer signature first,
        # even when owner_token is None.
        try:
            cb(self, owner_token=owner_token, **kwargs)
        except TypeError as e:
            # Best-effort detection of signature mismatch.
            msg = str(e)
            signature_mismatch = (
                "unexpected keyword argument" in msg
                or "got an unexpected keyword argument" in msg
                or "positional" in msg
                or "required positional" in msg
            )
            if not signature_mismatch:
                raise
            cb(self)

    def __repr__(self) -> str:
        return (
            f"SmartParameter(id={self.id!r}, value={self.value!r}, "
            f"min_val={self.min_val!r}, max_val={self.max_val!r}, "
            f"default_val={self.default_val!r})"
        )
