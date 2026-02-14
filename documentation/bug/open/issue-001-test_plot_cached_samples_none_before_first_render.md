# Issue 001: `Figure.plot(..., visible=False)` raises unexpected keyword error

## Summary
`tests/test_Figure_module_params.py::test_plot_cached_samples_none_before_first_render` fails because `Figure.plot()` does not accept a `visible` keyword, even though `Plot` supports visibility and render-skipping for hidden traces.

## Analysis
- Failure: `TypeError: Figure.plot() got an unexpected keyword argument 'visible'`.
- `Figure.plot` signature does not include `visible` and does not forward it to `Plot`.
- `Plot.__init__` *does* include `visible` and `Plot.render()` explicitly skips rendering when `visible is not True`, which aligns with the test's intent.
- This looks like an API inconsistency between the public facade (`Figure.plot`) and the underlying plot model (`Plot`).

## Proposed solution
- **Recommended (bug fix):** Add `visible: bool | str = True` to `Figure.plot` and forward it in both create and update paths (`Plot(...)` and `plot.update(...)`).
- Also add `visible` support in `Plot.update` for symmetry.
- If maintainers intentionally removed public `visible`, then this test is outdated and should be rewritten to set `plot.visible = False` immediately after creation.

## Disposition
**Likely bug (API mismatch), unless removal of `visible` from `Figure.plot` was intentional.**
