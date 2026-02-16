# Project 018: Fix Known Bugs & Clean Up Stale Code

## Status
Completed (2026-02-15)

## Goal/Scope
Resolve known reliability bugs and remove stale code/documentation references that caused confusion for maintainers.

## Delivered Outcomes

### Bug fixes
- `ParseLaTeX.parse_latex()` now validates the `lark` result type and falls back to `antlr` when `lark` returns a non-SymPy object.
- `Plot.__init__` and `Plot.set_func` use immutable defaults for `parameters`.
- `Plot.__init__` uses a valid union type for `sampling_points` (`Optional[Union[int, str]]`).
- `QueuedDebouncer` wraps callback execution in a logging boundary so callback exceptions are visible and do not wedge subsequent queued updates.

### Stale code/documentation cleanup
- Removed stale and duplicate legacy content from `Figure.py`.
- Reduced `prelude.py` to its intended alias surface without duplicate imports/commented debug leftovers.
- Updated developer-guide naming references to current module names (`Figure.py`, `Slider.py`).

## TODO checklist
- [x] `parse_latex()` always returns a SymPy expression (never a raw parser tree/object).
- [x] Regression coverage exists for lark non-expression fallback behavior.
- [x] No mutable default args remain in `Plot` public entry points targeted by this project.
- [x] `sampling_points` typing is syntactically valid.
- [x] `QueuedDebouncer` logs callback errors and keeps processing queued calls.
- [x] Stale/duplicate code comments/docstrings targeted by this project are removed.
- [x] Developer guide references use current file names.

## Exit criteria
- [x] Reliability regressions from project scope are covered by tests.
- [x] Project tracking moved under `documentation/projects/_completed/`.
- [x] Related issue tracking documentation updated to reflect resolution.
