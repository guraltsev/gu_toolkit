# Issue 022: Responsive Plotly pane side-pane resize verification gap

## Status
Open

## Summary
The notebook checklist for responsive Plotly behavior still includes an unchecked manual verification step: "Check that the plot resizes correctly when the width changes because of opening a side pane".

This issue tracks adding deterministic verification so the behavior is covered by a repeatable test instead of a one-off manual check.

## Evidence
- Source notebook: `tests/test-responsive_plotly.ipynb`.
- Current automated tests do not assert container-width changes caused by notebook UI chrome (for example, opening a side pane).

## TODO
- [ ] Add a browser-based integration test that resizes the plot container and asserts figure relayout behavior.
- [ ] If relayout lags behind container changes, add debounce/resize-observer handling in `PlotlyPane.py`.
- [ ] Update notebook checklist to checked state once verification is reproducible.

## Exit criteria
- Automated test coverage includes side-pane/container width change behavior.
- Manual notebook checklist item can be confidently marked complete.
