# Issue 006: `Figure.plot(..., visible=False)` raises unexpected keyword error

## Summary
`tests/test_Figure_module_params.py::test_plot_cached_samples_none_before_first_render` failed because `Figure.plot()` did not accept a `visible` keyword, even though `Plot` already supports visibility and intentionally skips rendering while hidden.

## Root cause
- `Plot.__init__` accepts `visible` and applies it to the underlying trace.
- `Plot.render()` exits early when `visible is not True`, which is exactly what this test expects.
- The public API (`Figure.plot` and module-level `plot`) did not expose/forward `visible`, producing a `TypeError` before a plot could be created.

## Implemented fix
- Added `visible: VisibleSpec = True` to:
  - `Figure.plot(...)`
  - module-level `plot(...)`
- Forwarded `visible` in both create and update paths:
  - create path passes `visible` to `Plot(...)`
  - update path passes `visible` to `Plot.update(...)`
- Extended `Plot.update(...)` to handle `visible` updates directly (`self.visible = ...`).
- Added regression coverage for updating an existing plot with `visible=False`.

## Verification
- The regression test for hidden plots now matches the exposed API.
- Additional test confirms update path accepts `visible` without error.

## Disposition
**Fixed.** This was an API mismatch between `Figure.plot`/`plot` and `Plot`.
