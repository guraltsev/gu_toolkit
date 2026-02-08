# Refactoring parameter management (SmartSlider-only, no behavior regressions)

## Scope and goals

### Goals
- Refactor parameter management so the system can support multi-symbol controls later (e.g., a 2D draggable pad), while **keeping current SmartSlider behavior unchanged**:
  - `SmartFigure.plot()` auto-detects parameters and creates sliders.
  - `SmartFigure.add_param()` gets renamed to `parameter()` creates a slider with defaults/overrides (leave old function and add deprecation in the documentation)
  - Slider updates trigger rerenders.
  - Existing hooks registered via `add_param_change_hook()` still run.
- Adopt **Option A**: `fig.params[symbol]` returns a **ParamRef** object (symbol view), while maintaining practical compatibility by forwarding attribute access to the underlying widget.

### Non-goals
- No multi-symbol controls in this document.
- No UI changes to `SmartFloatSlider` beyond what is required to adapt it (ideally none).
- No change to the mathematical evaluation pathway (`SmartPlot.render()` using `fig.params.get_value(p)`).

---

## Baseline (what exists today)

### ParameterManager responsibilities
- Stores sliders in `self._sliders: Dict[Symbol, SmartFloatSlider]`.
- Creates sliders in `add_param(symbol, config, **kwargs)`.
- Calls `self._render_callback("param_change", change)` when a slider’s `.value` changes.
- Exposes dict-like access: `fig.params[sym]` returns the `SmartFloatSlider`.

### SmartFigure/SmartPlot dependencies
- `SmartFigure.plot()` infers parameters from `func.free_symbols` (excluding the x-variable) and calls `self._params.add_param(p)`.
- `SmartPlot.render()` evaluates numeric functions using `fig.params.get_value(p)`.

These behaviors are the contract to preserve.

---

## Target architecture (SmartSlider-only implementation)

### Key design decision
Parameter management becomes **control-based**, but in this refactor we implement only one control type: **single-symbol slider control**.

A **control**:
- owns one or more symbols,
- can report current values as a dictionary `{symbol: value}`,
- provides a displayable widget,
- emits a generic “changed” event.

The figure/plot layer remains agnostic: it asks for values by symbol (`get_value`) and ensures parameters exist (`ensure_param`).

---

## Control interface (internal contract)

Define a minimal internal interface (formal `Protocol` optional) that ParameterManager uses:

**Required**
- `symbols: tuple[sympy.Symbol, ...]`
- `widget: ipywidgets.Widget`
- `values() -> dict[sympy.Symbol, float]`
- `get_value(symbol) -> float`
- `set_value(symbol, value) -> None`
- `on_change(callback) -> unsubscribe`

**Optional (forward-only; manager does not interpret)**
- `configure(symbol, *, min=None, max=None, step=None, value=None) -> None`

In this document, only a slider control exists, so all of the above map directly onto `SmartFloatSlider`.

---

## Public API and compatibility

### SmartFigure
No breaking changes required.
- Keep `SmartFigure.add_param(symbol, ...) -> SmartFloatSlider` returning the slider widget as it does today.
- `SmartFigure.plot(...)` continues to auto-create sliders via parameter autodetection.

Additive API (recommended; not required for SmartSlider-only usage)
- `SmartFigure.add_control(control)` to register a multi-symbol control later.
  - In this document it can exist and be used only internally or be present as a public additive method.

### `fig.params[symbol]` (Option A)
Change `ParameterManager.__getitem__` to return `ParamRef(symbol, manager)` instead of the raw slider.

**Compatibility requirement**
`ParamRef` must forward unknown attributes to the underlying widget so existing code that treated `fig.params[a]` as a widget continues to work in practice (hooks, styling, etc.).

---

## Detailed design

## 1) New class: `ParamRef`

### Purpose
A small proxy for one symbol, returned by `fig.params[symbol]`.

### Required behavior
- `ParamRef.value`:
  - getter: `manager.get_value(symbol)`
  - setter: `manager.set_value(symbol, value)` (forwarded to owning control)
- `ParamRef.widget`:
  - returns the owning control’s widget (for sliders, the `SmartFloatSlider` instance)
- `ParamRef.configure(...)`:
  - forwards configuration updates to the manager (which forwards to the control)
- `ParamRef.__getattr__(name)`:
  - forwards to `.widget` to preserve widget-compatibility behavior

### Non-behavioral constraints
- `ParamRef` must not cache values; it should always reflect the current manager/control state.

---

## 2) ParameterManager refactor

### Internal data structures
Replace `_sliders: Dict[Symbol, SmartFloatSlider]` with control ownership maps:

- `_owner: Dict[Symbol, ParamControl]`
  - symbol → owning control
- `_controls: List[ParamControl]`
  - registered controls in display order
- `_layout_box: ipywidgets.Box`
  - the sidebar container for parameter widgets (already exists in the current layout)
- Hook registry remains unchanged.

### Core methods

#### `register_control(control)`
- For each `sym in control.symbols`:
  - if already in `_owner`, raise (simplest policy for refactor; replacement can be added later)
  - set `_owner[sym] = control`
- Append `control` to `_controls`.
- Append `control.widget` to the sidebar container children (preserve insertion order).
- Subscribe to changes once:
  - `unsubscribe = control.on_change(self._on_control_change)`
  - store `unsubscribe` if you anticipate future removal (optional).

#### `ensure_param(symbol, config=None, **kwargs)`
- If `symbol` already in `_owner`, no-op.
- Else construct a single-symbol slider control (see below) and `register_control(...)`.

This replaces the “create a slider per symbol” logic but is behavior-identical for SmartSlider-only usage.

#### `add_param(symbol, config=None, **kwargs) -> SmartFloatSlider` (public, backward-compatible)
- Call `ensure_param(...)`.
- Return the underlying slider widget:
  - `return self[symbol].widget` (via `ParamRef`).

#### `get_value(symbol) -> float`
- If owned: `return _owner[symbol].get_value(symbol)`
- Else: return `0.0` (preserve current “missing param → 0.0” fallback)

#### `set_value(symbol, value) -> None`
- If not owned: raise `KeyError` (or ensure first; preserve existing semantics as desired)
- Else: `_owner[symbol].set_value(symbol, value)`

#### `configure(symbol, **kwargs)`
- Forward to control’s `configure(...)` if supported.
- If not supported, either:
  - raise `NotImplementedError`, or
  - no-op (but for sliders it will be supported).

#### `__getitem__(symbol) -> ParamRef`
- Return `ParamRef(symbol, self)`.

#### Iteration / dict-like API
- `keys()` returns `_owner.keys()`.
- `items()` yields `(sym, ParamRef(sym, self))`.
- Consider adding `widgets()` to yield `(sym, widget)` for convenience, rather than overloading `values()`.

---

## 3) Slider control adapter (`SmartSliderControl`)

Implement an internal adapter that wraps a `SmartFloatSlider` and conforms to the control interface.

### Construction
Inputs:
- `symbol: sympy.Symbol`
- `ParamConfig` + current kwargs merging logic (same as current code)

Outputs:
- `widget`: constructed `SmartFloatSlider`

### Interface mapping
- `symbols = (symbol,)`
- `widget = slider`
- `values() -> {symbol: float(slider.value)}`
- `get_value(symbol)` returns `slider.value` (KeyError if mismatch)
- `set_value(symbol, value)` sets `slider.value` after clamping to `[slider.min, slider.max]` (matching current behavior)
- `configure(symbol, min/max/step/value)` updates slider fields and clamps slider.value as needed

### Change subscription
- `on_change(cb)` implemented via `slider.observe(cb, names="value")`.
  - Return an unsubscribe closure for symmetry (optional but recommended).

No changes to `SmartFloatSlider` are required.

---

## 4) SmartFigure changes (localized)

### `SmartFigure.plot(...)`
- Replace direct slider creation calls with:
  - `self._params.ensure_param(p)` for each detected parameter symbol.
- Keep sidebar visibility logic unchanged.

### `SmartFigure.add_param(...)`
- Keep returning `SmartFloatSlider`:
  - call `self._params.add_param(...)` (which ensures the symbol exists)
  - return the slider widget

No changes to `SmartPlot.render()` are required.

---

## Validation plan (no regressions)

### Manual checks in Jupyter
1. Autodetection: `fig.plot(x, a*sp.sin(x))` creates one slider and renders.
2. Slider drag updates plot; no console warnings.
3. Text edits in slider numeric fields still work; plot updates.
4. Hooks:
   - `add_param_change_hook` runs on slider change.
   - Code that uses `fig.params[a].value` still works.
   - Code that accesses widget attributes via `fig.params[a].layout`, `.observe`, etc. still works (forwarding).
5. `SmartFigure.add_param` still returns a `SmartFloatSlider` instance.
6. `fig.params.get_value(a)` returns current slider value.

### Structural checks
- Sidebar remains hidden if no parameters/info exist.

---

## Deferred decisions
- Conflict policy if a symbol is already owned when registering a control (raise vs replace).
- Optional removal/unregistration of controls (requires unsubscribing and removing widgets from layout).
