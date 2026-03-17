# Issue 034: Notebook `Figure` display lifecycle contract is ambiguous (`display(fig)` vs constructor autodisplay)

## Status
External review passed. Make sure the behavior is fully documented and close. 

## Summary
Assessment (2026-02-20): implementation and regression coverage are largely complete, but documentation alignment is not fully closed due to notebook TODO mismatch and pending review.

State-of-completion checklist:
- [x] Constructor/display lifecycle behavior is implemented (`display=False` by default, opt-in `display=True`).
- [x] Regression tests cover constructor default behavior, constructor opt-in display, and explicit display hook behavior.
- [x] Code-level docstrings describe the lifecycle contract.
- [ ] Notebook guidance is still not fully aligned (remaining TODO text requests different default semantics).
- [ ] External review/decision on notebook-default expectations is still pending.

The display lifecycle contract is now explicit and test-enforced:
- `Figure(...)` remains side-effect free by default.
- `Figure(..., display=True)` is supported to force immediate display at construction time.
- Explicit display (`display(fig)` or notebook rich display as last expression) continues to work.

## Evidence
- `Figure.__init__` now accepts `display: bool = False` and invokes `_ipython_display_()` when `True`.
- `_ipython_display_` remains the canonical display hook that toggles lifecycle state and displays the widget output.
- Regression tests cover constructor default behavior, constructor `display=True` behavior, and display-hook behavior.
- **WARNING:** notebook source of truth still contains a TODO requesting default autodisplay-on-construction; current implementation adds an explicit opt-in (`display=True`) rather than changing the default behavior.

## Remediation plan
- Keep default construction side-effect free to avoid surprising display side effects.
- Provide explicit constructor opt-in (`display=True`) for users wanting immediate display.
- Enforce the contract with focused regression tests.
- Keep notebook files unchanged in this bugfix and flag the remaining TODO mismatch for a follow-up documentation alignment pass.

## TODO
- [x] Assess current completion state against notebook source of truth.
- [x] Document constructor/display lifecycle contract directly in code docstrings.
- [x] Add regression tests for constructor non-display behavior and `_ipython_display_` lifecycle behavior.
- [x] Add constructor `display=True` option and regression test.
- [x] Record WARNING about notebook TODO contradiction with implemented default behavior.
- [x] External review confirms whether notebook TODO should be removed, revised, or implemented as default behavior.

## Exit criteria
- [x] Notebook display lifecycle behavior is explicitly documented in toolkit docs/code docs.
- [x] Regression tests enforce both default and opt-in constructor display behavior.
- [x] User-facing guidance in this issue is consistent with tested behavior and highlights outstanding notebook mismatch.
- [x] Issue is closed only after external review.
