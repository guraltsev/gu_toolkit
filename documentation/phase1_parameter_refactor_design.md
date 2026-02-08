# Refactoring parameter management (SmartSlider-only, no behavior regressions)

This design revises Phase 1 so that the public API becomes `parameter()` (not `add_param()`), and parameter management is refactored around **control widgets** that provide **ParamRef** objects.

---

## Scope and goals

### Goals
- Replace the “slider-per-symbol” API (`add_param`) with **`parameter()`**, while keeping behavior unchanged:
  - Parameters are auto-detected in `SmartFigure.plot()` and created automatically.
  - Parameter changes trigger rerender.
  - Existing parameter-change hooks still run.
- Make parameter management **control-widget-based**, where a **single widget** may bind **one or multiple symbols** (multi-symbol controls are for later, but the refactor supports them structurally now).

### Non-goals
- No 2D pad implementation in Phase 1.
- No UI redesign of `SmartFloatSlider` beyond minimal additions needed for binding/proxying.

---

## Baseline (current behavior to preserve)

- `ParameterManager` stores a map of symbols to slider widgets, creates sliders in `add_param`, and triggers renders on `.value` changes.
- `SmartFigure.plot()` auto-detects parameters from `func.free_symbols` (excluding the x-variable) and ensures a slider exists for each.
- `SmartPlot.render()` pulls numeric values via `fig.params.get_value(p)`.

These behaviors remain the contract to preserve.

---

## Target architecture (control widgets + ParamRef)

### Key design change
Parameter management becomes **control-widget-based**:

- A **control** is an `ipywidgets.Widget` instance that can represent **one or more parameters**.
- The control is “wired” when registered with a figure:
  1. It is inserted into the figure’s parameter sidebar container.
  2. Its change events are subscribed so updates trigger rerender.
  3. It is bound to specific SymPy symbols and exposes **ParamRef** objects.

The figure/plot layer stays symbol-driven: it asks for values by symbol (`get_value(symbol)`), and ensures parameters exist (`parameter(...)` called during plot creation).

---

## Public API (replaces `add_param`)

### SmartFigure
Add:
- `SmartFigure.parameter(parameters, *, control=None)`
  - `parameters`: `sympy.Symbol | Sequence[sympy.Symbol]`
  - `control`: widget instance, default `None`.

Keep (compatibility only; not the preferred API):
- `SmartFigure.add_param(symbol, **kwargs)` remains as an alias/shim that calls
  `parameter(symbol, control=SmartFloatSlider(...))` using the same defaults and
  overrides as today. Mark as deprecated in docs.

### Module-level convenience
Add a global `parameter(...)` function analogous to existing global `plot(...)`:
- Uses the current figure context (`with SmartFigure(): ...`) like `plot` does today.

---

## ParamRef specification

### Purpose
A `ParamRef` is the symbol-level handle returned by `parameter(...)` and stored in `fig.params[symbol]`.

### Required attributes / behavior
- `.parameter`: the bound SymPy `Symbol`.
- `.value` property:
  - getter reads the parameter’s current numeric value from the underlying control widget,
  - setter updates the underlying control widget.
- Convenience methods:
  - `.get()` → same as `.value`
  - `.set(value)` → sets `.value`
  - `.get_attr(name)` / `.set_attr(**kwargs)` for explicit proxying (optional but recommended)

### Proxy semantics
- `ParamRef.__getattr__(name)` forwards to the underlying control widget so existing code that does
  `fig.params[a].layout`, `fig.params[a].observe(...)`, etc. continues to work in practice.
- `ParamRef.widget` property returns the underlying control widget (important when an actual Widget
  instance is needed, e.g. inserting into a custom layout).

### Optional configuration surface
If the control supports it, `ParamRef` *also* exposes:
- `.min`, `.max`, `.step` (get/set)

Implementation rule: these are present only if the underlying widget supports them (either as
attributes/properties or via explicit methods). Otherwise they raise `AttributeError`.

---

## Control widget contract (minimal, widget-agnostic)

A control is an `ipywidgets.Widget` instance that must support:

### Binding
- `control.bind(parameters: Sequence[sympy.Symbol]) -> dict[sympy.Symbol, ParamRef]`

This is where the control “provides the ParamRef(s)”. In Phase 1:
- `SmartFloatSlider.bind([a])` binds one symbol and returns `{a: ParamRef(...)}`.

Binding is expected to also set helpful UI labeling (e.g. slider description) where appropriate.

### Change subscription
- `control.on_change(callback) -> unsubscribe`

This is the only standardized wiring hook the manager needs. It fires when *any* of the bound
parameter values change.

For `SmartFloatSlider`, implement by observing the widget’s traitlets `value`, returning an
unsubscribe closure.

### Values access
`ParameterManager` does not interpret control internals. It uses the returned `ParamRef`s for
symbol-level get/set.

---

## SmartFloatSlider minimal additions (Phase 1)

To satisfy the new contract without changing its UI:

Add:
1. `bind(parameters)`:
   - enforce single symbol in Phase 1 (`len(parameters) == 1`)
   - set the label/description to `$latex(symbol)$` (or string form if LaTeX not desired)
   - create and store:
     - `self.paramref` (single)
     - `self.paramrefs` dict (general form)
   - return the dict

2. `on_change(callback)`:
   - `self.observe(callback, names="value")`
   - return an unsubscribe closure

3. Optional passthrough properties on `SmartFloatSlider` so ParamRef can expose them cleanly:
   - `.min`, `.max`, `.step` proxy to the inner slider’s min/max/step

No other behavioral changes.

---

## ParameterManager refactor

### Internal data structures
Replace:
- `_sliders: Dict[Symbol, SmartFloatSlider]`

With:
- `_refs: Dict[Symbol, ParamRef]` (symbol → ParamRef)
- `_controls: List[ipywidgets.Widget]` (registered control widgets in display order)
- `_owner_control: Dict[Symbol, ipywidgets.Widget]` (symbol → owning control widget)
- `_layout_box`: unchanged (sidebar VBox)
- hooks registry: unchanged

### Core methods

#### `parameter(parameters, *, control=None)`
Canonical entry point used by `SmartFigure.parameter()` and by autodetection.

- Normalize `parameters` to a tuple of symbols.
- If `control is None`:
  - if exactly one symbol: create default `SmartFloatSlider(value=0.0, min=-1.0, max=1.0, step=0.01)`
    (and do **not** display or wire yet)
  - else: raise `ValueError` (Phase 1: no default multi-symbol control)
- Call `register_control(parameters, control)`
- Return:
  - a single `ParamRef` if caller passed a single symbol
  - a tuple of `ParamRef`s in the same order as `parameters` if caller passed a sequence

#### `register_control(parameters, control)`
- Call `refs = control.bind(parameters)` (control provides ParamRefs)
- Validate:
  - `set(refs.keys()) == set(parameters)`
  - no symbol already registered in `_refs` (Phase 1 simplest policy: raise on conflict)
- Store:
  - for each symbol: `_refs[sym] = refs[sym]` and `_owner_control[sym] = control`
- Append control to `_controls`
- Add control widget to sidebar container:
  - `_layout_box.children += (control,)`
- Subscribe to changes once per control:
  - `unsubscribe = control.on_change(self._on_control_change)`
  - store unsubscribe if you anticipate later removal

#### `get_value(symbol) -> float`
- If symbol exists: return `_refs[symbol].value`
- Else: return `0.0` (preserve existing missing-param fallback)

#### `set_value(symbol, value)`
- Delegate to `_refs[symbol].value = value` (or `_refs[symbol].set(value)`)

#### Dict-like interface
- `__getitem__(symbol) -> ParamRef`
- `__contains__`, `keys`, `items`, `values` return views over `_refs`

Compatibility helper (recommended):
- `widget(symbol) -> ipywidgets.Widget` returns `_refs[symbol].widget`

#### Backward-compat alias
- `add_param(symbol, **kwargs) -> SmartFloatSlider`:
  - construct a `SmartFloatSlider(...)` using the same kwargs semantics as today (value/min/max/step)
  - call `parameter(symbol, control=that_slider)`
  - return the created slider widget

This preserves existing notebooks while making `parameter()` the canonical logic.

### Change handling
Replace `_on_slider_change` with `_on_control_change(change)`:
- call `self._render_callback("param_change", change)`
- hooks remain run by `SmartFigure.render(...)` as they are today

---

## SmartFigure changes (localized)

### `SmartFigure.parameter(...)`
New method:
- delegates to `self._params.parameter(parameters, control=control)`
- updates sidebar visibility after registration (same logic as today)
- returns ParamRef or tuple of ParamRefs

### `SmartFigure.plot(...)`
Change parameter creation:
- Instead of `self._params.add_param(p)`, call `self.parameter(p)` for each autodetected symbol.

Everything else remains unchanged (rendering path still uses `fig.params.get_value(p)`).

### Keep `SmartFigure.add_param(...)` as compatibility shim
- implemented in terms of `SmartFigure.parameter(...)`
- returns the underlying slider widget (same return type as today)

---

## Validation plan (no regressions)

1. Autodetection unchanged:
   - `fig.plot(x, a*sp.sin(x))` creates parameter control and renders.
2. Slider drag updates plot; no warnings; hooks still run.
3. Existing hook code:
   - `fig.params[a].value` works (now via ParamRef).
   - `fig.params[a].layout`, `.observe`, etc. work (proxying).
4. Backward compatibility:
   - `fig.add_param(a, min=..., max=...)` still works and returns a `SmartFloatSlider`.
5. Rendering code path unchanged:
   - `SmartPlot.render()` still calls `fig.params.get_value(p)`.

---

## Deferred decisions

- Policy for symbol conflicts (raise vs replace vs merge).
- Control removal/unregistration (needs unsubscribe + sidebar widget removal).
- For multi-symbol controls: standardize the shape of the `change` payload passed to render/hooks.
