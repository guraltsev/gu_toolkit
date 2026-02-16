# Issue 020: Responsive Plotly pane side-pane resize verification gap

Status: **Open**
Opened on: 2026-02-16
Priority: Medium

## Problem summary
The notebook checklist for responsive Plotly behavior still includes an unchecked manual verification step:
- "Check that the plot resizes correctly when the width changes because of opening a side pane"

Source notebook:
- `tests/test-responsive_plotly.ipynb`

## Why this is open
Current automated tests do not assert container-width changes caused by notebook UI chrome (for example, opening a side pane). The notebook note indicates this still requires explicit manual validation.

## Proposed next actions
1. Add a browser-based integration test that resizes the plot container and asserts figure relayout behavior.
2. If relayout lags behind container changes, add a debounce/resize observer fix in `PlotlyPane.py`.
3. Update notebook checklist to checked state after reproducible verification.

## Definition of done
- Automated test covers side-pane/container width change path.
- Manual notebook checklist item can be confidently marked complete.
