# Project 057 / Phase 003: peer section model and section-state split

## Status
Proposed (revised)

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Replace the remaining singleton-section and view-centric assumptions with a **peer section model**, and split the section logic that truly matters now:

- parameters: controller/state vs widget surface
- legend: controller/state vs widget surface
- info content: enough shell-facing structure to support multiple peer info sections/cards

This phase also intentionally revises the old “tabs / navigation split” idea.

The shell still needs page buttons and other controls, but tabs are **not** the conceptual center of the architecture. The conceptual center is now:

- peer section instances
- soft associations
- shell-owned visibility

## Current context
Phase 002 introduced a useful stepping stone: shell presets and page regions.

But the codebase still shows that the shell is not yet ready for the new requirements.

### The phase-2 shell is still singleton-based
`src/gu_toolkit/figure_shell.py:15-16` defines only three shell section ids:

- `legend`
- `parameters`
- `info`

`src/gu_toolkit/figure_shell.py:78-104` then forbids mounting the same section id more than once and requires exactly one stage page.

That is not a peer-section model. It is still a singleton-category model.

### `FigureLayout` still exposes one legend surface and one info surface
`src/gu_toolkit/figure_layout.py:351-381` builds exactly one legend panel, one parameters panel, and one info panel.

`src/gu_toolkit/figure_layout.py:479-504` then stores those singleton surfaces in `_section_widgets` / `_shell_slots`.

That means the shell can move one legend around, but not create multiple legend section instances.

### `Figure` still wires one legend manager and one info manager
`src/gu_toolkit/Figure.py:423-437` constructs one `InfoPanelManager` and one `LegendPanelManager`.

`src/gu_toolkit/Figure.py:1256-1263` collapses shell visibility to three booleans.

That is exactly the wrong granularity for the revised problem.

### Legend logic is still fused to active-view filtering
`src/gu_toolkit/figure_legend.py:1529-1652` shows:

- `set_active_view(...)`
- `_plot_in_active_view(...)`
- `refresh(...)` building the visible row list based on the active view.

The revised shell should not make views the organizing rule for legend sections.

### Info content is still one-box-plus-view-scope
`src/gu_toolkit/figure_info.py:332-342` appends outputs into one `_layout_box.children` container.

`src/gu_toolkit/figure_info.py:641-697` stores `card.view_id` and hides cards based on the active view.

That makes info content children of one singleton shell area rather than peer shell sections.

## What this phase must accomplish

### 1. Replace singleton shell sections with peer section instances
Introduce an internal section registry whose entries represent **instances**, not categories.

Each section record should have at least:

- stable section id
- section kind (`stage`, `legend`, `info`, `parameters`, `output`, ...)
- controller / state owner
- stable widget surface root
- optional association metadata
- optional default placement hints or tags

The new shell model must support, at minimum:

- multiple legend sections
- multiple info sections / info-card sections
- one or more stage sections later, without changing the model again

### 2. Introduce soft associations instead of ownership
A legend or info section may be naturally associated with:

- one plot id
- a plot group
- a semantic label or tag

But those relationships must remain **soft metadata**.

The layout must still be free to do unusual arrangements, including deliberately placing one plot beside another plot’s legend.

Do **not** introduce plot-subordinate legend or info ownership.

### 3. Split parameter handling into controller/state versus widget surface
Refactor parameters so one side owns:

- parameter registry
- refs and hooks
- render-trigger semantics
- custom-control binding policy

and another side owns:

- concrete control widgets
- modal-host specific wiring
- stable widget roots used by shell sections
- ordering / grouping inside parameter sections

The parameter controller must no longer require a concrete shell layout box to do its job.

### 4. Split legend handling into controller/state versus widget surface
Refactor legend handling so one side owns:

- plot membership for the legend section
- ordering
- row state
- style state
- sound state
- editor intent

and another side owns:

- row widgets
- labels / toggles / buttons
- toolbar widgets
- dialog widgets
- anywidget bridges
- stable legend section roots
- modal placement details

The new legend controller must not require:

- `layout_box`
- `header_toolbar`
- `active_view_id`

as its primary way of deciding what content it represents.

A compatibility adapter may still read legacy `plot.views` data where needed, but that must not be the new architectural center.

### 5. Promote info content into the peer-section model
This phase does **not** need to explode the info system into many unrelated classes.

But it does need to make info content shell-ready.

At minimum, the revised design must support:

- multiple info section instances or card groups
- stable widget roots for those sections
- shell-level placement independent of one global info box
- optional association metadata that defaults can use

The old model of “one info manager that appends widgets into one box” is no longer enough.

### 6. Replace the old tabs/navigation split with shell visibility state
Do **not** build a large independent navigation / presenter hierarchy.

Instead, create a small shell-level visibility model that can express:

- which page is selected, if pages are used
- which section instances are currently visible
- which plot-bearing sections are hidden and therefore eligible for deferred rendering

Notebook buttons, tab bars, HTML page controls, or CSS classes are then just **controls over that state**.

### 7. Keep views out of the new shell contracts
Views may remain part of the plotting runtime for now.

But the new shell-facing contracts introduced in this phase must not require:

- `view_id` for section identity
- active-view filtering as the normal legend rule
- active-view-scoped info as the normal info rule

Legacy view-based behaviors may remain behind compatibility shims if needed.

### 8. Make section logic testable without a full notebook shell
The new controller/state halves for parameters and legends should be testable without constructing the full `FigureLayout` tree.

The new section registry / association behavior should also be testable without a notebook display environment.

That is one of the clearest proofs that the split is real.

## Suggested internal shape

The exact names may vary, but the boundary should look roughly like this:

- `SectionRecord`
  - id, kind, controller, widget_surface, associations, tags
- `SectionAssociation`
  - plot ids / group ids / semantic tags
- `ParameterController`
  - refs, hooks, control binding policy
- `ParameterWidgetSurface`
  - live widget roots and control mounting
- `LegendController`
  - row state and legend-specific logic for one legend section instance
- `LegendWidgetSurface`
  - rows, toolbar, dialogs, bridges
- `InfoSectionAdapter` or equivalent
  - enough structure to expose info content as peer shell sections
- `ShellVisibilityState`
  - page selection and section visibility, but not a giant tabs framework

## Deliverables for this phase

- a peer section registry / section-record model
- soft association metadata used by defaults but not enforced as ownership
- a parameter controller/state half and a parameter widget-surface half
- a legend controller/state half and a legend widget-surface half
- info content promoted enough to participate as peer shell sections
- shell visibility state that replaces the old tabs-centric split
- section-level tests that focus on logic separately from notebook shell composition

## Out of scope

- standalone HTML widget runtime bootstrap
- final notebook display-surface migration
- final Plotly sizing sign-off
- removal of public legacy view APIs
- a custom HTML UI stack

## Exit criteria

- [ ] The internal shell model can represent multiple legend sections and multiple info sections as peer items.
- [ ] Section associations are represented as soft metadata rather than ownership.
- [ ] Parameter logic no longer requires a concrete shell layout box.
- [ ] Legend logic no longer requires a concrete layout box, a header toolbar, or an active-view id as its primary contract.
- [ ] Info content can participate in the shell as more than one peer section.
- [ ] Shell visibility state exists independently from whichever notebook / HTML control happens to expose it.
- [ ] Section logic is testable without constructing one fixed notebook shell.
