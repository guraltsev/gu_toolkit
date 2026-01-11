## Detailed technical blueprint (updated to “scan for idempotency”, no callback→token dict)

### 1. Purpose and scope

Implement a small reactive-parameter core suitable for JupyterLab usage:

* `SmartParameterRegistry`: a dict-like container keyed by immutable/hashable IDs (primarily SymPy `Symbol`), **auto-vivifies** parameters on access.
* `SmartParameter`: holds parameter metadata and a `value`. Setting `value` triggers callback notifications. A protected setter `set_protected(new_val, owner_token, **kwargs)` notifies all callbacks **except** the owner identified by `owner_token`, preventing feedback loops when multiple UI controllers share the same parameter.
* Callback registration is **idempotent** and stored with **weak references**, so rerunning “create widgets” cells doesn’t leak callbacks.
* Callback errors are **aggregated**; notification continues.

Non-goals:

* No widget implementations here (sliders/controllers built on top).
* No step on parameters (step belongs to each controller/widget).
* No async/debounce logic in v1 (but we leave clean seams to add later).

---

### 2. Public API

#### 2.1 `CallbackToken` (opaque handle)

A lightweight, hashable token returned from registration and used for exclusion/removal.

**Requirements**

* Opaque (user doesn’t inspect internals).
* Must not keep a strong reference to the callback.
* Comparable/hashable.

**Recommended**

```python
from dataclasses import dataclass
import uuid

@dataclass(frozen=True)
class CallbackToken:
    token: str  # uuid4 hex

def _new_token() -> CallbackToken:
    return CallbackToken(uuid.uuid4().hex)
```

---

#### 2.2 `SmartParameter`

**Constructor**

```python
SmartParameter(
    id,
    type=float,
    value=None,           # if None, initialize to default_val (recommended)
    min_val=-1.0,
    max_val=+1.0,
    default_val=0.0,
)
```

**Fields**

* `id`: immutable/hashable identifier
* `type`: callable used to coerce incoming values (default `float`)
* `min_val`: float or `None` (unbounded below)
* `max_val`: float or `None` (unbounded above)
* `default_val`: default numeric value
* `value`: property; setter does coerce→clamp→assign→notify (**always notify**)

**Callback methods**

* `register_callback(callback) -> CallbackToken`

  * idempotent: re-registering the same callback returns the same token
  * callbacks stored weakly
* `remove_callback(token) -> None`

  * ignore missing
* `set_protected(new_val, owner_token, **kwargs) -> None`

  * sets and notifies everyone **except** the callback registered under `owner_token`

**Callback invocation signature**
Callbacks are called like:

```python
callback(param, owner_token=<token_or_None>, **kwargs)
```

Compatibility policy (recommended):

* Try calling with `owner_token` and `**kwargs`.
* If that fails due to an unexpected keyword argument / signature mismatch, fall back to:

  ```python
  callback(param)
  ```
* If fallback also fails, aggregate the error.

This keeps “simple callbacks” usable while enabling richer future compatibility.

**Notification rules**

* Always notify on set (no `new_val == old_val` shortcut).
* Continue calling remaining callbacks even if some raise.
* Aggregate errors.

**Error aggregation surface**

* `last_callback_errors`: list of `CallbackError` from the most recent notify batch.
* Optional: `callback_error_log`: bounded deque of recent error batches.

**Warning surface**

* If any errors occurred during a notify batch: emit **one** `warnings.warn(...)` summary directing to `param.last_callback_errors`.

---

#### 2.3 `SmartParameterRegistry`

A dict-like container with auto-vivification.

**Constructor**

```python
SmartParameterRegistry(param_factory=None)
```

* `param_factory`: optional callable `id -> SmartParameter` to customize defaults.

**Behavior**

* `reg[key]` returns existing `SmartParameter` or creates one (auto-vivify).
* Enforce stored values are `SmartParameter` instances on `__setitem__`.

**Convenience methods (recommended)**

* `get_param(id) -> SmartParameter` (alias for `__getitem__`)
* `set_value(id, new_val, **kwargs) -> None`
* `set_protected(id, new_val, owner_token, **kwargs) -> None`

---

### 3. Internal callback storage (updated design: single dict + scans)

You requested: *no callback→token dict*. We implement idempotency by scanning existing registrations.

#### 3.1 Data structures inside `SmartParameter`

Maintain a single mapping:

* `_callbacks_by_token: dict[CallbackToken, _CallbackEntry]`

Because Python dict preserves insertion order (Py3.7+), iterating over `_callbacks_by_token.values()` yields registration order.

No reverse map is maintained. Idempotency is implemented by scanning entries and comparing normalized identities.

#### 3.2 `_CallbackEntry` abstraction

Each entry stores:

* `token: CallbackToken`
* a **weak reference mechanism** that can later yield a live callable or `None`
* a stable, human-readable `label` for error messages/debugging
* methods:

  * `get_callable() -> callable | None`
  * `matches(callback) -> bool`  (for idempotency)

Recommended shapes:

* For plain functions / callable objects that are weakref-able:

  * store `weakref.ref(callback_obj)`
  * `matches(cb)` compares `self_ref() is cb` (object identity)

* For bound methods:

  * store `weakref.WeakMethod(bound_method)`
  * `matches(cb)` checks:

    * `hasattr(cb, "__self__") and hasattr(cb, "__func__")`
    * compare `cb.__self__ is stored_self` and `cb.__func__ is stored_func`
    * (or, equivalently, compare dereferenced method’s `__self__`/`__func__`)

Why `WeakMethod` is essential:

* `obj.method` creates ephemeral bound-method objects; weakly storing the bound-method object itself will often vanish immediately.
* `WeakMethod` weakly references the instance and function, which is the behavior we need.

#### 3.3 Register logic (idempotent via scan)

Algorithm for `register_callback(cb)`:

1. Validate `cb` is callable.
2. Iterate over `_callbacks_by_token` entries:

   * if entry is dead (`entry.get_callable() is None`): mark token for removal
   * else if `entry.matches(cb)`: return `entry.token` (idempotent)
3. Remove any dead entries found during the scan.
4. Create a new token.
5. Create `_CallbackEntry` for `cb`:

   * if cb is bound method → `WeakMethod`
   * else → `weakref.ref(cb)` (if not possible, raise `TypeError`)
6. Insert entry into `_callbacks_by_token[token] = entry`.
7. Return token.

This piggybacks cleanup onto registration scans; no separate cleanup subsystem needed.

#### 3.4 Notification logic

Algorithm for `_notify(exclude_token, owner_token, **kwargs)`:

1. Reset `last_callback_errors = []`.
2. Iterate entries in insertion order:

   * if token equals `exclude_token`: continue
   * deref callable; if dead: mark token for removal and continue
   * call callback with rich signature:

     * try `cb(self, owner_token=owner_token, **kwargs)`
     * on signature mismatch `TypeError` (unexpected kw), try `cb(self)`
     * on exception: aggregate error with traceback; continue
3. Remove dead entries found during notify.
4. If any errors: emit a single `warnings.warn` summary.

Notes:

* Exclusion is by token (stable).
* `owner_token` passed to callbacks is:

  * `None` for normal `.value = ...`
  * the provided token for `set_protected`
* If `set_protected` is called with a token that’s not registered, exclusion becomes “exclude none” (still pass owner_token through).

#### 3.5 Coercion + clamping

Unified internal function:

```python
def _coerce_and_clamp(self, new_val):
    try:
        v = self.type(new_val)
    except Exception as e:
        raise TypeError(
            f"SmartParameter({self.id!r}) expected value coercible by {self.type}, got {new_val!r}"
        ) from e

    if self.min_val is not None:
        v = max(v, self.min_val)
    if self.max_val is not None:
        v = min(v, self.max_val)
    return v
```

Bounds validation:

* if both bounds not None and `min_val > max_val`: raise `ValueError`.

Initialization policy (recommended):

* If constructor `value is None`, set internal `_value = default_val` **without notifying callbacks** (no callbacks exist yet anyway, but avoid surprising side effects).

#### 3.6 Error aggregation record

Recommended:

```python
from dataclasses import dataclass

@dataclass
class CallbackError:
    token: CallbackToken
    label: str
    exception: BaseException
    traceback: str
```

Store `last_callback_errors: list[CallbackError]`.

Warning summary example:

* “2 callbacks raised exceptions for parameter 'a'. Inspect param.last_callback_errors for details.”

#### 3.7 Extensibility seam for thread-safety / async later

* Keep the invariant: **snapshot live callables / decide targets before calling them**.
* Later thread-safety:

  * add `threading.RLock`
  * under lock: coerce+clamp+assign + build list of `(token, callable)` + cleanup dead
  * release lock then invoke callbacks
* Later async scheduling:

  * add internal `self._dispatch(callable0)` hook (default direct call)
  * swap with `loop.call_soon`, executor submit, debounce scheduler

This can be added without changing the external API.

---

### 4. Documentation / UX notes (important for notebooks)

Because callbacks are weakly referenced:

* If a user registers a callback via an unnamed lambda and doesn’t store it, it may be garbage collected and stop firing.
* Widget/controller objects should be stored in variables (or registry-owned structures) across cell execution if they must stay alive.

Provide a short “gotchas” section in module docstrings.

---

## Implementation stages (functional after each stage)

### Stage 1 — `SmartParameter`: coercion, bounds, notify mechanics (strong refs, no tokens yet)

**Description and instructions**

* Implement `SmartParameter` fields and `value` property.
* Implement `_coerce_and_clamp`.
* Implement a simple strong-reference callback list `self._callbacks: list[callable]`.
* Implement `set_protected` excluding a specific callback object (temporary placeholder).

**Functional requirements**

* Coercion + clamping applied on every set.
* Always notify (no equality check).
* Unbounded sides use `None`.

**Regression requirements**

* Invalid bounds raise `ValueError`.
* Type coercion failures raise helpful `TypeError`.

**Completeness criteria**

* Basic tests for clamping/coercion/always-notify pass.

---

### Stage 2 — Introduce `CallbackToken` + token-based protected exclusion + idempotent scan (still strong refs)

**Description and instructions**

* Add `CallbackToken`.
* Replace callback list with `_callbacks_by_token: dict[token, callback]` (strong refs for now).
* Implement `register_callback(cb)`:

  * scan `dict.items()` for existing callback identity `is cb`; if found return existing token
  * else allocate new token and store
* Implement `remove_callback(token)` no-op if missing.
* Implement `set_protected(new_val, owner_token, **kwargs)` excluding by token.

**Functional requirements**

* Idempotent registration returns same token when re-registering the same callback object.
* `set_protected` excludes owner by token.

**Regression requirements**

* Stage 1 behavior preserved.

**Completeness criteria**

* Token-based exclusion and idempotency tests pass.

---

### Stage 3 — Switch to weakref callback entries + scan-based idempotency + cleanup piggyback

**Description and instructions**

* Replace stored callbacks with `_CallbackEntry` objects holding weakrefs:

  * bound method → `weakref.WeakMethod`
  * otherwise → `weakref.ref`
* Store entries as `_callbacks_by_token[token] = entry` (single dict).
* Implement `register_callback` via scan:

  * during scan, remove dead entries
  * use `entry.matches(cb)` for idempotency
* Implement notify-time cleanup (remove dead entries found while iterating).

**Functional requirements**

* Dead callbacks are not called and are removed.
* Rerunning cells that create and discard callback owners does not accumulate dead entries.

**Regression requirements**

* Idempotency still holds for live callbacks.
* Exclusion still works by token.

**Completeness criteria**

* Weakref cleanup tests (bound method owner deleted + gc) pass.

---

### Stage 4 — Callback signature flexibility + error aggregation + single warning

**Description and instructions**

* Implement `CallbackError` and `last_callback_errors`.
* Wrap callback invocation:

  * try rich call `cb(param, owner_token=..., **kwargs)`
  * if signature mismatch, fallback `cb(param)`
  * on exception, aggregate with traceback and continue
* Emit a single warning if any errors occurred.

**Functional requirements**

* Errors are aggregated; good callbacks still run.
* One warning per notify batch on error.
* `last_callback_errors` contains tracebacks.

**Regression requirements**

* No change to weakref behavior.
* No change to set semantics (still always notify).

**Completeness criteria**

* Aggregation/continue/warn tests pass.

---

### Stage 5 — Implement `SmartParameterRegistry` with auto-vivify + convenience methods

**Description and instructions**

* Implement `SmartParameterRegistry` as `collections.abc.MutableMapping`.
* Internal storage `self._data: dict`.
* `__getitem__`: auto-create using `param_factory` or `SmartParameter(id=key)`.
* `__setitem__`: enforce value is `SmartParameter`.
* Add `get_param`, `set_value`, `set_protected`.

**Functional requirements**

* Access auto-creates parameters with defaults.
* Convenience methods function as expected.

**Regression requirements**

* `SmartParameter` tests remain passing.

**Completeness criteria**

* Registry tests pass using SymPy symbol keys.
