# Design Document: Ref-First Parameter System (Option A) with Idempotent `parameter(...)` and Required `ParamRef.observe`

Date: 2026-02-07

## Scope
This document merges the “ORIGINAL” blueprint and the “UPDATE” plan into a single specification for the ref-first parameter system:

- Public API returns **`ParamRef` everywhere** (not widgets).
- **`ParamRef.observe(...)` is required** and is the standard mechanism to route parameter changes.
- **`SmartFigure.parameter(...)` is the only entrypoint** for creating/configuring parameters (remove `ensure(...)` entirely).
- Parameter changes route through **one render path**: `ParamRef.observe → ParameterManager → SmartFigure.render("param_change", event)`.
- Reset semantics are **value-only**; documentation and UI wording must match.

Backwards compatibility is out of scope.

---

## 0. Definitions and principles

### 0.1 Terms
- **Symbol**: a `sympy.Symbol` used as a parameter (e.g. `a`, `b`).
- **Control**: a UI object that owns state and can drive one or more symbols (e.g. slider, 2D pad).
- **ParamRef**: the symbol-level handle returned by the parameter system. It exposes:
  - symbol identity,
  - `value` get/set,
  - required `observe(...)` producing normalized events,
  - optional capability properties (e.g. `min/max/step`) only when meaningful.

### 0.2 Single entrypoint
- **All creation/configuration flows must go through `parameter(...)`.**
- Plot inference must not create parameters via a “backdoor” API.

### 0.3 Event normalization
- All parameter callbacks receive a normalized `ParamEvent`, not raw widget/traitlets payloads.

---

## 1. Public API

### 1.1 `SmartFigure.parameter(...)`
Creates/configures parameters and returns refs.

```python
def parameter(self, symbols, *, control=None, **control_kwargs):
    '''
    symbols: Symbol | Sequence[Symbol]
    returns: ParamRef (scalar) or dict[Symbol, ParamRef] (sequence)
    '''
```

Behavior:
- Scalar input returns a single `ParamRef`.
- Sequence input returns `dict[Symbol, ParamRef]`.
- The call is **idempotent**:
  - if parameter(s) exist, it still applies provided configuration kwargs.
  - if missing, it creates them and applies provided configuration kwargs.

### 1.2 `SmartFigure.params`
Exposes a `ParameterManager` with a dict-like surface:
- `fig.params[sym] -> ParamRef`
- iteration/`values()` yields refs (not widgets)

### 1.3 UI escape hatch
Because refs are not widgets, provide:
- `ParameterManager.widget(symbol) -> Any` (root UI/control for that symbol’s ref)
- `ParameterManager.widgets() -> list[Any]` (controls suitable for display; dedup is a later concern, but repeated `parameter(...)` calls must not add duplicates for existing params)

---

## 2. Required contract: `ParamRef`

### 2.1 Required interface
```python
class ParamRef(Protocol):
    @property
    def parameter(self) -> Symbol: ...

    @property
    def widget(self) -> Any: ...

    @property
    def value(self) -> Any: ...
    @value.setter
    def value(self, v: Any) -> None: ...

    def observe(
        self,
        callback: Callable[[ParamEvent], None],
        *,
        fire: bool = False
    ) -> None:
        '''Register callback for parameter-level value changes.'''

    def reset(self) -> None:
        '''Reset value only (not range/config).'''
```

### 2.2 `observe` semantics (required)
- `observe(callback)` registers `callback(event)` to fire when the **effective value** changes.
- The ref maps underlying widget/control events into a `ParamEvent`.
- `fire=True` calls `callback` once with a synthetic event reflecting the current value.

### 2.3 Optional capabilities
Refs may expose `min`, `max`, `step` (and optionally `default`/`set_default(...)` if supported).
- If supported: get/set the relevant control configuration.
- If unsupported: raise `AttributeError`.

---

## 3. Normalized event: `ParamEvent`

```python
@dataclass(frozen=True)
class ParamEvent:
    parameter: Symbol
    old: Any
    new: Any
    ref: ParamRef
    raw: Any = None
```

Notes:
- `raw` may contain a traitlets change dict or a custom control event payload.
- Do **not** add old==new suppression at this stage.

---

## 4. Default implementation: slider + proxy ref

### 4.1 `ProxyParamRef` (default)
A concrete ref proxying to a slider-like control:
- `value` delegates to `widget.value`
- `observe` attaches to widget notifications and emits `ParamEvent`
- `reset` sets value back to the control’s stored default value (value-only)

### 4.2 Slider wrapper requirements
If you have a wrapper (e.g. `SmartFloatSlider`) around an inner widget, the wrapper must expose at top-level:
- `min`, `max`, `step` (if supported)
- `value`
- `reset()` (value-only)
- **a way to update the stored reset value** used by `reset()` (see §5.6)

---

## 5. ParameterManager (single source of truth)

### 5.1 State
Minimum required:
- `_refs: dict[Symbol, ParamRef]`
- `_controls: list[Any]` or similar registry (for display and to avoid duplicates on repeated calls)
- `_render_callback: Callable[[str, ParamEvent], None]` (provided by figure)

### 5.2 Remove `ensure(...)`
`ParameterManager.ensure(...)` must not exist. All internal callers must migrate.

### 5.3 Implement `ParameterManager.parameter(...)`
Single method implementing creation + configuration + wiring:

```python
def parameter(self, symbols, *, control=None, **control_kwargs):
    '''Create/configure parameter(s) and return ParamRef(s).'''
```

#### 5.3.1 Normalize input / return shape
- Convert `symbols` to list `syms`.
- Remember whether scalar vs sequence was requested (to return `ParamRef` vs dict).

#### 5.3.2 Partition existing vs missing
- `existing = [s for s in syms if s in _refs]`
- `missing  = [s for s in syms if s not in _refs]`

#### 5.3.3 Create refs for missing symbols

**Case A: `control is None` (default slider-per-symbol)**  
For each `s in missing`:
1. Create a default slider control (e.g. `SmartFloatSlider`) using default configuration.
2. Call `refs = slider.make_refs([s])`.
3. Store `_refs[s] = refs[s]`.
4. Wire render routing: `_refs[s].observe(self._on_param_change)`.
5. Register the control for display exactly once.

**Case B: `control is not None` (explicit control instance)**  
1. Call `new_refs = control.make_refs(missing)` **exactly once**.
2. For each `s in missing`:
   - store `_refs[s] = new_refs[s]`,
   - wire `_refs[s].observe(self._on_param_change)`.
3. Register the `control` for display exactly once.

This enforces the multi-symbol handshake and prevents the “loop per symbol passing the same control repeatedly” bug.

#### 5.3.4 Control swapping policy (deferred lifecycle management)
If `control is not None` and `existing` is non-empty:
- If every existing symbol is already bound to the **same control instance** being passed, allow.
- Otherwise raise `ValueError` (no silent rebinding; removal/lifecycle is deferred).

(Implement “bound to same control” using a reliable identity check; the ref must expose enough to perform this check, e.g. `ref.widget` identity or a `ref.control` attribute if you have one.)

#### 5.3.5 Apply configuration kwargs to *all requested refs* (existing + missing)
This is required idempotence behavior.

Rules:
- Apply only explicitly provided kwargs.
- Apply through the ref surface (capabilities). Unsupported attributes raise `AttributeError`.
- Recommended order:
  1) range/config (`min/max/step`)
  2) `value` last

#### 5.3.6 Value-only reset semantics and default reset value update
Reset is value-only; documentation must match.

Additionally, when `value=` is provided via `parameter(...)`, update the control’s stored “reset value” so that:

- `parameter(a, value=v)` sets the current value to `v`, and
- subsequent `reset()` returns to that `v`.

Mechanism:
- Provide a control method such as `set_default_value(v)` (or an equivalent ref-level hook).
- In `ParameterManager.parameter(...)`, when `value` is present:
  - set `ref.value = value`
  - update the control’s stored default reset value accordingly (for slider controls)

---

## 6. Render routing and hooks (Option A)

### 6.1 Single routing path for parameter changes
- The manager wires an internal observer on every ref:
  - `ref.observe(self._on_param_change)`
- `_on_param_change(event)` calls:
  - `self._render_callback("param_change", event)`

Only the manager should be responsible for “param change → render”.

### 6.2 `SmartFigure.render(reason, event)`
On `reason == "param_change"`:
1. Render all plots using current ref values.
2. Run hooks after plots are rendered.

### 6.3 Hook registration and `run_now`
Adopt explicit initialization semantics (avoid “fake param-change events” and avoid undocumented `None`):
- Define an `InitEvent` (or `HookEvent` union) for hook calls at registration time.

Example:
```python
@dataclass(frozen=True)
class InitEvent:
    snapshot: dict[Symbol, Any]  # optional but recommended
```

Hook signature accepts `ParamEvent | InitEvent`.
- `add_hook(cb, run_now=True)`:
  - registers `cb` for future param-change events
  - if `run_now`, calls `cb(InitEvent(snapshot=...))` once immediately

---

## 7. Plot evaluation and inference

### 7.1 Plot evaluation is ref-based
- Replace any `get_value(symbol)` usage with `fig.params[sym].value`.
- Missing parameters should raise `KeyError` (no silent defaulting).

### 7.2 Plot inference must route through `parameter(...)`
Any auto-detection of symbols inside `SmartFigure.plot(...)` must call:
- `self.parameter(detected_symbols)`
and must not reintroduce an internal “ensure-like” creation path.

---

## 8. Error handling and invariants

### 8.1 Invariants
- `_refs` maps each symbol to exactly one `ParamRef`.
- `ParamRef` provides stable identity (`parameter`), stable value path (`value`), and required routing (`observe`).

### 8.2 Missing parameters
- `fig.params[sym]` raises `KeyError`.
- `fig.parameter(sym)` creates/returns the ref.

### 8.3 Deferred features (explicitly out of scope)
- Parameter/control removal and full lifecycle management.
- UI deduplication for shared multi-symbol controls (beyond “don’t duplicate on repeated calls”).
- Rerender coalescing/suppression.

---

## 9. Integrated verification checklist (behavioral)

### 9.1 Single-symbol
- `fig.parameter(a)` creates slider+ref and returns `ParamRef`.
- `fig.parameter(a, min=-2)` updates existing slider range.
- `fig.parameter(a, value=0.3)` updates current value and updates reset default value.
- `fig.params[a].observe(cb)` fires `ParamEvent` and triggers `render("param_change", event)`.

### 9.2 Sequence + explicit control
- `fig.parameter([a, b], control=pad)` calls `pad.make_refs([a, b])` exactly once.
- Passing a single-symbol control with `[a, b]` raises (control rejects multi-symbol or manager enforces).

### 9.3 Plot inference
- Plot creation does not call an internal ensure; it calls `fig.parameter(...)`.

### 9.4 Reset semantics
- Docs and UI text state: reset resets value only.
- Reset does not revert `min/max/step`.
- If `parameter(..., value=v)` was called, reset returns to `v`.

### 9.5 Hooks
- Hooks run after plot render on param-change renders.
- `run_now` triggers a well-defined init call with `InitEvent`.

---

# Code Implementation Review: Detailed Evaluation Criteria

Below is an implementation review rubric with concrete pass/fail checks and required evidence (tests or demonstrations).

## A. Public API conformance

### A1. `SmartFigure.parameter(...)` shape and return types
**Pass if:**
- Accepts scalar and sequence inputs.
- Returns `ParamRef` for scalar; `dict[Symbol, ParamRef]` for sequence.
- For repeated calls, still applies provided kwargs.

**Evidence:**
- Unit tests covering scalar and sequence returns.
- Type hints match behavior.

### A2. `fig.params` mapping surface
**Pass if:**
- `fig.params[sym]` returns a `ParamRef`.
- `values()` yields `ParamRef` (not widgets).
- Missing symbol access raises `KeyError`.

**Evidence:**
- Unit test: `pytest.raises(KeyError, ...)` for missing symbol.
- Unit test: `all(isinstance(v, ParamRefLike) ...)` for `values()`.

---

## B. “Single entrypoint” and deletion of `ensure(...)`

### B1. No `ensure(...)` remains
**Pass if:**
- `ParameterManager.ensure` does not exist.
- No call sites remain (including plot inference).

**Evidence:**
- Grep-based check in CI or review notes.
- Tests that create plots and verify parameters are created via `parameter(...)` path (e.g. by mocking/spying).

### B2. Plot inference uses `parameter(...)`
**Pass if:**
- Any auto-created parameters in plot code call `SmartFigure.parameter(...)`.

**Evidence:**
- Integration test that calls `plot(...)` with a sympy expression requiring a parameter and then checks `sym in fig.params`.

---

## C. Idempotence and configuration update behavior

### C1. Idempotent updates on existing params
**Pass if:**
- `parameter(a, min=..., step=..., value=...)` updates an already-created parameter.
- The update applies even if the parameter was created earlier with different values.

**Evidence:**
- Unit tests verifying that calling `parameter(a, min=-2)` after creation changes `fig.params[a].min` (or the underlying widget range).
- Unit tests verifying `value` updates.

### C2. Application order: range before value
**Pass if:**
- When both range and value are passed, the value is applied after range changes.

**Evidence:**
- Unit test with a value that would be invalid under the old range but valid under the new range; verify it succeeds.

---

## D. Multi-symbol control handshake correctness

### D1. Single call to `make_refs` for sequences
**Pass if:**
- `parameter([a, b], control=pad)` calls `pad.make_refs([a, b])` exactly once.

**Evidence:**
- Unit test with a spy control object recording call count and arguments.

### D2. Rejection of invalid multi-binding
**Pass if:**
- A single-symbol control cannot be (silently) used to bind multiple symbols.
- Either the control raises, or the manager detects and raises.

**Evidence:**
- Unit test expecting an exception.

### D3. Control swapping policy
**Pass if:**
- If a symbol exists and a different control instance is provided, `ValueError` is raised.
- If the same control instance is provided and some symbols are missing, it adds missing ones without rebinding existing ones.

**Evidence:**
- Unit test: create `a` with `pad1`, then call `parameter([a, b], control=pad1)` succeeds and creates `b`.
- Unit test: create `a` with `pad1`, then call `parameter(a, control=pad2)` raises `ValueError`.

---

## E. Event routing correctness (`observe → render`)

### E1. `ParamEvent` normalization
**Pass if:**
- All callbacks (manager internal and user) receive `ParamEvent` with correct fields.
- `event.parameter` matches the symbol.
- `event.ref is fig.params[sym]` (or equals appropriately).

**Evidence:**
- Unit tests invoking widget change and validating `ParamEvent`.

### E2. Central render routing
**Pass if:**
- Parameter changes trigger `SmartFigure.render("param_change", event)` through manager wiring.
- This wiring is established when the parameter is created (or ensured via `parameter(...)`).

**Evidence:**
- Integration test with render spied/mocked; assert called on value change.
- Confirm no alternate internal routes exist (review + grep).

### E3. No old==new suppression added
**Pass if:**
- Implementation does not add filters/coalescing logic at this stage.

**Evidence:**
- Review + tests showing a change event triggers render even if values are identical (if the underlying widget emits such events).

---

## F. Reset semantics and documentation

### F1. Reset is value-only
**Pass if:**
- `reset()` changes only the value, not `min/max/step`.

**Evidence:**
- Unit test: set `min` to something new, call reset, verify `min` unchanged.

### F2. `parameter(..., value=v)` updates reset default value
**Pass if:**
- After `parameter(a, value=v)`, calling reset returns to `v`.

**Evidence:**
- Unit test: set to v1 via parameter; change value to v2; call reset; assert value == v1.

### F3. Documentation/UI wording updated
**Pass if:**
- Docstrings and any UI tooltip/label state “Reset value” / “Reset slider value”.

**Evidence:**
- Docstring review in PR; screenshot/manual check if applicable.

---

## G. Hooks ordering and `run_now`

### G1. Hooks fire after plot render on param-change
**Pass if:**
- Hooks run after plots are rendered during a param-change render.

**Evidence:**
- Integration test: hook inspects derived state updated by plot render; verify state is available.

### G2. `run_now` semantics are explicit and stable
**Pass if:**
- Registering a hook with `run_now=True` triggers an immediate call with an explicit init event (`InitEvent` or equivalent), not a fake param-change event and not undocumented `None`.

**Evidence:**
- Unit test: `add_hook(cb, run_now=True)` calls cb once immediately and cb receives an init-typed payload.

---

## H. UI registration / duplication control

### H1. Repeated `parameter(...)` calls do not duplicate controls
**Pass if:**
- Calling `parameter(a)` multiple times does not append the same control multiple times to the layout/control registry.

**Evidence:**
- Unit test verifying control registry length is stable across repeated calls.

---

## I. Code quality / maintainability constraints

### I1. Minimal helper proliferation
**Pass if:**
- The bulk of logic lives in `ParameterManager.parameter(...)` as specified.
- `SmartFigure.parameter(...)` is a thin forwarder.

**Evidence:**
- Code review: confirm no parallel creation logic in figure/plot code.

### I2. Clear exceptions and error messages
**Pass if:**
- Control swapping raises `ValueError` with a message identifying symbol(s) and control mismatch.
- Unsupported capability access raises `AttributeError` (capability contract).

**Evidence:**
- Unit tests for exception types and (at least partial) message matching.

---

## Suggested test matrix (minimum)
1. Scalar create: `parameter(a)` returns ref; control registered once.
2. Scalar idempotent update: `parameter(a, min=-2, step=...)` changes config after creation.
3. Scalar value + reset default update: `parameter(a, value=v)` then `reset()` returns to `v`.
4. Sequence + explicit control: `parameter([a,b], control=pad)` calls `make_refs` once.
5. Single-symbol control rejects multi-symbol: exception.
6. Mixed existing+missing with same control: `a` exists on `pad`, then `parameter([a,b], control=pad)` adds `b`.
7. Control swap rejection: `parameter(a, control=pad2)` after `pad1` raises.
8. Event routing: changing widget value triggers manager `_on_param_change` and figure render called with `ParamEvent`.
9. Hook `run_now`: immediate init call with explicit init payload.
10. Plot inference: plot creation creates parameters via `parameter(...)` only.
