# Project 057 / Phase 006: Plotly sizing and validation

## Status
Proposed

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Guarantee that Plotly respects the active layout region across all supported shell arrangements and display environments, and prove that behavior with focused validation.

This phase closes the loop between the shell refactor and the existing responsive Plotly pane architecture.

## Current context
The repository already has a dedicated Plotly sizing boundary in `PlotlyPane` and its anywidget resize driver. That is the right architecture to preserve.

However, the current geometry-trigger story is tied to the current notebook shell:

- full-width checkbox changes call back into reflow (`src/gu_toolkit/Figure.py:464-468`)
- sidebar visibility changes cause active-view reflow (`src/gu_toolkit/Figure.py:1256-1275`)
- `PlotlyPane` measures actual browser geometry rather than trusting Python layout traits

The open responsive verification issue in `docs/issues/bug-022-responsive-plotly-side-pane.md` also shows that responsive behavior still needs stronger end-to-end proof.

## What this phase must accomplish

### 1. Generalize geometry-change signaling
Geometry-affecting events must no longer be limited to the old notebook sidebar/full-width cases.

The new shell must emit reflow-worthy events for at least:

- shell arrangement changes
- legend placement changes
- shell-page/tab switches
- section visibility changes
- HTML slot mount completion
- external HTML/container resizes where relevant
- notebook/Jupyter shell size changes driven by the new arrangement layer

### 2. Keep Plotly sizing responsibility in `PlotlyPane`
Do not move sizing to ad-hoc Python width/height patches.

Instead, preserve the current design principle:

- shell/presentation emits geometry-change intent
- `PlotlyPane` / resize driver measures real browser geometry
- the active pane reflows against the real measured host

### 3. Validate measurable host semantics in every arrangement
Ensure that every supported arrangement keeps the active figure stage in a measurable, fill-capable host with the right flex/min-size semantics.

That includes at least:

- default side-region layout
- legend below layout
- legend hidden layout
- shell tab/page layout
- standalone HTML div-slot layout

### 4. Add regression coverage and verification surfaces
This phase should add or update:

- focused tests for shell-triggered reflow behavior
- tests for active-pane visibility/host semantics where possible
- notebook/manual verification surfaces for arrangements that are hard to prove headlessly
- standalone HTML verification guidance

### 5. Resolve the responsive verification gap explicitly
Use this phase to either close or clearly advance `bug-022-responsive-plotly-side-pane.md` with evidence.

The repository should not claim layout success merely because the shell refactor compiles. Plotly layout respect must be demonstrated.

## Deliverables for this phase

- a generalized geometry/reflow contract for the new shell
- confirmed Plotly sizing behavior across supported arrangements
- updated regression/manual verification coverage
- explicit evidence addressing the current responsive verification gap

## Out of scope

- replacing `PlotlyPane`
- replacing browser-side measurement with Python-only sizing logic
- expanding into unrelated plotting or rendering rewrites

## Exit criteria

- [ ] Plotly respects the active layout region across all supported shell arrangements.
- [ ] Geometry-change events from the new shell correctly trigger pane reflow.
- [ ] Both notebook environments and standalone HTML have validation coverage or clear manual verification guidance.
- [ ] The responsive verification gap is either closed or materially reduced with concrete evidence.
