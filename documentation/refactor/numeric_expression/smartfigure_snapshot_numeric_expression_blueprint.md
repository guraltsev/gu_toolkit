# Blueprint: ParameterSnapshot + NumericExpression (SmartFigure)

## Goals

1. **Info cards** (and other consumers) can evaluate plotted functions numerically without manually substituting parameters.
2. Provide **snapshot semantics**:
   - `fig.params.snapshot()` produces a *dead* snapshot of parameter state (value + available metadata).
   - Snapshots preserve **creation order** so they can later be used to recreate the parameter UI/state.
3. Provide a **numerical-expression API** on each plot:
   - Default is “live” w.r.t. the figure’s current parameter values.
   - Can be *bound* to a snapshot or a value dict (dead).
   - Can be *unbound* to require explicit parameters.
4. Preserve `numpify_cached` compilation + caching: compilation remains a single cached core callable; binding does not trigger recompilation.

Non-goals (for this milestone)
- No optional validation of bound values.
- No automatic reattachment of an unbound evaluator back to a live figure.
- No UI restoration implementation beyond storing enough information (restoration will be implemented later).

---

## Current State (as implemented)

### SmartPlot render path (today)
In `SmartPlot.render()`:
1. It computes `x_values` from figure viewport and sampling.
2. It builds `args = [x_values] + [fig.params[p].value for p in self._parameters]`.
3. It calls the compiled function: `y = self._f_numpy(*args)`.

Compilation is performed in `SmartPlot.set_func(...)` using:
- `self._f_numpy = numpify_cached(func, args=[var] + parameters)`

So:
- compilation is cached (good),
- parameter value substitution is currently **manual** in `render()` (undesired duplication for info cards).

### ParameterManager (today)
`fig.params` is a `ParameterManager` holding:
- `_refs: Dict[Symbol, ParamRef]` (in insertion/creation order),
- `parameter(...)` creates `SmartFloatSlider` controls and registers observers,
- mapping interface (`__getitem__`, `items()`, etc.),
- **no snapshot** capability.

### ParamRef / ProxyParamRef (today)
- `ParamRef` is a `Protocol` exposing `parameter`, `widget`, `value`, `observe`, `reset`.
- `ProxyParamRef` exposes optional properties (`default_value`, `min`, `max`, `step`) when widget supports them.
- `ProxyParamRef.capabilities()` exists as a **method** returning `dict[str,bool]`.

---

## Target API

### 1) Snapshot API

#### Live manager
```python
snap = fig.params.snapshot()  # -> ParameterSnapshot
```

#### Snapshot object
- Behaves as an **ordered mapping**: `Symbol -> ParameterSnapshotEntry`
- Order is the manager’s **creation order**.
- Snapshot is **dead/immutable**: modifying it has no effect on the figure.

#### Convenience extraction
```python
values = snap.values_only()   # -> dict[Symbol, Any] (unordered ok)
```

#### Snapshot entry
Each entry stores:
- `value` (required)
- optional metadata *only when available*:
  - `default_value`, `min`, `max`, `step`
- `capabilities: list[str]` — names of metadata fields that exist for this ref/widget

Capabilities strings are stable keys, e.g.:
- `"value"` is always implicit; capabilities list covers optional fields:
  - `"default_value"`, `"min"`, `"max"`, `"step"`

### 2) Plot numerical-expression API

For `plot = fig.plots[id]`:

```python
plot.symbolic_expression     # -> sympy.Expr  (public; _func becomes internal)
plot.parameters              # -> tuple[Symbol, ...] (deterministic order; today = the order used for numpify args)
plot.numeric_expression      # -> NumericExpression (callable object)
```

Behavior:
- `plot.numeric_expression(x_array)` evaluates using **live** figure parameter values (by dereferencing a weakref to the ParameterManager).
- `plot.numeric_expression.unbind()` returns an **unbound** callable object that requires explicit parameter values, in `plot.parameters` order.
- `plot.numeric_expression.bind(snapshot_or_dict)` returns a **dead** callable object bound to:
  - a `ParameterSnapshot` (uses its values),
  - or a `dict[Symbol, value]`.
  Extra keys are ignored; missing required keys raise.

Binding/unbinding must not recompile.

---

## Core Design Decisions

### A) Capabilities as a getter (not a method)
- Replace `ProxyParamRef.capabilities()` with a `@property capabilities -> list[str]`.
- `ParameterSnapshot` stores a copy of `capabilities` (list of strings) per entry.

Rationale:
- Capabilities are state, not an action.
- Snapshot production should not depend on calling a method with side effects.

Back-compat strategy (optional):
- keep `capabilities()` as deprecated alias to the property for one release, or remove immediately if you truly do not need compatibility.

### B) Snapshot ordering
- `ParameterManager._refs` insertion order is the ordering source.
- `ParameterSnapshot` stores entries in that order, using an `OrderedDict` or (in modern Python) a `dict` populated in iteration order.

### C) NumericExpression holds weakref to ParameterManager
- Prevent strong reference cycles: figure → plot → numeric_expression → params → figure/widget graph.
- If weakref is dead at evaluation time: raise a clear error.

### D) Immutability
- `ParameterSnapshot` immutable.
- `NumericExpression` immutable:
  - `.bind()` / `.unbind()` return new objects.
- Live evaluation is “live” only in the sense “read current values on call”, not “track plot definition changes”.

### E) No validation
- `bind(dict)` does not validate ranges or types.
- `bind` checks only key coverage (missing required symbols).

---

## Detailed Data Model

### 1) `ParameterSnapshotEntry`
A frozen dataclass, or a minimal immutable record:

Required:
- `symbol: Symbol`
- `value: Any`
- `capabilities: tuple[str, ...]`  (store as tuple internally; expose list if desired)

Optional (only present when capability exists):
- `default_value: Any` (optional)
- `min: Any` (optional)
- `max: Any` (optional)
- `step: Any` (optional)

**“Store what exists” policy**
- When a capability is absent, the field is either:
  - omitted from the entry entirely (if entry is a mapping-like),
  - or set to a sentinel (e.g. `MISSING`) if using a dataclass with fixed fields.

Given you want “store what exists”, the cleanest representation is:
- `ParameterSnapshot` as ordered mapping to a `dict[str, Any]` entry, with keys present only when supported,
- plus `capabilities` saved explicitly.

Example entry payload:
```python
{
  "value": 0.25,
  "min": -1.0,
  "max": 1.0,
  "step": 0.01,
  "default_value": 0.0,
  "capabilities": ["default_value", "min", "max", "step"],
}
```

### 2) `ParameterSnapshot`
An immutable ordered mapping: `Symbol -> ParameterSnapshotEntry`

Public surface:
- `__getitem__(sym) -> entry`
- `items()`, `keys()`, `values()`, `__iter__`, `__len__`
- `values_only() -> dict[Symbol, Any]` (unordered ok)

### 3) `NumericExpression`
Callable object with:
- `core: Callable[..., Any]` — compiled numpified function (positional args)
- `parameters: tuple[Symbol, ...]` — parameter order
- one of the following “binding modes”:

#### Binding modes
1. **Live**: provider is `weakref(ParameterManager)`
2. **Snapshot-bound**: provider is `ParameterSnapshot` or its `.values_only()` dict
3. **Dict-bound**: provider is `dict[Symbol, Any]`
4. **Unbound**: provider is `None`, requiring explicit params

Suggested internal representation:
- `mode: Literal["live", "bound", "unbound"]`
- `provider: weakref | Mapping | None`

#### Call signatures
- Live / bound:
  - `__call__(x: np.ndarray) -> np.ndarray`
- Unbound:
  - `__call__(x: np.ndarray, *params: Any) -> np.ndarray`
  - where `params` order matches `self.parameters`

This is intentionally a *different signature*. That is acceptable and explicit.

#### Methods
- `bind(snapshot_or_dict) -> NumericExpression`
  - snapshot: use snapshot values; ignore extra keys; missing required -> `KeyError` with list of missing symbols
- `unbind() -> NumericExpression`
  - drops provider, returns unbound evaluator
- `core_unbound` (optional convenience)
  - returns raw `core` if you want direct function access

---

## Interaction With `numpify_cached`

### Compilation remains unchanged
- Compile once per `(expr, args)` via:
  - `core = numpify_cached(expr, args=[var] + parameters)`

### Binding does not affect caching
- `.bind` wraps the existing `core` and does not call `numpify_cached` again.
- `.unbind` returns another wrapper (or a thin object exposing `core`) without recompiling.

### Memory behavior
- `core` may be shared across plots if compilation arguments and expression match cache keys (this is existing behavior).
- `NumericExpression` objects are lightweight and can be created on plot update without heavy overhead.

---

## Error Handling Contract

### Snapshot
- Snapshot never raises due to missing optional metadata; it simply does not store that field and excludes it from `capabilities`.

### NumericExpression
- `bind(dict)`:
  - ignores extra keys
  - raises `KeyError` if any required symbols in `self.parameters` are missing
- live evaluation:
  - if parameter manager weakref is dead: raise `RuntimeError` with message indicating the evaluator is detached from a living figure/manager
- no value validation; underlying NumPy errors propagate

Error messages should include:
- plot id (if available),
- parameter symbols list (for missing keys),
- evaluator mode (“live/bound/unbound”) when relevant.

---

## Integration Points / Required Code Changes

### 1) `ParamRef.py`
- Extend `ParamRef` protocol to include:
  - `@property capabilities -> Sequence[str]`
  - (optional) `@property default_value/min/max/step` may remain optional and discovered via capabilities
- Change `ProxyParamRef.capabilities()` into a property:
  - `capabilities` returns list/tuple of supported optional keys based on widget attribute existence
- Update docs accordingly.

### 2) `SmartFigure.py` – ParameterManager
Add:
- `def snapshot(self) -> ParameterSnapshot`
  - iterates `self._refs.items()` in insertion order
  - for each `ref`, stores:
    - `"value": ref.value`
    - optional metadata fields if present in `ref.capabilities`
    - `"capabilities": list(ref.capabilities)`
- (Future) `def restore(self, snap: ParameterSnapshot) -> None`
  - not implemented in this milestone, but snapshot must be shaped to support it.

### 3) New module: `ParameterSnapshot.py` (recommended)
- `ParameterSnapshotEntry` (immutable record)
- `ParameterSnapshot` (ordered mapping + `values_only()`)

Alternative: define in `SmartFigure.py` for now, but module keeps responsibilities clearer and reduces file size.

### 4) New module: `NumericExpression.py` (recommended)
- `NumericExpression` callable object with:
  - mode/provider
  - bind/unbind
  - weakref handling

### 5) `SmartFigure.py` – SmartPlot
Add new public properties:
- `symbolic_expression` (returns stored sympy expr)
- `parameters` (tuple of symbols, deterministic order)
- `numeric_expression` (returns NumericExpression “live” evaluator)

Update `set_func(...)`:
- compile `core` via `numpify_cached` (as today)
- build/store `NumericExpression` live evaluator with weakref to `fig.params`
- store `_func`, `_parameters`, `_var` as today

Update `render()`:
- replace manual arg-building with:
  - `y_values = np.asarray(self.numeric_expression(x_values))`

### 6) Deprecation notes (internal)
- Keep `_f_numpy` as internal detail if needed (e.g. debugging), but prefer routing evaluation through `numeric_expression` to eliminate duplicated logic.

---

## Usage Examples (Target)

### Info card: sup norm estimate
```python
plot = fig.plots["f_0"]
x = np.linspace(-5, 5, 2000)

# live evaluation (reads current figure parameters)
y = plot.numeric_expression(x)
sup = np.max(np.abs(y))
```

### Cross-card consistent snapshot
```python
snap = fig.params.snapshot()

f = fig.plots["f_0"].numeric_expression.bind(snap)
g = fig.plots["f_1"].numeric_expression.bind(snap)

x = np.linspace(-5, 5, 2000)
dist = np.max(np.abs(f(x) - g(x)))
```

### Explicit evaluation (unbound)
```python
core = fig.plots["f_0"].numeric_expression.unbind()
# parameters in plot.parameters order:
y = core(x, a_value, b_value)
```

---

## Implementation Plan (Stages)

### Stage 0: Preparatory refactors (low risk)
1. Add `capabilities` property to `ProxyParamRef` (keep old method temporarily if desired).
2. Update internal call sites (none today except docs) to use property.

### Stage 1: Snapshot
1. Implement `ParameterSnapshot` (+ entry type).
2. Implement `ParameterManager.snapshot()` returning ordered snapshot.
3. Add `values_only()` convenience.

Deliverable: `fig.params.snapshot()` works and is stable.

### Stage 2: NumericExpression (core)
1. Implement `NumericExpression` with:
   - live mode (weakref to ParameterManager),
   - bind(snapshot/dict),
   - unbind(),
   - missing-key handling.
2. Add to `SmartPlot.set_func()` and store as internal `_numeric_expression` or similar.
3. Add `SmartPlot.numeric_expression` property.

Deliverable: external code can evaluate `plot.numeric_expression(x)`.

### Stage 3: Render rewrite
1. Change `SmartPlot.render()` to call `numeric_expression(x_values)` and remove manual param substitution.
2. Keep viewport/sampling logic unchanged.

Deliverable: no behavior change in plots, reduced duplication.

### Stage 4: Public surface polishing
1. Add `SmartPlot.symbolic_expression` and `SmartPlot.parameters` properties.
2. Ensure docstrings reflect immutability and signatures.

---

## Test Plan

### Unit tests (fast)
1. **Snapshot ordering**
   - create parameters in order `a`, `b`, `c`
   - snapshot keys preserve that order
2. **Snapshot “store what exists”**
   - with `SmartFloatSlider`, verify optional keys exist and are captured
   - with a dummy control lacking `step`, verify snapshot omits it and capabilities excludes it
3. **NumericExpression missing keys**
   - `bind({a:1})` when parameters are `(a,b)` raises with missing `b`
4. **Extra keys ignored**
   - `bind({a:1,b:2,extra:99})` does not error
5. **Weakref dead**
   - create live evaluator, delete manager (or simulate), ensure evaluation raises clear error

### Integration tests (notebook-level)
1. Compare old vs new render path:
   - same expression, same parameter values, verify identical `y` arrays.
2. Info card sample:
   - compute sup norm in a hook; ensure updates reflect slider changes.

---

## Open Questions (explicitly deferred)
- Snapshot serialization format (JSON-friendly encoding of SymPy symbols).
- `ParameterManager.restore(snapshot)` semantics for non-slider controls.
- Whether to expose `NumericExpression.core` (raw callable) as public API.

