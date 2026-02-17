# Issue 022: Responsive Plotly pane side-pane resize verification gap

## Status
Open

## Summary
State-of-completion checklist:
- [x] `PlotlyPane`/`PlotlyResizeDriver` implementation already includes resize observers, clip-ancestor handling, debounce, and follow-up reflow hooks intended to handle side-pane width changes.
- [x] Basic automated tests exist for `PlotlyPane` wrapper behavior (`reflow` delegation and style wiring).
- [ ] There is still no deterministic browser/integration test that validates container-width changes caused by notebook side panes.
- [ ] The manual notebook checklist item remains unchecked.

## Evidence
- Source notebook: `tests/test-responsive_plotly.ipynb` still contains an unchecked side-pane resize verification item.
- Current automated tests (`tests/test_plotlypane_behavior.py`) do not assert real DOM resize behavior under side-pane/container width changes.

## TODO
- [ ] Add a browser-based integration test that resizes the plot container and asserts figure relayout behavior.
- [ ] If relayout lags behind container changes, add/adjust debounce/resize-observer handling in `PlotlyPane.py`.
- [ ] Update notebook checklist to checked state once verification is reproducible and automated.

## Exit criteria
- [ ] Automated test coverage includes side-pane/container width change behavior.
- [ ] Manual notebook checklist item can be confidently marked complete.
