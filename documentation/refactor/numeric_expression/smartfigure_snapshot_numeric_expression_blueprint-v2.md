# Updated Blueprint: `ParameterSnapshot` + `NumericExpression` (SmartFigure)

## Goals

1. **Info cards (and other consumers)** can evaluate plotted functions numerically without manually substituting figure parameters.
2. Provide **snapshot semantics**:
   - `fig.params.snapshot()` produces a *dead* snapshot of parameter state (value + optional UI metadata).
   - Snapshots preserve **creation order** so they can later be used to recreate parameter UI/state.
3. Provide a **numerical-expression API** per plot:
   - Default is **live**, i.e. reads current parameter values from the figure on each call.
   - Can be **bound** to a snapshot or a `dict` of parameter values (dead/detached).
   - Can be **unbound** to require a later `.bind(...)` before evaluation (dead/detached).
4. Preserve `numpify_cached` compilation + caching:
   - compilation remains a single cached core callable;
   - binding must not trigger recompilation.

## Non-goals (this milestone)

- No validation of bound values (ranges/types).
- No snapshot serialization format (JSON encoding of `Symbol`, etc.).
- No `ParameterManager.restore(snapshot)` implementation beyond storing enough information.
- No attempt to solve or refactor figure/plot lifetime cycles; “live” is defined by being a proxy to an existing `SmartPlot`.

---

## Current State (summary)

### SmartPlot render path (today)
In `SmartPlot.render()`:
1. Compute `x_values`.
2. Build positional args: `[x_values] + [fig.params[p].value for p in self._parameters]`.
3. Call compiled function: `y = self._f_numpy(*args)`.

Compilation is performed in `SmartPlot.set_func(...)` via:
- `self._f_numpy = numpify_cached(expr, args=[var] + parameters)`

Problem: parameter-value collection is duplicated; info cards want the same logic without reimplementing it.

### ParameterManager (today)
`fig.params` is a `ParameterManager` holding:
- `_refs: Dict[Symbol, ParamRef]` in insertion/creation order,
- `parameter(...)` creates controls and registers observers,
- mapping interface,
- **no snapshot capability**.

### ParamRef / ProxyParamRef (today)
- `ParamRef` protocol exposes core behaviors: `parameter`, `widget`, `value`, `observe`, `reset`.
- `ProxyParamRef` provides optional metadata when widget supports it (`default_value`, `min`, `max`, `step`).
- `capabilities` currently exists as a method in some form; this blueprint standardizes it.

---

## Target API (final)

## 1) Snapshot API

### Live manager
```python
snap = fig.params.snapshot()  # -> ParameterSnapshot
```

### Snapshot object
- Behaves as an **immutable ordered mapping**:
  - keys: `sympy.Symbol`
  - values: `dict[str, Any]` “entry dict” (defined below)
- Order is the manager’s **creation/insertion order**.

### Snapshot entry dict shape (required)
Each entry is a `dict[str, Any]` with:

- required:
  - `"value"`: current value
  - `"capabilities"`: `list[str]` of optional metadata keys present
- optional keys present iff supported:
  - `"default_value"`, `"min"`, `"max"`, `"step"`

Rules:
- `"value"` is **always present** and is **not** listed in `"capabilities"`.
- Optional keys appear **only when available**; no sentinels.

Example entry:
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

### Convenience extraction
```python
values = snap.values_only()   # -> dict[Symbol, Any]
```
- `values_only()` returns `{sym: entry["value"]}`.
- The returned dict preserves snapshot order (standard `dict` insertion-order behavior).

---

## 2) Plot numerical-expression API

For `plot = fig.plots[id]`:

```python
plot.symbolic_expression     # -> sympy.Expr
plot.parameters              # -> tuple[Symbol, ...] (deterministic; matches numpify args)
plot.numeric_expression      # -> LiveNumericExpression (proxy)
```

### Core semantics
- `plot.numeric_expression` is **live**, defined as a proxy to `SmartPlot`:
  - `plot.numeric_expression(x)` evaluates with **current** figure parameter values.
- `bind(...)` creates a **dead/detached** evaluator:
  - it stores the compiled numeric core plus a concrete parameter-value tuple.
  - it is no longer linked to the figure.

### Preferred calling style (no `f(x, *params)`)
- **Never** use a call signature like `f(x, *params)`.
- Unbound evaluation is expressed as:
  - `(plot.numeric_expression.bind(values))(x)`.

---

## Data model

## 1) `ParameterSnapshot`

### Representation
An immutable mapping that preserves insertion order:
- internal: `dict[Symbol, dict[str, Any]]` populated in `_refs` iteration order.
- exposed: mapping interface (`__getitem__`, `__iter__`, `__len__`, `items()`, …).

### Requirements
- Immutable:
  - no mutation of stored entries is allowed via public API.
- Implement:
  - `values_only() -> dict[Symbol, Any]`
  - `__eq__` (ordered equality over items)
  - `__repr__` (compact, useful in debugging and tests)

## 2) `NumericExpression` objects

This blueprint uses **three concrete immutable callable-ish objects**, with no explicit “mode” field.

### A) `LiveNumericExpression`
- Purpose: proxy live evaluation to a `SmartPlot`.
- Stores: reference to a `SmartPlot`.
- Methods:
  - `__call__(x: np.ndarray) -> np.ndarray`
  - `bind(snapshot_or_dict) -> DeadBoundNumericExpression`
  - `unbind() -> DeadUnboundNumericExpression`

Error messages for live evaluation may include plot id (available from the plot).

### B) `DeadUnboundNumericExpression`
- Purpose: detached evaluator that requires `.bind(...)` before evaluation.
- Stores:
  - `core: Callable[..., Any]` (compiled function)
  - `parameters: tuple[Symbol, ...]`
- Methods:
  - `bind(snapshot_or_dict) -> DeadBoundNumericExpression`
  - `__call__(x)` raises `TypeError` indicating `.bind(...)` is required.

### C) `DeadBoundNumericExpression`
- Purpose: detached, callable evaluator with frozen parameter values.
- Stores:
  - `core`
  - `parameters`
  - `bound_values: tuple[Any, ...]` aligned with `parameters`
- Methods:
  - `__call__(x) -> np.ndarray` calling `core(x, *bound_values)`
  - optionally `unbind()` returning `DeadUnboundNumericExpression`
  - optionally `bind(...)` returning a new `DeadBound...` (convenience)

---

## Binding rules

`bind(source)` accepts:
- a `ParameterSnapshot`, or
- a `dict[Symbol, Any]`.

**Symbol keys only.**

Rules:
- Extra keys: **ignored**.
- Missing required keys (any symbol in `parameters`): raise `KeyError`.
  - The error message must include the list of missing symbols (and for live, may include plot id).
- No value validation.

---

## Capabilities API (ParamRef protocol)

### Requirement
`capabilities` is part of the `ParamRef` protocol and is a property:

```python
@property
def capabilities(self) -> Sequence[str]:
    ...
```

### Expected values
A sequence containing zero or more of:
- `"default_value"`, `"min"`, `"max"`, `"step"`

`ProxyParamRef.capabilities` computes these based on widget support.

---

## Interaction with `numpify_cached`

### Compilation
Unchanged:
- `core = numpify_cached(expr, args=[var] + parameters)`

### Binding and caching
- Binding/unbinding never calls `numpify_cached`.
- Dead evaluators reuse the existing `core`.

### Memory and sharing
- `core` may be shared across plots if cache keys match (existing behavior).
- Live/dead expression objects are lightweight.

---

## Integration points / required code changes

## 1) `ParamRef.py`
- Update `ParamRef` protocol to include `capabilities` property.
- Update `ProxyParamRef`:
  - `capabilities` becomes a property returning the list/tuple of supported optional keys.

## 2) `SmartFigure.py` – `ParameterManager`
Add:
```python
def snapshot(self) -> ParameterSnapshot:
    ...
```

Behavior:
- Iterate `self._refs.items()` in insertion order.
- For each `(sym, ref)`:
  - `entry = {"value": ref.value}`
  - `caps = list(ref.capabilities)`
  - `entry["capabilities"] = caps`
  - for each `name in caps`: `entry[name] = getattr(ref, name)`
- Return an immutable `ParameterSnapshot` wrapping the ordered mapping.

## 3) New module: `ParameterSnapshot.py` (recommended)
- `ParameterSnapshot` implementation (immutable ordered mapping)
- `values_only`, `__eq__`, `__repr__`

Implementation note:
- Since values are entry dicts, enforce immutability by:
  - storing internal dict privately, and
  - returning shallow copies of entry dicts (or `MappingProxyType`) from `__getitem__`.

## 4) New module: `NumericExpression.py` (recommended)
Implement:
- `LiveNumericExpression`
- `DeadUnboundNumericExpression`
- `DeadBoundNumericExpression`

## 5) `SmartPlot` changes

### Public properties
- `symbolic_expression` -> the stored sympy expr
- `parameters` -> tuple[Symbol, ...] used for compilation arg order
- `numeric_expression` -> returns a new `LiveNumericExpression(self)` (cheap)

### Internal evaluation authority
Add a single internal method that is the one true place where parameter values are collected:

```python
def _eval_numeric_live(self, x: np.ndarray) -> np.ndarray:
    # builds values in self._parameters order from self._smart_figure.params
    # calls self._core
```

### `set_func(...)`
- Continue compiling `self._core` via `numpify_cached`.
- Store `self._parameters` deterministically.
- Do not store any bound evaluators here.

### `render()`
Replace manual arg-building with:
```python
y_values = np.asarray(self.numeric_expression(x_values))
```

---

## Error handling contract

### Snapshot
- Snapshot never raises due to missing optional metadata.
- Snapshot must always include `"value"` and `"capabilities"`.

### NumericExpression
- Live:
  - normal numpy errors propagate.
  - errors may include plot id in message.
- Dead:
  - no plot id.
- Bind:
  - ignores extra keys.
  - raises `KeyError` on missing required symbols.
- Dead unbound:
  - calling raises `TypeError` directing user to `.bind(...)`.

---

## Usage examples

### Live evaluation (info card)
```python
plot = fig.plots["f_0"]
x = np.linspace(-5, 5, 2000)
y = plot.numeric_expression(x)
sup = np.max(np.abs(y))
```

### Cross-card consistent snapshot binding
```python
snap = fig.params.snapshot()

f = fig.plots["f_0"].numeric_expression.bind(snap)
g = fig.plots["f_1"].numeric_expression.bind(snap)

x = np.linspace(-5, 5, 2000)
dist = np.max(np.abs(f(x) - g(x)))
```

### Explicit parameter dict binding (Symbol keys only; extras ignored)
```python
vals = {a: 1.0, b: 2.0, extra: 99.0}
y = (fig.plots["f_0"].numeric_expression.bind(vals))(x)
```

### Unbound then bind (detached flow)
```python
unbound = fig.plots["f_0"].numeric_expression.unbind()
bound = unbound.bind({a: 1.0, b: 2.0})
y = bound(x)
```

---

## Implementation plan (stages)

### Stage 0: Capabilities property (low risk)
1. Add `capabilities` property to `ParamRef` protocol.
2. Implement `ProxyParamRef.capabilities` property.

### Stage 1: Snapshot
1. Implement `ParameterSnapshot` as immutable ordered mapping.
2. Implement `ParameterManager.snapshot()`.
3. Implement `values_only()`, `__eq__`, `__repr__`.

Deliverable: `fig.params.snapshot()` is stable and ordered.

### Stage 2: NumericExpression (live proxy + dead evaluators)
1. Implement the three NumericExpression objects.
2. Add `SmartPlot._eval_numeric_live(x)` and `SmartPlot.numeric_expression`.

Deliverable: external code can evaluate `plot.numeric_expression(x)` and can create detached bound evaluators.

### Stage 3: Render rewrite
1. Change `SmartPlot.render()` to use `numeric_expression(x_values)`.

Deliverable: identical plot behavior, no duplicated parameter collection logic.

### Stage 4: Public surface polishing
1. Add/confirm `symbolic_expression` and `parameters` properties.
2. Ensure docstrings reflect:
   - Symbol-key binding
   - extra-key ignore
   - `.bind(...)(x)` calling style
   - live vs dead semantics

---

## Test plan

### Unit tests
1. **Snapshot ordering**
   - Create parameters in order `a, b, c`.
   - Assert `list(snap.keys()) == [a, b, c]`.
2. **Snapshot “store what exists”**
   - For a slider-like ref, confirm optional keys exist and appear in `capabilities`.
   - For a ref lacking e.g. `step`, confirm `"step"` absent from entry and from `capabilities`.
3. **Snapshot immutability**
   - Mutating returned entry dict does not change stored snapshot (i.e., snapshot returns copies / proxy).
4. **Bind missing keys**
   - For parameters `(a,b)`, `bind({a:1})` raises `KeyError` mentioning `b`.
5. **Bind ignores extras**
   - `bind({a:1,b:2,extra:99})` succeeds.
6. **Dead unbound call errors**
   - Calling unbound dead evaluator raises `TypeError` instructing `.bind(...)`.

### Integration tests
1. **Old vs new render path equivalence**
   - Compare y arrays for multiple expressions and parameter values.
2. **Info card live updates**
   - Slider changes affect `plot.numeric_expression(x)` results.
3. **Snapshot consistency**
   - `snap = fig.params.snapshot()` then `bind(snap)` yields identical evaluation across multiple plots.

---

## Open questions (deferred)

- Snapshot serialization (Symbol encoding).
- `ParameterManager.restore(snapshot)` UI semantics for non-slider controls.
- Whether to expose raw `core` callable publicly (currently internal).
