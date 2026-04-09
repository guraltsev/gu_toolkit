# Project 057 / Phase 001: architecture and boundaries

## Status
Implemented

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Define the internal architecture and migration boundaries that later phases will implement.

## Implementation summary
This revision keeps Phase 001 intentionally narrow and concrete.

The implementation now treats **`FigureLayout` as the notebook layout manager**.

That manager owns:

- the current notebook widget tree,
- the stable section widgets for shell/title/navigation/stage/legend/parameters/info/output,
- notebook display materialization,
- notebook parameter control mounting,
- notebook legend body/toolbar/overlay mounting,
- view-selector state synchronization.

`Figure`, `ParameterManager`, and `LegendPanelManager` now delegate notebook-specific mounting work to that layout manager instead of carrying separate presenter/display objects.

## Ownership model

### Figure orchestration logic
Owned by `Figure`.

### Shell layout policy for the current notebook shell
Owned by `FigureLayout`.

### Section controllers/state
Owned by the existing managers (`ParameterManager`, `LegendPanelManager`, info manager, view manager).

### Section widgets / notebook parentage
Owned by `FigureLayout`.

### Notebook display surface
Owned by `FigureLayout._materialize_display_output()`.

### HTML display surface
Not implemented in Phase 001.

### Geometry / reflow signaling
Still coordinated through the existing `FigureLayout`/`Figure` reflow callback path.

## Internal contract chosen for this phase
No layout DSL, no shell spec objects, and no abstract placement model were added.

The concrete internal seam is:

- `FigureLayout` exposes mount methods and stable section widgets.
- managers can use those methods instead of mutating notebook parents directly.
- display entrypoints ask the layout manager to materialize the notebook display object.

That is the whole phase-1 contract.

## Migration map

### `Figure`
Kept mostly as-is as the coordinator, but narrowed away from notebook mounting helpers.

### `FigureLayout`
Kept and promoted into the notebook layout manager boundary.

### `ParameterManager`
Kept, with control mounting delegated to the layout manager when provided.

### `LegendPanelManager`
Kept, with body/toolbar/overlay mounting delegated to the layout manager when provided.

### Current tabs / view selector
Still notebook-only, but state synchronization now belongs to `FigureLayout` directly.

### `show()` / `_ipython_display_()`
Public behavior preserved. Internal display routing now goes through `FigureLayout._materialize_display_output()`.

## Public API compatibility
The user-facing APIs remain effectively unchanged in this phase:

- `Figure(...)`
- `show()`
- notebook rich display
- parameter authoring calls
- legend behavior from a user perspective
- current view-selection semantics

Phase 001 does not add a public arrangement API yet.

## Preserved known-good cores
The following were intentionally left alone:

- `View`
- `ViewManager`
- `PlotlyPane`
- runtime timer support in `runtime_support.py`

## Test plan
Implemented now:

- layout-manager-based parameter mounting tests
- layout-manager-based legend mounting tests
- view-selector synchronization tests on `FigureLayout`
- display routing tests through `FigureLayout`
- stable section-widget exposure tests

Still for later phases:

- alternate shell arrangement tests
- JupyterLab/JupyterLite regression coverage for new arrangements
- standalone HTML runtime tests
- Plotly reflow validation across arrangements

## Exit criteria check
- [x] One documented ownership model exists for shell, sections, and notebook display.
- [x] Later phases can build on concrete layout-manager methods instead of inventing ad hoc boundaries.
- [x] There is an explicit migration decision for `FigureLayout`, `ParameterManager`, `LegendPanelManager`, and view selection.
- [x] Notebook-specific code now has a clearer home: `FigureLayout`.
