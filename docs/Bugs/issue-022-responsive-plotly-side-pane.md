# Issue 022: Responsive Plotly pane side-pane resize verification gap

## Status
Open

## Summary
State-of-completion checklist:
- [x] `PlotlyPane`/`PlotlyResizeDriver` implementation includes resize observers, clip-ancestor handling, debounce, and follow-up reflow hooks.
- [x] Basic automated tests exist for `PlotlyPane` wrapper behavior (`reflow` delegation and style wiring).
- [ ] No deterministic browser/integration test validates side-pane or container-width resize behavior end to end.
- [ ] Manual notebook checklist item for side-pane width changes is still unchecked.
- [ ] No doc update in `docs/notebooks/Toolkit_overview.ipynb` or guide docs confirms validated side-pane behavior.

## Evidence
- `tests/test-responsive_plotly.ipynb` still includes unchecked side-pane resize verification items.
- Current automated tests do not assert real DOM resize behavior under side-pane/container width transitions.

## TODO
- [ ] Add a browser-based integration test that resizes the plot container and asserts figure relayout behavior.
- [ ] If relayout lags behind container changes, adjust debounce/resize-observer behavior in `PlotlyPane.py`.
- [ ] Update notebook/manual checklist to checked state once verification is reproducible and automated.

## Exit criteria
- [ ] Automated test coverage includes side-pane/container width change behavior.
- [ ] Manual notebook checklist item can be confidently marked complete.
