# Guide/Plan: Fix Parameter System Issues (SmartFigure / SmartSlider / ParameterManager)

Date: 2026-02-07

This guide consolidates all issues raised in this conversation and provides a concrete implementation plan. The goals are:

- Remove the `ensure(...)` concept entirely.
- Make `parameter(...)` the *only* entrypoint for creating/configuring parameters.
- Keep a ref-first API (`fig.params[sym] -> ParamRef`), with required `ParamRef.observe` routing changes to `SmartFigure.render(...)`.
- Keep reset semantics as **value-only**, and fix documentation accordingly.
- Avoid adding a proliferation of helper functions; implement the behavior primarily in **one** method on `ParameterManager`.

---

## 1. Issues to address

### 1.1 `ensure(...)` blocks required idempotence/config update behavior
Current behavior: if a parameter exists, `ensure(...)` returns immediately and ignores new kwargs.  
Required behavior: `parameter(a)` is idempotent; `parameter(a, min=..., value=...)` must create if missing and **set/update** provided values even if already created.

### 1.2 Sequence + explicit control is handled incorrectly
Current behavior: sequence calls loop per symbol and pass the same control repeatedly, preventing the intended multi-symbol handshake (`control.make_refs(symbols)` once). This also enables accidental “two symbols bound to one scalar slider” patterns when the control is single-symbol.

### 1.3 Plot inference creates parameters through a backdoor
`SmartFigure.plot(...)` auto-creates parameters via `ensure(...)`. After removing `ensure`, plot inference must route through `parameter(...)` so there is only one creation/config policy.

### 1.4 Reset docs are wrong; reset is value-only
Reset currently restores only `.value`, not min/max/step, but documentation suggests “initial defaults”. You explicitly want docs changed (not behavior changed): “reset resets only value”.

### 1.5 Hook initialization (“run_now”) is missing / unacceptable
Hooks currently run only after a parameter-change render path. You want a clean way to run hooks at registration time without inventing brittle semantics.

### 1.6 `control_kwargs` ignored when a control instance is supplied
Configuration kwargs are applied only when constructing the default slider; they should also apply when an explicit `control=` is passed.

### 1.7 Redundant re-render suppression is not a priority
Do not add complexity to filter events for `old == new` at this stage.

---

## 2. Architectural decision

### 2.1 Put `parameter(...)` logic in `ParameterManager`
If parameter creation/configuration and ref wiring are part of the parameter system, they belong in `ParameterManager`. Then:

- `SmartFigure.parameter(...)` becomes a thin forwarder to the manager.
- `ParameterManager` becomes the single source of truth for:
  - creation of default controls,
  - binding controls → refs (`make_refs`),
  - storing refs (`_refs`) and controls (`_controls`),
  - wiring `observe` to route to render,
  - applying configuration kwargs to existing parameters.

This removes duplicated logic and prevents the “backdoor creation” problem.

---

## 3. Implementation plan (minimal functions)

### Step A — Delete `ensure(...)`
- Remove `ParameterManager.ensure(...)` entirely.
- Remove any references to `ensure` in `SmartFigure` and elsewhere.

### Step B — Add `ParameterManager.parameter(...)`
Implement a single method:

```python
def parameter(self, symbols, *, control=None, **control_kwargs):
    """Create/configure parameter(s) and return ParamRef(s)."""
```

#### B1) Normalize input
- Convert `symbols` into a list `syms`.
- Track whether the original request was scalar (return a single `ParamRef`) or sequence (return `dict[Symbol, ParamRef]`).

#### B2) Partition into existing vs missing
- `existing = [s for s in syms if s in self._refs]`
- `missing  = [s for s in syms if s not in self._refs]`

#### B3) Create refs for missing symbols
**Case 1: `control is None` (default slider-per-symbol)**

For each `s in missing`:
1. Construct the default `SmartFloatSlider` with default config.
2. Call `refs = slider.make_refs([s])`.
3. Store `self._refs[s] = refs[s]`.
4. Wire render routing: `refs[s].observe(self._on_param_change)`.
5. Register the control for display once (append to `_controls`, update `_layout_box.children`).

**Case 2: `control is not None` (explicit control provided)**

1. Call `new_refs = control.make_refs(missing)` **exactly once**.
   - This enforces correct multi-symbol binding and lets single-symbol controls reject multi-symbol usage.
2. For each `s in missing`:
   - store `self._refs[s] = new_refs[s]`,
   - wire `observe` to `_on_param_change`.
3. Register the control for display once.

#### B4) For existing symbols, prevent control swapping (for now)
If `control is not None` and `existing` is non-empty:
- If the existing symbol is already bound to a different control, raise a `ValueError`.
- Reason: removal/rebinding and lifecycle management are postponed; silent rebinding would be dangerous.

#### B5) Apply configuration kwargs to *all requested refs* (existing + missing)
This is the key behavioral requirement.

- Only apply values explicitly provided in `control_kwargs`.
- Apply via the ref API/capabilities (e.g., `ref.min`, `ref.max`, `ref.step`, `ref.value`).
- If a ref does not support an attribute, let it raise `AttributeError` (capability contract).

**Order recommendation:**
1. Apply range/config first (`min/max/step`),
2. Apply `value` last (so the chosen value is interpreted under updated bounds).

#### B6) Value-only reset semantics: update “default reset value” on configuration
Because reset is value-only, the “default value” used by reset should be updated when the user configures `value=` via `parameter(...)`.

- Add one method on `SmartFloatSlider`, e.g. `set_default_value(v)` that updates its stored reset value.
- In `ParameterManager.parameter`, when `value` is provided and the underlying control is a `SmartFloatSlider`, call `set_default_value(value)`.

This makes the rule true:
- `parameter(a, value=0.3)` sets the authoritative value *and* sets what reset returns to.

### Step C — Make `SmartFigure.parameter(...)` a forwarder
Implement:

```python
def parameter(self, symbols, *, control=None, **control_kwargs):
    out = self._params.parameter(symbols, control=control, **control_kwargs)
    self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)
    return out
```

No creation/config logic in `SmartFigure` beyond layout visibility.

### Step D — Route plot inference through `parameter(...)`
Replace any auto-creation via `ensure` with a call to the public entrypoint:

- In `SmartFigure.plot(...)`, when parameters are detected, call:
  - `self.parameter(parameters)` (preferred) or loop `self.parameter(p)`.
- This preserves “one entrypoint” and makes the behavior consistent.

### Step E — Fix reset documentation (value-only)
Do **not** change behavior; change documentation and UI wording.

- Update `SmartFloatSlider._reset` docstring to “Reset the slider value to its initial value.”
- Update `SmartFloatSlider.reset()` docstring similarly.
- If there is a reset button tooltip/label, consider “Reset value”.

### Step F — Hooks: implement a clean `run_now`
Goal: allow immediate hook execution at registration time without requiring fake parameter-change events.

Recommended approach:
- Keep hooks as “param-change hooks” for normal operation.
- Provide a figure-level helper with explicit semantics, e.g.:

```python
def add_hook(self, callback, *, run_now=True, hook_id=None):
    self._params.add_hook(callback, hook_id=hook_id)
    if run_now:
        # Option 1: call callback(None) and document it
        callback(None)
```

If you want to avoid `Optional` payloads, use an explicit initialization hook API (separate from param-change hooks).

### Step G — Do not add redundant rerender suppression
Do nothing for old==new filtering. Keep the current “few redundant rerenders expected” assumption.

---

## 4. Verification checklist

### 4.1 Single-symbol behavior
- `fig.parameter(a)` creates a default control on first call; subsequent calls do nothing.
- `fig.parameter(a, min=-2)` updates the existing control range if `a` already exists.
- `fig.params[a]` returns a `ParamRef`.
- `fig.params[a].observe(cb)` fires normalized `ParamEvent` and routes through `render("param_change", event)`.

### 4.2 Sequence behavior and multi-symbol controls
- `fig.parameter([a, b], control=pad)` calls `pad.make_refs([a, b])` exactly once.
- Single-symbol controls reject `parameter([a,b], control=slider)` (raise) rather than silently binding both.

### 4.3 Plot inference
- `fig.plot(...)` never calls internal “ensure-like” logic; it calls `fig.parameter(...)`.

### 4.4 Reset docs
- Documentation clearly states reset is value-only.
- `parameter(a, value=...)` updates what reset returns to (via `set_default_value`).

### 4.5 Hooks
- Hook registration can run immediately (`run_now`) with documented semantics.
- Param-change hooks still run after plot rendering on parameter-change renders.

---

## 5. Scope explicitly deferred
- Parameter/control removal and rebinding policies beyond “no silent swap”.
- Multi-control UI deduplication and lifecycle management.
- Rerender suppression and coalescing of events.
