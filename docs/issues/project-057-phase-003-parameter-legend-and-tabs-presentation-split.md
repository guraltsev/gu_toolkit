# Project 057 / Phase 003: parameter, legend, and tabs logic/presentation split

## Status
Proposed

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Split parameter handling, legend handling, and tabs/navigation handling into controller/state logic versus presentation/widget code.

This is the phase that directly addresses the maintainability request at the section level.

## Current context
The current managers are logic-heavy and widget-heavy at the same time.

### Parameters
`src/gu_toolkit/figure_parameters.py:198-374` shows `ParameterManager` creating default `FloatSlider` controls, binding refs, attaching modal hosts, and directly appending controls into `layout_box.children`.

### Legend
`src/gu_toolkit/figure_legend.py:772-1012`, `1518-1587`, and `1595-1679` show `LegendPanelManager` owning plot state, row state, row widget creation, dialog widgets, context-menu bridge widgets, and direct widget parenting.

### Tabs / navigation
`src/gu_toolkit/figure_layout.py:1598-1760` shows current tab APIs are thin wrappers over one `ToggleButtons` implementation rather than a general selection-model plus presenter boundary.

Those are the core maintainability problems inside the sections themselves.

## What this phase must accomplish

### 1. Split parameter logic from parameter presentation
Refactor parameter handling so that one side owns:

- parameter registry
- refs and hooks
- render-trigger semantics
- custom-control binding policy

and another side owns:

- built-in control widget construction
- section-root widget exposure
- control ordering/placement inside the parameter section
- modal-host specific widget wiring

Custom controls should still be supported, but the binding path should go through an adapter/presenter boundary instead of requiring the logic layer to own `layout_box.children`.

### 2. Split legend logic from legend presentation
Refactor legend handling so that one side owns:

- plot ordering
- active-view filtering
- legend row state
- style state
- sound state / editor-intent state

and another side owns:

- row widgets
- buttons and labels
- toolbar widgets
- dialog widgets
- anywidget bridges
- section-root widget exposure
- modal placement details

The legend logic should no longer decide where its widgets live.

### 3. Split tabs/navigation logic from tabs presentation
Create a reusable navigation model for:

- available tabs/pages
- selected tab/page
- activation callbacks
- selected/hidden state

Then let presenters choose how to render that model:

- `ToggleButtons` where appropriate
- toolkit button-based tab bars where appropriate
- `TabListBridge` for accessibility semantics where appropriate

This is important because view selection and shell-page selection are not the same thing.

### 4. Remove direct shell-container mutation from section logic
After this phase, the logic halves for parameters/legend/tabs should not directly mutate:

- `layout_box.children`
- `header_toolbar.children`
- notebook output placement
- shell slot parenting

Those are presentation responsibilities.

### 5. Make section logic testable without a full notebook shell
The split should make it possible to test controller/state behavior without constructing the full `FigureLayout` shell.

That is one of the strongest proofs that the boundary is real and not cosmetic.

## Deliverables for this phase

- a parameter controller/state half and a parameter presenter/widget half
- a legend controller/state half and a legend presenter/widget half
- a tabs/navigation model plus one or more presenters
- section-level tests that focus on logic separately from widget arrangement

## Out of scope

- standalone HTML runtime mounting
- final Jupyter display-surface migration
- Plotly sizing hardening beyond the callbacks needed for later phases
- broad refactoring of info cards unless a small compatibility shim is required

## Exit criteria

- [ ] Parameter logic no longer requires a concrete layout box to do its job.
- [ ] Legend logic no longer requires a concrete layout box or header toolbar to do its job.
- [ ] Tabs/navigation can be rendered by more than one presenter style.
- [ ] Section logic can be tested independently of one fixed notebook shell.
- [ ] The split is real enough that shell arrangement changes no longer require editing section logic.
