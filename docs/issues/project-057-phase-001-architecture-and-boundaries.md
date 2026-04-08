# Project 057 / Phase 001: architecture and boundaries

## Status
Proposed

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Define the internal architecture and migration boundaries that later phases will implement.

This phase exists to prevent the refactor from turning into another round of shallow file shuffling. The current issue is structural: logic, presentation, shell arrangement, and display transport are fused together. Before moving code, the repository needs a clear internal contract for what will own state, what will own widgets, and what will own display/mount behavior.

## Why this phase is necessary
The current code proves that boundaries are blurred:

- `Figure` passes concrete widget boxes and modal hosts into managers (`src/gu_toolkit/Figure.py:414-468`).
- `FigureLayout` is simultaneously shell policy and one concrete notebook widget tree (`src/gu_toolkit/figure_layout.py:249-423`).
- `ParameterManager` mutates `layout_box.children` directly while also owning parameter state (`src/gu_toolkit/figure_parameters.py:198-374`).
- `LegendPanelManager` mixes plot state, dialog state, anywidget bridges, and direct widget parenting (`src/gu_toolkit/figure_legend.py:772-1012`, `1518-1587`).
- Notebook display is hard-coded through `display(self._layout.output_widget)` (`src/gu_toolkit/Figure.py:3800-3883`).

Without a deliberate contract, implementation work in later phases will drift back into the same coupling.

## What this phase must accomplish

### 1. Define the ownership model
Write down, in code comments or architecture docs accompanying the implementation, the intended responsibilities for:

- figure orchestration logic
- shell layout policy
- section controllers/state
- section presenters/widgets
- notebook display surface
- HTML display surface
- geometry/reflow signaling

The exact class names can vary, but these ownership boundaries must be explicit.

### 2. Define the core internal interfaces or protocols
Create the internal seam definitions needed for later phases. Example concepts:

- shell spec / arrangement object
- section presenter protocol
- section controller/state protocol
- display surface / mount surface protocol
- geometry-change / reflow callback contract
- tab-selection model contract

The implementation can use `Protocol`, ABCs, dataclasses, simple internal classes, or another lightweight pattern. The important part is the boundary, not the exact language feature.

### 3. Define the migration map from current classes to future roles
For each of the current heavy classes, record whether it will be:

- kept mostly as-is
- narrowed into one role
- split into controller + presenter pieces
- deprecated internally and replaced

At minimum this must cover:

- `Figure`
- `FigureLayout`
- `ParameterManager`
- `LegendPanelManager`
- current tab/view-selector handling
- display entrypoints (`show`, `_ipython_display_`)

### 4. Preserve the known-good cores
This phase must explicitly declare which pieces should remain central and should not be rewritten casually:

- `View`
- `ViewManager`
- `PlotlyPane`
- runtime timer support in `runtime_support.py`

Those parts are not the core source of the current problem.

### 5. Define the public-API compatibility strategy
Record how the refactor will preserve or intentionally extend:

- `Figure(...)`
- `show()`
- notebook rich display
- parameter authoring calls
- legend behavior from a user perspective
- view selection semantics
- any future layout/presentation configuration entrypoint

This phase should decide whether arrangement is configured at construction time, through a setter, through presets, through a spec object, or some combination of those.

### 6. Define the test plan for the rest of the project
Record what kinds of tests later phases must add or update:

- section-controller tests without full notebook layout dependency
- JupyterLab/JupyterLite regression tests
- shell arrangement tests
- HTML standalone runtime tests or manual verification surfaces
- Plotly sizing/reflow validation

## Deliverables for this phase

- a clear internal ownership map
- the chosen internal contracts/protocols for shell, sections, display surfaces, and geometry signaling
- a migration map from current classes to future boundaries
- a compatibility plan for public authoring/display APIs
- a concrete test strategy for later phases

## Out of scope

- implementing new arrangements
- splitting parameter or legend code yet
- adding HTML runtime support yet
- changing Plotly sizing behavior yet
- rewriting `View`/`PlotlyPane`

## Exit criteria

- [ ] There is one documented ownership model for shell, sections, and display surfaces.
- [ ] Later phases can point to concrete internal contracts instead of inventing new boundaries ad hoc.
- [ ] There is an explicit migration decision for `FigureLayout`, `ParameterManager`, `LegendPanelManager`, and tabs/navigation.
- [ ] The project can proceed without ambiguity about where notebook-specific code should live and where HTML-specific mounting should live.
