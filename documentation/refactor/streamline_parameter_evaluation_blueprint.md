# Streamline Parameter Evaluation — Detailed Blueprint

## Table of Contents

1. [New class: `NumpifiedFunction`](#1-new-class-numpifiedfunction)
2. [New class: `BoundNumpifiedFunction`](#2-new-class-boundnumpifiedfunction)
3. [Changes to `numpify.py`](#3-changes-to-numpifypy)
4. [Changes to `SmartFigure.py` context management](#4-changes-to-smartfigurepy-context-management)
5. [Migration of `NumericExpression.py`](#5-migration-of-numericexpressionpy)
6. [Changes to `SmartPlot`](#6-changes-to-smartplot)
7. [Public API / `__init__.py`](#7-public-api--__init__py)
8. [Architectural critique](#8-architectural-critique)

---

## 1. New class: `NumpifiedFunction`

**File:** `numpify.py` (add near top, after imports)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

import sympy as sp

if TYPE_CHECKING:
    from .SmartFigure import SmartFigure
    from .ParameterSnapshot import ParameterSnapshot


class NumpifiedFunction:
    """A compiled sympy→numpy callable that carries its own metadata.

    Attributes
    ----------
    expr : sp.Basic
        The sympy expression (post-expansion) that was compiled.
    args : tuple[sp.Symbol, ...]
        Ordered argument symbols matching the positional signature.
    source : str
        Generated Python source code of the inner function.
    """

    __slots__ = ("_fn", "expr", "args", "source")

    def __init__(
        self,
        fn: Callable[..., Any],
        expr: sp.Basic,
        args: tuple[sp.Symbol, ...],
        source: str,
    ) -> None:
        self._fn = fn
        self.expr = expr
        self.args = args
        self.source = source

    # --- Callable protocol -------------------------------------------

    def __call__(self, *positional_args: Any) -> Any:
        """Evaluate with positional args in the same order as self.args."""
        return self._fn(*positional_args)

    # --- Binding -----------------------------------------------------

    def bind(
        self,
        source: "SmartFigure | ParameterSnapshot | dict[sp.Symbol, Any] | None" = None,
    ) -> "BoundNumpifiedFunction":
        """Bind parameter values and return a partially-applied callable.

        Parameters
        ----------
        source
            - ``dict[Symbol, value]`` or ``ParameterSnapshot`` →
              dead (snapshot) binding.  Values are captured immediately.
            - ``SmartFigure`` instance → live binding.
              Parameter values are read from the figure on every call.
            - ``None`` → live binding to the current figure from the
              context stack (``_require_current_figure()``).

        Returns
        -------
        BoundNumpifiedFunction
        """
        # Lazy import to avoid circular dependency
        from .SmartFigure import SmartFigure as _SmartFigure, _require_current_figure
        from .ParameterSnapshot import ParameterSnapshot as _Snap

        if source is None:
            # Live-bind to current context figure
            fig = _require_current_figure()
            return BoundNumpifiedFunction(parent=self, figure=fig)

        if isinstance(source, _SmartFigure):
            return BoundNumpifiedFunction(parent=self, figure=source)

        if isinstance(source, (_Snap, dict)):
            return BoundNumpifiedFunction(parent=self, snapshot=source)

        raise TypeError(
            f"bind() expects SmartFigure, ParameterSnapshot, dict, or None; "
            f"got {type(source).__name__}"
        )

    # --- Introspection -----------------------------------------------

    @property
    def arg_names(self) -> tuple[str, ...]:
        """Symbol names in argument order."""
        return tuple(s.name for s in self.args)

    def __repr__(self) -> str:
        args_str = ", ".join(s.name for s in self.args)
        return f"NumpifiedFunction({self.expr!r}, args=({args_str}))"
```

### Design decisions

- **`__slots__`** keeps the object lightweight — these are created frequently
  via `numpify_cached`.
- **`_fn`** is the raw compiled function (the `_generated` from `exec`).
  Keeping it private discourages bypassing the wrapper.
- The class is intentionally **not a dataclass** because `__call__` semantics
  and custom `__repr__` are cleaner on a plain class, and frozen dataclasses
  forbid setting `_fn`.

---

## 2. New class: `BoundNumpifiedFunction`

**File:** `numpify.py` (immediately after `NumpifiedFunction`)

```python
class BoundNumpifiedFunction:
    """A NumpifiedFunction with some or all parameters pre-bound.

    Supports two mutually exclusive modes:

    Dead (snapshot) mode
        Parameter values captured at bind-time.  Deterministic.

    Live (figure) mode
        Parameter values read from a SmartFigure on every __call__.
    """

    __slots__ = ("parent", "_figure", "_snapshot_values", "_free_indices")

    def __init__(
        self,
        parent: NumpifiedFunction,
        *,
        figure: "SmartFigure | None" = None,
        snapshot: "ParameterSnapshot | dict[sp.Symbol, Any] | None" = None,
    ) -> None:
        self.parent = parent
        self._figure = figure
        self._snapshot_values: tuple[Any, ...] | None = None
        self._free_indices: tuple[int, ...] | None = None

        if snapshot is not None:
            self._resolve_snapshot(snapshot)

    def _resolve_snapshot(self, source: Any) -> None:
        """Coerce snapshot/dict to an ordered tuple of values."""
        from .ParameterSnapshot import ParameterSnapshot as _Snap

        if isinstance(source, _Snap):
            value_map = source.values_only()
        elif isinstance(source, dict):
            value_map = source
        else:
            raise TypeError(f"Expected ParameterSnapshot or dict, got {type(source)}")

        # Build bound-value tuple aligned to self.parent.args
        vals: list[Any] = []
        free: list[int] = []
        for i, sym in enumerate(self.parent.args):
            if sym in value_map:
                vals.append(value_map[sym])
            else:
                vals.append(None)  # placeholder
                free.append(i)

        self._snapshot_values = tuple(vals)
        self._free_indices = tuple(free)

    # --- Callable protocol -------------------------------------------

    def __call__(self, *free_args: Any) -> Any:
        """Evaluate the function.

        In dead-bind mode
            ``free_args`` fills any unbound argument slots.
        In live-bind mode
            ``free_args`` fills the independent-variable slot(s).
            Remaining args are fetched live from the figure.
        """
        if self._figure is not None:
            return self._eval_live(*free_args)
        return self._eval_dead(*free_args)

    def _eval_live(self, *free_args: Any) -> Any:
        """Read parameter values from the bound SmartFigure."""
        assert self._figure is not None
        params = self._figure.params
        full: list[Any] = list(free_args)
        # Append bound parameters in the order they appear in parent.args,
        # skipping those already provided as free_args (assumed to be the
        # leading positions — typically just the independent variable x).
        n_free = len(free_args)
        for sym in self.parent.args[n_free:]:
            full.append(params[sym].value)
        return self.parent._fn(*full)

    def _eval_dead(self, *free_args: Any) -> Any:
        """Evaluate using captured snapshot values."""
        assert self._snapshot_values is not None
        assert self._free_indices is not None

        full = list(self._snapshot_values)
        if len(free_args) != len(self._free_indices):
            raise TypeError(
                f"Expected {len(self._free_indices)} free arg(s), got {len(free_args)}"
            )
        for idx, val in zip(self._free_indices, free_args):
            full[idx] = val
        return self.parent._fn(*full)

    # --- Navigation --------------------------------------------------

    def unbind(self) -> NumpifiedFunction:
        """Return the original unwrapped NumpifiedFunction."""
        return self.parent

    @property
    def is_live(self) -> bool:
        return self._figure is not None

    def __repr__(self) -> str:
        mode = "live" if self.is_live else "dead"
        return f"BoundNumpifiedFunction({self.parent!r}, mode={mode})"
```

### Design decisions

- **Two modes in one class** is simpler than a class hierarchy.  The modes are
  mutually exclusive and small — a base class + two subclasses would add
  indirection for no real benefit.
- **`_free_indices`** enables partial binding (e.g., bind parameters but leave
  the independent variable free).  This is the common case for
  `SmartPlot._eval_numeric_live()`.
- **Live mode convention:** free args are the *leading* positional args (the
  independent variable `x`), and the rest are fetched from the figure.  This
  mirrors the existing `[var] + parameters` ordering in `SmartPlot.set_func()`.

---

## 3. Changes to `numpify.py`

### 3a. `numpify()` return type

Replace the final section (currently lines 270–297) that builds docstring and
attaches `_generated_source`:

```python
    # Current code (to be replaced):
    #   fn.__doc__ = ...
    #   setattr(fn, "_generated_source", src)
    #   setattr(fn, "_generated_expr_code", expr_code)
    #   return fn

    # New:
    return NumpifiedFunction(fn=fn, expr=expr, args=args_tuple, source=src)
```

The `NumpifiedFunction` wraps the raw `fn` and carries `expr`, `args`, and
`source` as first-class attributes.

### 3b. `numpify_cached()` — preserve cache identity

`_numpify_cached_impl` already returns whatever `numpify()` returns, so this
change is transparent.  The LRU cache will store `NumpifiedFunction` instances.

**No further changes needed** — the `_FrozenFNumPy` cache key logic is
unaffected.

### 3c. Backward compatibility

`NumpifiedFunction.__call__` delegates to the inner `_fn`, so existing code
that calls the result of `numpify(...)` positionally keeps working.

However:

- `getattr(fn, "_generated_source")` → use `.source` instead.
- `fn.__doc__` → the class can implement `__doc__` as a property or just not
  set it on the inner `_fn`.  Decide based on whether any downstream code reads
  it.
- `isinstance(result, types.FunctionType)` → will now be `False`.  Audit
  callers.

### 3d. Deprecation shims (optional, short-term)

```python
@property
def _generated_source(self) -> str:
    import warnings
    warnings.warn("Use .source instead of ._generated_source", DeprecationWarning)
    return self.source
```

**Critique:** These shims add noise.  If the only consumers are internal
(`SmartPlot`, `NumericExpression`), skip the shims and update callers directly.

---

## 4. Changes to `SmartFigure.py` context management

### 4a. Expose a public `current_figure()` function

Currently the stack helpers are private (`_current_figure`,
`_require_current_figure`).  Add a thin public API:

```python
# SmartFigure.py — module level, after _require_current_figure

def current_figure(*, required: bool = True) -> "SmartFigure | None":
    """Return the active SmartFigure from the context stack.

    Parameters
    ----------
    required : bool
        If True (default), raise RuntimeError when no figure is active.
        If False, return None.
    """
    fig = _current_figure()
    if fig is None and required:
        raise RuntimeError(
            "No active SmartFigure. Use `with fig:` to set one, "
            "or pass an explicit figure to .bind()."
        )
    return fig
```

### 4b. Export from `__init__.py`

```python
from .SmartFigure import current_figure
```

### 4c. `NumpifiedFunction.bind(None)` uses this

```python
# In NumpifiedFunction.bind():
if source is None:
    from .SmartFigure import current_figure as _current_figure
    fig = _current_figure(required=True)
    return BoundNumpifiedFunction(parent=self, figure=fig)
```

### 4d. Critique: coupling direction

`numpify.py` importing from `SmartFigure.py` creates an **upward dependency**
(compilation layer → UI layer).  This is acceptable because:

- The import is **lazy** (inside `bind()`), so `numpify` can still be used
  standalone without SmartFigure loaded.
- An alternative is to define a `ParameterSource` protocol and have
  `SmartFigure` implement it, but the protocol would be isomorphic to
  "has `.params` returning a `Mapping[Symbol, ParamRef]`" — just a dict
  lookup.  The protocol adds a file and an abstraction for one consumer.  Not
  worth it now, but worth revisiting if more parameter sources appear.

---

## 5. Migration of `NumericExpression.py`

### Current state

Three dataclasses in `NumericExpression.py`:

| Class | Stores | Callable? |
|-|-|-|
| `DeadUnboundNumericExpression` | `core`, `parameters` | Raises on call |
| `DeadBoundNumericExpression` | `core`, `parameters`, `bound_values` | Yes (dead) |
| `LiveNumericExpression` | `plot` (SmartPlot ref) | Yes (live) |

### Target state

These classes become **thin facades** over `NumpifiedFunction` /
`BoundNumpifiedFunction`:

```python
@dataclass(frozen=True)
class DeadUnboundNumericExpression:
    numpified: NumpifiedFunction

    @property
    def core(self) -> Callable[..., Any]:
        return self.numpified._fn

    @property
    def parameters(self) -> tuple[Symbol, ...]:
        return self.numpified.args

    def bind(self, source: ...) -> DeadBoundNumericExpression:
        bound = self.numpified.bind(source)
        return DeadBoundNumericExpression(bound=bound)


@dataclass(frozen=True)
class DeadBoundNumericExpression:
    bound: BoundNumpifiedFunction

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return self.bound(x)

    def unbind(self) -> DeadUnboundNumericExpression:
        return DeadUnboundNumericExpression(numpified=self.bound.parent)


@dataclass(frozen=True)
class LiveNumericExpression:
    bound: BoundNumpifiedFunction  # live-bound to a figure

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return self.bound(x)
```

### Critique: keep or remove the facade?

**Argument to keep:** The facade gives semantic names (`LiveNumericExpression`
vs `DeadBound...`) and constrains the API surface for plot-specific code.
Notebook users who inspect objects see meaningful type names.

**Argument to remove:** The facade is now almost zero-logic delegation.
`BoundNumpifiedFunction` already distinguishes live vs dead via `.is_live`.
Removing the facade cuts ~80 lines and one file.

**Recommendation:** Keep the facades for now as **type aliases with
construction helpers**, deprecate direct instantiation, and revisit removal
once all internal callers are migrated.

---

## 6. Changes to `SmartPlot`

### Current state (`SmartFigure.py` ~line 1550)

```python
def set_func(self, var, func, parameters=[]):
    self._core = numpify_cached(func, args=[var] + parameters)
    self._var = var
    self._parameters = tuple(parameters)
    self._func = func
```

And evaluation (`~line 1602`):

```python
def _eval_numeric_live(self, x):
    fig = self._smart_figure
    args = [x]
    for symbol in self._parameters:
        args.append(fig.params[symbol].value)
    return self._core(*args)
```

### Target state

```python
def set_func(self, var, func, parameters=[]):
    self._numpified = numpify_cached(func, args=[var] + parameters)
    self._var = var
    self._func = func
    # Parameters are now introspectable from self._numpified.args

def _eval_numeric_live(self, x):
    # Option A: use live binding (created once, reads figure each call)
    bound = self._numpified.bind(self._smart_figure)
    return bound(x)

    # Option B: keep manual loop for zero-overhead (no wrapper allocation)
    params = self._smart_figure.params
    args = [x]
    for sym in self._numpified.args[1:]:  # skip var
        args.append(params[sym].value)
    return self._numpified(*args)
```

**Recommendation:** Use Option B for the hot path (render loop), and expose
Option A via the `numeric_expression` property for external consumers.

### Property migration

```python
@property
def parameters(self) -> tuple[Symbol, ...]:
    """Parameter symbols (excludes independent variable)."""
    return self._numpified.args[1:]  # args[0] is var

@property
def numeric_expression(self) -> LiveNumericExpression:
    bound = self._numpified.bind(self._smart_figure)
    return LiveNumericExpression(bound=bound)
```

The separate `_parameters` field is removed; it is derived from
`_numpified.args`.

---

## 7. Public API / `__init__.py`

### New exports

```python
from .numpify import NumpifiedFunction, BoundNumpifiedFunction
from .SmartFigure import current_figure
```

### Unchanged exports

All existing `plot`, `params`, `parameter`, `render`, etc. remain.

---

## 8. Architectural Critique

### Strengths of this design

1. **Single source of truth** — argument order and expression live with the
   compiled function, not duplicated across `SmartPlot._parameters`,
   `DeadUnboundNumericExpression.parameters`, etc.

2. **Standalone usability** — `NumpifiedFunction` is useful outside the figure
   context (batch evaluation, testing, serialization) because it carries its
   own metadata.

3. **Smooth migration** — `NumpifiedFunction.__call__` is drop-in compatible
   with the current bare callable, so callers can be updated incrementally.

### Weaknesses / risks

1. **Implicit context (`bind(None)`)** — global mutable state via
   `_FIGURE_STACK` is a known footgun.  In async or multi-threaded scenarios
   it will break.  The toolkit is currently single-threaded Jupyter, but this
   should be flagged with a "not thread-safe" note.

2. **Live binding holds a strong reference** to the `SmartFigure`.  If a
   `BoundNumpifiedFunction` outlives the figure (stored in a variable after the
   figure is closed), it silently reads stale widget values or crashes.
   Consider a `weakref` to the figure with a clear error on access-after-close.

3. **Cache wrapping overhead** — `numpify_cached` LRU cache will now store
   `NumpifiedFunction` objects.  Since the wrapper is lightweight (`__slots__`,
   no copies), overhead is negligible.  But if the same expression is compiled
   with different `f_numpy` bindings, the cache stores separate
   `NumpifiedFunction` instances that share no state — same as today.

4. **`isinstance` breakage** — any code doing
   `isinstance(fn, types.FunctionType)` will fail.  The fix is to check
   `callable(fn)` instead.  Audit `SmartPlot`, tests, and notebooks.

5. **Partial binding ambiguity** — `BoundNumpifiedFunction` supports partial
   binding (some args bound, some free).  The caller must know which positional
   slots are free.  This is fine for the `[var, *params]` convention but could
   confuse users who bind an arbitrary subset.  Document the convention:
   *leading args are free, trailing args are bound*.

6. **Two binding APIs** — users can now bind via
   `numpified.bind(snapshot)` *or* via the `NumericExpression` wrappers.
   During migration both paths exist.  Clear deprecation warnings on the old
   path will prevent confusion.

### Recommended implementation order

1. Add `NumpifiedFunction` and `BoundNumpifiedFunction` to `numpify.py`.
2. Change `numpify()` return to `NumpifiedFunction`.
3. Add `current_figure()` public helper to `SmartFigure.py`.
4. Update `SmartPlot.set_func()` and `_eval_numeric_live()`.
5. Migrate `NumericExpression.py` to delegate to new classes.
6. Update `__init__.py` exports.
7. Update tests.
8. Audit notebooks for `_generated_source` / `isinstance` usage.
