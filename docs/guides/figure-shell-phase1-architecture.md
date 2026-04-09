# Figure shell refactor / Phase 001 architecture and boundaries

## Status
Implemented

## What Phase 001 does now
Phase 001 does not create a new shell, a new arrangement system, or an HTML runtime.

It makes one structural change only:

**`FigureLayout` is now the notebook layout manager for the shell.**

That means the notebook-specific facts about:

- where parameter controls get mounted,
- where legend rows and overlays get mounted,
- how the current shell root is displayed in a notebook, and
- how view-selection widget state is synchronized

now live on `FigureLayout` instead of being split across `Figure`, `ParameterManager`, `LegendPanelManager`, and ad hoc widget plumbing.

## What was wrong in the code
The problem was still the same structural one described in the project brief.

### Symptom evidence

1. `FigureLayout` built one fixed notebook widget tree and therefore hard-coded one shell arrangement.
2. `Figure` passed concrete notebook containers into logic-heavy managers.
3. `ParameterManager` owned parameter registry logic and direct widget parenting.
4. `LegendPanelManager` owned legend state and direct widget parenting/toolbar hosting.
5. View selection lived inside one `ToggleButtons` implementation instead of a clearer layout-owned state path.
6. Notebook display was treated as a direct `display(...)` concern rather than something owned by the shell/layout side.

### Core source
The core source was still boundary collapse:

- section logic mixed with notebook widget placement,
- shell policy mixed with one concrete widget tree,
- display transport mixed with `Figure.show()` / `_ipython_display_()`.

Adding more booleans or more special cases would still have treated the symptoms instead of the source.

## Ownership model used in this implementation

### `Figure`
Owns orchestration only:

- view activation
- render requests
- manager coordination
- public display entrypoints

`Figure` no longer carries separate notebook presenter/display helper objects for Phase 001.

### `FigureLayout`
Owns notebook shell/layout management:

- the current notebook widget tree
- stable top-level section widgets via `_section_widgets`
- view selector state and widget synchronization
- parameter mounting through `_mount_parameter_control(...)`
- legend mounting helpers such as `_set_legend_body_children(...)`
- notebook display materialization through `_materialize_display_output()`

This is the main phase-1 seam.

### `ParameterManager`
Owns parameter logic:

- parameter refs and registry
- render-trigger semantics
- hooks
- default-control creation

It no longer needs to know how notebook parenting works when a layout manager is supplied.

### `LegendPanelManager`
Owns legend logic:

- plot ordering
- active-view filtering
- row state
- dialog state
- sound/editor intent state

It no longer needs to know notebook container parenting details when a layout manager is supplied.

## Concrete internal contract used now
There is no new arrangement language and no new shell model here.

The contract is much simpler:

- `FigureLayout` exposes notebook mount methods and stable section widgets.
- section managers may call those methods instead of mutating notebook parents directly.
- `Figure.show()` and `_ipython_display_()` ask `FigureLayout` to materialize the notebook display object.

That is enough for Phase 001.

## Migration map

### `Figure`
Kept as coordinator, narrowed away from notebook mounting details.

### `FigureLayout`
Kept and strengthened as the notebook layout manager.

### `ParameterManager`
Kept, but notebook control parenting is now delegated to the layout manager when present.

### `LegendPanelManager`
Kept, but notebook legend parenting/overlay hosting is now delegated to the layout manager when present.

### View selector / tabs compatibility
Kept inside `FigureLayout`, but now treated as layout-manager-owned state plus widget synchronization instead of an external helper stack.

### `show()` / `_ipython_display_()`
Kept public and unchanged from a user perspective; internally they now route through `FigureLayout._materialize_display_output()`.

## What this phase does **not** do
It does not yet add:

- alternate legend placements,
- a slot-based shell,
- HTML mount points,
- PyScript/Pyodide widget runtime injection,
- custom HTML tags.

Those belong to later phases.

## Why this is not a stopgap
This change touches the actual coupling points:

- parameter logic no longer depends on direct notebook box mutation,
- legend logic no longer depends on direct notebook box mutation,
- notebook display is owned by the layout side,
- stable section widgets are now explicit.

That means later layout and HTML work can build on one notebook layout manager instead of reopening the same wiring in several classes.

## Test strategy now in the repo
Phase 001 now tests:

- parameter control mounting through a layout manager,
- legend mounting through a layout manager,
- view-selector state owned by `FigureLayout`,
- figure display routing through the layout manager,
- stable section widgets exposed by the layout manager.

Later phases still need arrangement tests, HTML runtime tests, and Plotly reflow validation.
