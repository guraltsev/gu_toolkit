# Issue 053: MathLive frontend sync could run before the field was connected/mounted, dropping initial state and producing stale transport snapshots

## Status
Closed (2026-04-04)

## Summary
The MathLive anywidget bridge was applying model state and committing transport snapshots too early in the frontend lifecycle. It could try to seed a `math-field` before the custom element was fully defined, before the field was connected to the DOM, or before MathLive had finished its own mount cycle.

That timing mismatch was enough to explain the reported behavior from the showcase notebook: initial text could fail to appear in the visible widget, and backend state could keep reflecting an older or empty snapshot instead of the latest browser edit.

## Evidence
- `src/gu_toolkit/mathlive/widget.py` previously called `syncFromModel()` immediately after `el.appendChild(input)` and called `commitTransport(...)` synchronously from both the initial sync path and the `input` / `change` handlers.
- The previous frontend code did **not** wait for `customElements.whenDefined("math-field")` before creating the MathLive element.
- The previous frontend code did **not** defer initial sync or browser-side commit work with `requestAnimationFrame(...)`, even though other widgets in this repo already use that timing guard when DOM attachment matters.
- The original notebook bug comments explicitly reported the visible symptom: the widget could render blank even when Python-side `value` had been set, and browser edits were not reflected reliably in the Python-facing state.
- The fix now:
  - waits for `customElements.whenDefined("math-field")`,
  - schedules sync/commit work with `requestAnimationFrame(...)`,
  - re-syncs after the MathLive `mount` event, and
  - listens for `blur` / `focusout` in addition to `input` / `change` so the browser-to-kernel bridge has another chance to capture settled field state.
- Regression coverage now includes a frontend-architecture guard in `tests/semantic_math/test_mathlive_inputs.py` that checks for the connected-DOM/mount timing protections in the widget bridge source.

## TODO / Approach to solution
- [x] Wait for the `math-field` custom element to be registered before constructing it.
- [x] Defer initial widget sync until the frontend has had a frame to attach/connect the node.
- [x] Re-run model-to-widget sync once MathLive emits its `mount` event.
- [x] Defer browser-to-kernel transport commits until after the field state has settled for the current frame.
- [x] Add a regression guard so the connected-DOM/mount timing strategy remains visible in tests.

## Exit criteria
- [x] Initial frontend state no longer depends on a synchronous pre-mount `setValue(...)` succeeding.
- [x] Browser-side edits are committed after the visible field state has had a chance to settle.
- [x] The widget bridge source explicitly waits for custom-element readiness and uses deferred sync/commit scheduling.
- [x] Semantic-math tests continue to pass with the updated frontend timing strategy.
