# Step 1 Refactor Plan — Introduce `ParamRef` (Proxy Semantics Only)

This document specifies the **proxy semantics** and a **minimal implementation plan** for introducing `ParamRef` so that:

- `fig.params[symbol]` returns a **ParamRef** (not a widget),
- reads and **writes** (attribute assignment) proxy to the underlying widget,
- `.value` is a required get/set property,
- `.min/.max/.step` are exposed when they make sense (and otherwise raise `AttributeError`),
- `SmartFloatSlider` can *provide* a `ParamRef` that the parameter manager stores and returns.

Everything else (multi-parameter controls, widget removal, unregistration, conflict policies beyond idempotency, etc.) is intentionally postponed.

---

## 1. `ParamRef` contract

### 1.1 Purpose
`ParamRef` is the **symbol-level handle** returned to user code when indexing the parameter manager:

```python
ref = fig.params[a]     # ref is ParamRef, not a Widget
```

It keeps a stable reference to:
- the SymPy parameter symbol, and
- the underlying widget that actually holds/changes the value.

### 1.2 Required attributes / properties

#### `parameter: sympy.Symbol`
- Read-only.
- The bound SymPy symbol.

#### `widget: ipywidgets.Widget`
- Read-only.
- The underlying widget instance (initially a `SmartFloatSlider`).

#### `value`
- Required property (get/set).
- Getter returns the current numeric value of the underlying widget.
- Setter updates the underlying widget’s value.

Contract: **setting `value` must behave exactly like writing the widget value directly**, so any existing observers on the widget fire normally.

### 1.3 Optional range configuration (`min`, `max`, `step`)
`ParamRef` exposes:
- `.min`, `.max`, `.step` **only if** the underlying widget supports them.

Rules:
- If the widget supports a field/property (e.g. `widget.min`), `ParamRef.min` proxies to it.
- If unsupported, `ParamRef.min` raises `AttributeError` (same for `max` and `step`).

### 1.4 Proxy semantics (reads + writes)

#### Read proxying (`__getattr__`)
If `name` is not found on `ParamRef`, `__getattr__` forwards to the underlying widget:

```python
ref.layout        # forwarded to ref.widget.layout
ref.observe(...)  # forwarded method call
```

#### Write proxying (`__setattr__`)
If `name` is not an internal ParamRef field, `__setattr__` forwards assignment to the widget:

```python
ref.layout = Layout(width="200px")  # forwarded to widget.layout
```

Special cases:
- `parameter` and `widget` are read-only; assignment raises `AttributeError`.
- `value/min/max/step` assignments route through their property setters so they can validate and raise cleanly.

### 1.5 Convenience (recommended, not required)
Provide small helpers:
- `get()` / `set(v)` as aliases for `.value`
- `get_attr(name)` / `set_attr(**kwargs)` explicit proxy helpers

---

## 2. Minimal implementation plan

### 2.1 Add `ParamRef` class

#### Location
Place `ParamRef` near `ParameterManager` (same module) for the first step, or in a small shared module imported by both slider and figure.

#### Storage and safety
- Use `__slots__` or a strict internal naming convention to prevent accidental shadowing.
- Suggested internal fields:
  - `_parameter`
  - `_widget`

#### Suggested skeleton
Key behaviors:
- read-only `parameter`, `widget`
- `value` property uses `widget.value`
- optional `min/max/step` via `hasattr(widget, ...)`
- proxy reads/writes via `__getattr__` and `__setattr__`

---

### 2.2 Make `SmartFloatSlider` “range-configurable” at top level

Today range configuration lives on the inner `FloatSlider` (e.g. `self.slider.min`). Expose it at the `SmartFloatSlider` level so `ParamRef` can proxy in a widget-agnostic way:

Add properties on `SmartFloatSlider`:

- `min` → get/set `self.slider.min`
- `max` → get/set `self.slider.max`
- `step` → get/set `self.slider.step`

This makes `ref.min/ref.max/ref.step` meaningful when `ref.widget` is a `SmartFloatSlider`.

---

### 2.3 Make `SmartFloatSlider` provide a `ParamRef` via `bind(...)`

Add a minimal binding method:

```python
def bind(self, parameters: Sequence[Symbol]) -> dict[Symbol, ParamRef]:
    assert len(parameters) == 1
    sym = parameters[0]
    ref = ParamRef(sym, self)
    self.paramref = ref             # optional: debugging handle
    return {sym: ref}
```

Notes:
- No multi-symbol binding in Step 1.
- No automatic relabeling policy is specified in Step 1 (keep existing description/label behavior unchanged).

---

### 2.4 Update `ParameterManager` to return `ParamRef` from `__getitem__`

This is the core behavior change: **abandon widget identity expectations**.

#### Data structures (minimal change)
Keep the existing slider storage (for sidebar display and backward compatibility of the manager internals):

- existing: `_sliders: Dict[Symbol, SmartFloatSlider]`
- add: `_refs: Dict[Symbol, ParamRef]`

#### `add_param` behavior (minimal changes)
When creating a new slider:
1. create the slider as today,
2. register `.observe(..., names="value")` as today,
3. append widget to sidebar as today,
4. call `slider.bind([symbol])` and store the returned ref in `_refs[symbol]`.

When the symbol already exists:
- keep idempotency (returning existing slider widget is fine internally),
- ensure a `ParamRef` exists in `_refs` for that symbol (create it lazily via `bind` once if needed).

#### Public manager interface
- `__getitem__(symbol)` now returns `_refs[symbol]` (ParamRef)
- `items()/values()/keys()` should reflect refs where appropriate
- `get_value(symbol)` should read `_refs[symbol].value`

#### Escape hatch (recommended)
Add:

```python
def widget(self, symbol) -> ipywidgets.Widget:
    return self._refs[symbol].widget
```

This avoids reintroducing widget identity at `__getitem__`, but keeps a supported path to retrieve a widget when necessary.

---

## 3. Verification checklist (proxy semantics only)

### 3.1 Read proxy works
- `fig.params[a].layout` returns the widget layout
- `fig.params[a].observe(cb, names="value")` attaches as expected

### 3.2 Write proxy works
- `fig.params[a].layout = Layout(width="200px")` updates the underlying widget
- `fig.params[a].value = 0.3` updates the slider and triggers the existing render callback path

### 3.3 Range configuration works when supported
After adding `min/max/step` passthrough properties on `SmartFloatSlider`:
- `fig.params[a].min = -2`
- `fig.params[a].max = 2`
- `fig.params[a].step = 0.05`

For widgets that do not support these:
- accessing or setting these raises `AttributeError` by contract.

### 3.4 No additional refactors
- Autodetection, hook mechanics, multi-symbol controls, and widget removal are untouched in Step 1.

---

## 4. Implementation notes / constraints

- The main compatibility break is intentional: `fig.params[a]` is no longer a widget and should not be inserted into widget containers directly. Use `fig.params.widget(a)` or `fig.params[a].widget` instead.
- `__setattr__` forwarding must be careful to not forward internal ParamRef fields. Use `__slots__` and/or a strict internal name whitelist.
