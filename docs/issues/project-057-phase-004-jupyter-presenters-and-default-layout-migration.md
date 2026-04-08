# Project 057 / Phase 004: Jupyter presenters and default-layout migration

## Status
Proposed

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Make JupyterLab and JupyterLite/JupyterLite+Pyodide first-class consumers of the new shell/presenter boundaries while preserving current user-facing behavior.

This phase is where the new internal design becomes the actual notebook implementation.

## Current context
The current notebook display path is hard-coded through notebook output display:

- `FigureLayout.output_widget` creates a `OneShotOutput` and displays `root_widget` into it (`src/gu_toolkit/figure_layout.py:538-587`)
- `Figure._ipython_display_()` and `Figure.show()` then call `display(self._layout.output_widget)` (`src/gu_toolkit/Figure.py:3800-3883`)

That path works for notebooks but is too notebook-specific to be the long-term figure display contract.

At the same time, JupyterLab and JupyterLite are already working today, so this phase must preserve that behavior while moving them onto the new shell boundaries.

## What this phase must accomplish

### 1. Implement the notebook presentation path on top of the new shell system
Create the concrete notebook presenter/display surface that uses:

- the new shell slots/arrangement spec
- the new section presenters
- the existing stable view runtimes
- notebook widget containers and shared toolkit chrome

The notebook shell can stay visually close to the current UI; what must change is the internal ownership boundary.

### 2. Route notebook display through a display-surface abstraction
`show()` and `_ipython_display_()` should no longer be the only place where the figure “knows” how it is mounted.

The notebook implementation should become one display surface among potentially several. It may still use one-shot notebook output semantics internally if that remains useful, but that behavior should live in the notebook presentation layer, not as the figure’s only display model.

### 3. Preserve current notebook behavior and default layout parity
Validate that the default arrangement remains close to the current notebook behavior:

- multiple views still show view navigation above the stage
- legend/parameters/info behave as expected in the default shell
- output remains visible below the main content
- current notebook examples remain understandable and broadly compatible

### 4. Validate JupyterLite + Pyodide compatibility on the new notebook path
The repository already supports Pyodide-like runtime features at the scheduler/runtime level. This phase must ensure the notebook presenters still work correctly when the kernel/runtime is Pyodide-backed.

### 5. Keep existing anywidget-based helpers working in notebook mode
This includes at least:

- `PlotlyResizeDriver`
- legend interaction bridge
- slider/modal bridges
- tab accessibility bridge if introduced in earlier phases

The notebook migration should not silently break those runtime helpers.

## Deliverables for this phase

- the notebook/Jupyter concrete shell presenter
- the notebook display surface/mount path
- updated notebook-focused tests
- JupyterLab and JupyterLite regression validation on the new architecture

## Out of scope

- standalone HTML runtime bootstrap
- HTML slot mounting
- final Plotly sizing hardening across every arrangement

## Exit criteria

- [ ] JupyterLab still works on the new shell/presenter boundaries.
- [ ] JupyterLite + Pyodide still works on the new shell/presenter boundaries.
- [ ] Default notebook behavior remains functionally similar to today.
- [ ] Notebook display is implemented through the new display-surface boundary rather than as the figure’s only hard-coded display path.
- [ ] Anywidget-based notebook helpers continue to function.
