# Blueprint (Option A): Ref-First Parameter System with Required `ParamRef.observe`

Date: 2026-02-07

This blueprint defines a ref-first parameter system in which:

- The public parameter API returns `ParamRef` objects everywhere (not widgets).
- `ParamRef.observe(...)` is **required** and is the standard mechanism to route “parameter changed → callback”.
- The figure keeps a central render loop and a hook mechanism (**Option A**): parameter changes trigger `SmartFigure.render(reason="param_change", event=ParamEvent)`; hooks run after plot rendering.

Backwards compatibility is intentionally **out of scope**.

---

## 0. Definitions and guiding principles

### 0.1 Symbols, controls, refs
- **Symbol**: a `sympy.Symbol` used as a parameter (e.g. `a`, `b`).
- **Control**: a UI object that owns state and can drive one or more symbols (e.g. a slider, a 2D pad).
- **ParamRef**: the **symbol-level handle** returned by the parameter system. It exposes:
  - the symbol identity,
  - a `value` interface,
  - a required `observe(...)` that emits parameter-level events,
  - optional capability methods/properties (e.g. `min/max/step`) when meaningful.

The manager/figure/plots must depend on `ParamRef` (contract), not on widget internals.

### 0.2 Event normalization
All parameter-change callbacks consume a normalized event object (`ParamEvent`) rather than raw traitlets/ipywidgets change dicts.

---

## 1. Goals and non-goals

### 1.1 Goals
1. **Ref-first (dict-like) API**: `fig.params[sym]` returns a `ParamRef`. Iteration returns refs.
2. **Required `ParamRef.observe`**: every ref can register callbacks and guarantees they fire when the *effective parameter value* changes.
3. **Single render routing**: parameter changes route through the figure render loop:
   - `ParamRef.observe` → `ParameterManager` handler → `SmartFigure.render("param_change", ParamEvent)`
4. **Capability-based range configuration**: `min/max/step` exist only if supported; otherwise raise `AttributeError`.
5. **Single source of truth for values**: `ParamRef.value` is the authoritative value access path.

### 1.2 Non-goals (postponed)
- Multi-symbol controls and coordinate transforms (pad, polar) beyond interface accommodation.
- Control/widget removal and lifecycle management.
- Conflict/unregistration policies beyond “single owner per symbol”.

---

## 2. Public API

### 2.1 `SmartFigure`
#### `figure.parameter(...)`
Create/ensure parameters and return refs.

Proposed signatures:

```python
def parameter(self, symbols, *, control=None, **control_kwargs):
    # symbols: Symbol | Sequence[Symbol]
    # returns: ParamRef (single) or dict[Symbol, ParamRef] (multi)
```

- If `symbols` is a single symbol: return a `ParamRef`.
- If `symbols` is a sequence: return a `dict[Symbol, ParamRef]`.
- `control` is optional; if omitted, use the default control (slider) with default config.

#### `figure.params`
Expose a `ParameterManager` instance whose dict-like surface returns refs.

---

## 3. ParameterManager (ref-first)

### 3.1 Core storage
Primary state is refs, not widgets:

- `_refs: dict[Symbol, ParamRef]`
- Optional: `_controls` / `_widgets` registry for UI assembly and deduplication (future).

### 3.2 Required methods
```python
class ParameterManager(Mapping[Symbol, ParamRef]):
    def ensure(self, symbol: Symbol, *, control=None, **control_kwargs) -> ParamRef: ...
    def __getitem__(self, symbol: Symbol) -> ParamRef: ...
    def get(self, symbol: Symbol, default=None): ...
    def items(self): ...   # returns (Symbol, ParamRef)
    def values(self): ...  # returns ParamRef
    def keys(self): ...    # returns Symbol
```

### 3.3 UI enumeration (escape hatch)
Since refs are not widgets, provide a supported way to build UI:

```python
def widget(self, symbol: Symbol):
    return self._refs[symbol].widget

def widgets(self):
    """Return unique widgets/controls suitable for display (dedup in future)."""
```

`widgets()` matters once multiple symbols share one control.

---

## 4. Required contract: `ParamRef`

### 4.1 Required interface
```python
class ParamRef(Protocol):
    @property
    def parameter(self) -> Symbol: ...

    @property
    def widget(self) -> Any: ...  # ipywidgets.Widget or control UI root

    @property
    def value(self) -> Any: ...
    @value.setter
    def value(self, v: Any) -> None: ...

    def observe(self, callback: Callable[[ParamEvent], None], *, fire: bool = False):
        """Register callback for parameter-level value changes."""
        ...

    def reset(self) -> None:
        """Reset this parameter to its default value."""
        ...
```

### 4.2 `observe` semantics (required)
- `observe(callback)` registers `callback(event)` to fire when the **effective value** of this parameter changes.
- The ref is responsible for routing underlying control/widget events into `ParamEvent`.
- `fire=True` immediately calls `callback` once with a synthetic event reflecting the current value.

### 4.3 Range/config capability (optional)
Refs may expose:

- `min`, `max`, `step`
- `default` (optional) and `set_default(...)` (optional)

Rules:
- If supported, these get/set the relevant control range.
- If unsupported, raise `AttributeError`.

Avoid forcing these capabilities onto controls where they do not make sense.

---

## 5. Normalized event: `ParamEvent`

### 5.1 Required fields
```python
@dataclass(frozen=True)
class ParamEvent:
    parameter: Symbol
    old: Any
    new: Any
    ref: ParamRef
    raw: Any = None  # optional original event payload
```

- `raw` may contain a traitlets change dict, a custom drag event, etc.

---

## 6. Default implementation: Slider control + proxy ref

### 6.1 `ProxyParamRef` (default)
A concrete ref that proxies to a widget/control when direct proxying is correct (e.g. sliders).

Behavior:
- `value` delegates to `widget.value`.
- `observe` attaches to the underlying widget's change notifications and maps them into `ParamEvent`.
- `reset` calls `widget.reset()` (or sets `value` to stored default).

### 6.2 Make the default slider range-configurable at top level
If the default control is a composite wrapper (e.g. `SmartFloatSlider` wrapping an inner `FloatSlider`), expose at the wrapper level:

- `min`, `max`, `step` properties
- `reset()` method (public)

So that:
- `ref.min = -2` means “set control min”
- `ref.reset()` means “restore default”

The wrapper should preserve any existing clamp/sync behavior for limits.

---

## 7. Control → refs handshake (“bind” / “make_refs”)

This blueprint keeps a control-level handshake so controls can:
- define symbol mappings (especially for multi-symbol controls),
- return custom `ParamRef` implementations.

### 7.1 Control API
```python
class Control(Protocol):
    def make_refs(self, symbols: Sequence[Symbol]) -> dict[Symbol, ParamRef]:
        ...
```

- For a single slider control, `make_refs([a]) -> {a: ProxyParamRef(a, slider)}`.
- For a multi-symbol control, `make_refs([a, b])` can return distinct ref objects that map to a shared widget.

**Note:** Step 1 may implement this only for single-symbol controls.

---

## 8. Option A render routing and hooks (selected)

### 8.1 Single routing path
Parameter changes are routed centrally:

1. Manager ensures a ref exists for symbol.
2. Manager registers an internal observer:
   - `ref.observe(self._on_param_change)`
3. `_on_param_change(event)` calls the figure’s render callback:
   - `self._render_callback("param_change", event)`

### 8.2 `SmartFigure.render`
`render(reason, event)` does:
1. Render all plots using current ref values.
2. If `reason == "param_change"`, run hook callbacks:
   - `hook(event)` (event is `ParamEvent`)

Hook order:
- render plots first (so hooks can update derived UI state based on current plot state)
- then run hooks

### 8.3 Hook registration API
Maintain a figure-level hook API (Option A), but switch payload to `ParamEvent`:

```python
def add_hook(self, callback: Callable[[ParamEvent], None], *, run_now: bool = True) -> None:
    ...
```

If `run_now=True`, call once with a synthetic event (or call with `None` + documented behavior).
Prefer passing a synthetic `ParamEvent` with `old == new == current_value` for a chosen parameter, or define a separate “initialization event” type.

---

## 9. Plot evaluation changes (ref-based)

### 9.1 Replace manager value helpers
Remove `get_value(symbol)` and read directly from refs:

```python
val = fig.params[a].value
```

For bulk access, define:
- `fig.params.snapshot() -> dict[Symbol, Any]` (optional)

Plots should not rely on missing parameters defaulting to `0.0`. Missing symbols should raise `KeyError` to catch mistakes early.

---

## 10. Error handling and invariants

### 10.1 Invariants
- Every symbol in `_refs` maps to exactly one `ParamRef`.
- A `ParamRef` provides stable access to:
  - identity (`parameter`)
  - effective value (`value`)
  - change routing (`observe`)

### 10.2 Missing parameters
- `fig.params[sym]` raises `KeyError` if not ensured.
- `fig.parameter(sym)` ensures and returns the ref.

### 10.3 Re-entrancy policy
To avoid double renders:
- Only the manager should call the figure render callback for parameter changes.
- Users may attach additional observers via `ref.observe`, but they should not call `render` directly unless explicitly intended.
Optional: provide an internal flag to suppress nested renders if needed.

---

## 11. Step 1 implementation plan (concrete)

1. **Add `ParamEvent`** (new module, imported by refs and manager).
2. **Define `ParamRef` protocol** (new module). Decide whether to use `typing.Protocol` or an ABC.
3. **Implement `ProxyParamRef`** for the default slider control.
4. **Update default slider wrapper** to expose `min/max/step` and `reset()` at top level.
5. **Refactor `ParameterManager`**:
   - primary storage `_refs`
   - `ensure` creates a control (default slider) and calls `control.make_refs([sym])`
   - registers internal `ref.observe(self._on_param_change)`
6. **Update `SmartFigure.parameter(...)`** to call `params.ensure(...)`.
7. **Update plot rendering** to read from refs rather than `get_value`.
8. **Update hooks** (Option A):
   - hook payload is `ParamEvent`
   - hook invocation remains inside `SmartFigure.render` after plot renders.

---

## 12. Verification checklist

### 12.1 Core behavior
- `fig.parameter(a)` returns a `ParamRef`.
- `fig.params[a].value = 0.3` updates the control and triggers:
  - manager’s internal observer
  - `SmartFigure.render("param_change", ParamEvent)`
  - plots redraw
  - hooks fire after redraw

### 12.2 Observation API
- `fig.params[a].observe(cb)` fires `cb(ParamEvent(...))` on effective value changes.
- `fire=True` calls immediately once with a sensible initial event.

### 12.3 Capability behavior
- For slider refs: `min/max/step` settable and take effect.
- For non-range controls (future): access raises `AttributeError`.

### 12.4 Dict-like surface
- `fig.params.items()` yields `(Symbol, ParamRef)` pairs.
- `fig.params.values()` yields refs (not widgets).

---

## 13. Notes for future steps (not implemented now)

- Multi-symbol controls will return multiple refs that share a widget.
- `widgets()` will need to deduplicate shared widgets for display.
- `ParamRef.observe` in custom refs may observe multiple internal signals (e.g. x/y change) and emit one normalized `ParamEvent`.
