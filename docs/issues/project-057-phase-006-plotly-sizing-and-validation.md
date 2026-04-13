# Project 057 / Phase 006: visibility lifecycle, Plotly sizing, and validation

## Status
Proposed (revised)

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Guarantee that Plotly respects the **currently visible layout region** across all supported shell arrangements and display environments, and prove that behavior with focused validation.

This phase also formalizes the new hidden / visible lifecycle:

- hidden plot-bearing sections may defer expensive work
- visible transitions must trigger refresh / reflow

## Current context
The repository already has the right low-level sizing boundary in `PlotlyPane`.

Relevant evidence:

- `src/gu_toolkit/PlotlyPane.py:643-655` computes DOM host visibility
- `src/gu_toolkit/PlotlyPane.py:942-952` waits for visibility and measurable size before resizing

The repository also already has a useful stale-marking pattern in the render pipeline:

- `src/gu_toolkit/figure_diagnostics.py:411-456` renders the current view and marks other views stale on parameter changes

Those are exactly the two ingredients the revised shell needs:

- DOM-owned visibility for sizing
- deferred refresh for content that is not currently visible

What is still missing is a shell-level contract that turns section visibility changes into the right render / reflow behavior across notebook and HTML surfaces.

## What this phase must accomplish

### 1. Define a real visibility lifecycle for plot-bearing sections
The shell must emit transport-neutral lifecycle events for at least:

- section became visible
- section became hidden
- section host mounted
- section host geometry changed
- page became visible / hidden when pages are used

This lifecycle should be defined for **section instances**, not only for views.

### 2. Defer hidden plot work instead of forcing immediate updates
When a plot-bearing section is hidden, the runtime should be allowed to:

- skip immediate expensive plot updates
- mark that section dirty / stale
- wait for the next visible transition to do the expensive refresh

This is the revised-shell analogue of the existing inactive-view stale-marking pattern.

### 3. Refresh and reflow when visibility returns
When a hidden plot-bearing section becomes visible again, the shell/runtime must:

- schedule a render if the section is dirty / stale
- queue a pane reflow so `PlotlyPane` can measure the now-visible host
- avoid duplicate work when repeated visibility changes happen quickly

### 4. Keep Plotly sizing responsibility inside `PlotlyPane`
Do **not** move sizing into ad hoc Python width / height patches.

The preserved design principle is:

- shell surfaces emit visibility / geometry intent
- `PlotlyPane` / resize driver measures real browser geometry
- Plotly reflows against the measured host once the host is visible and measurable

### 5. Validate measurable host semantics in every arrangement
Ensure that every supported arrangement keeps visible plot-bearing sections inside hosts with the correct measurable semantics.

That includes at least:

- default notebook side-region layout
- legend below layout
- legend hidden layout
- separate page / tab layout
- standalone HTML div-slot layout
- layouts containing more than one legend / info section

### 6. Validate that visibility ownership really moved to the shell surface
This phase must prove that the new architecture is not just cosmetic.

Evidence should show that:

- hiding a section does not require tearing down the whole figure shell
- repeated page switches do not duplicate widget mounting
- Plotly respects the visible host rather than stale Python layout guesses
- the shell uses DOM / widget visibility rather than a second custom geometry engine

### 7. Add regression coverage and manual verification surfaces
This phase should add or update:

- focused tests for shell-triggered visibility / reflow behavior
- tests for deferred render / stale semantics while hidden
- notebook/manual verification surfaces for hard-to-prove responsive cases
- standalone HTML verification guidance

### 8. Resolve the responsive verification gap explicitly
Use this phase to either close or materially advance `docs/issues/bug-022-responsive-plotly-side-pane.md` with concrete evidence.

The project should not claim success merely because the shell composes. Plotly region-respect must be demonstrated.

## Deliverables for this phase

- a generalized visibility lifecycle contract for shell section instances
- deferred-render / stale semantics for hidden plot-bearing sections
- confirmed Plotly sizing behavior across supported arrangements and transports
- updated regression and manual verification coverage
- explicit evidence addressing the current responsive verification gap

## Out of scope

- replacing `PlotlyPane`
- replacing browser-side measurement with Python-only sizing logic
- rewriting unrelated plotting or rendering systems

## Exit criteria

- [ ] Plotly respects the currently visible layout region across all supported shell arrangements.
- [ ] Hidden plot-bearing sections can defer expensive work and then refresh / reflow when visible.
- [ ] Visibility / geometry changes from the notebook and HTML shell surfaces correctly trigger pane reflow.
- [ ] Both notebook environments and standalone HTML have validation coverage or clear manual verification guidance.
- [ ] The responsive verification gap is either closed or materially reduced with concrete evidence.
