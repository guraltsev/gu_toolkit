# Project 057 / Phase 002: slot-based shell and arrangement spec

## Status
Proposed

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Replace the current fixed “figure left / sidebar right / output below” shell with a declarative slot-based shell model that can express multiple arrangements without rewriting section logic.

This phase focuses on shell arrangement, not yet on fully splitting parameter/legend logic from their widget presenters.

## Current context
Today the shell is hard-coded in `FigureLayout`:

- `view_selector` and `view_stage` live in `left_panel`
- `legend_panel`, `params_panel`, and `info_panel` live in one `sidebar_container`
- output lives in `print_area`
- the full-width checkbox mutates one hard-coded wrapper mode

Relevant evidence:

- `src/gu_toolkit/figure_layout.py:249-423`
- `src/gu_toolkit/figure_layout.py:766-856`
- `src/gu_toolkit/figure_layout.py:1805-1841`
- `tests/test_project030_phase1_layout.py`

That structure is the immediate blocker for configurable legend placement and shell-level tabs/pages.

## What this phase must accomplish

### 1. Introduce stable shell slots
Create stable shell slots or shell-region hosts for at least:

- title
- view navigation
- figure stage
- legend section
- parameter section
- info section
- output section
- optional shell page/tab content region

The key rule is that later code should place section roots into slots, not talk directly to one hard-coded sidebar container.

### 2. Introduce a declarative arrangement spec
Add an internal arrangement description capable of expressing at least:

- legend hidden
- legend left
- legend right
- legend bottom
- legend in a separate shell tab/page
- default layout matching the current shell closely

The arrangement spec should support ordering and occupancy decisions without encoding them in manager internals.

### 3. Preserve the current default layout as a preset
The default preset should remain functionally close to the current layout:

- title at the top
- view navigation above the stage when there are multiple views
- figure stage in the main region
- legend/parameters/info available in a side region by default
- output below

The full-width checkbox should disappear from the default visible UI. If a stacked or wide mode remains desirable, it should become a preset or explicit configuration choice, not an always-present shell control.

### 4. Separate shell tabs/pages from view tabs
This phase must explicitly support the idea that shell-level tabs/pages and per-view selection are different concerns.

Examples:

- per-view selection: “main / alt / frequency”
- shell-level pages: “figure / legend / parameters”

Do not force both concerns through the same `ToggleButtons` strip.

### 5. Keep section contents mountable without depending on one sidebar
The arrangement layer should operate on stable section roots/hosts so that later phases can move legend/parameters/info around without changing their underlying logic.

### 6. Update the test contract for the shell
Existing tests that assert a single `sidebar_container` contract will need to be revised or replaced.

This phase should add shell-arrangement tests that assert placement through the new arrangement model instead of through the old fixed sidebar structure.

## Deliverables for this phase

- stable shell slots/hosts
- an arrangement spec or preset system
- a default arrangement preset that matches today’s behavior closely
- support for shell-level page/tab placement concepts
- updated shell tests that no longer encode the old fixed-sidebar assumption as the only valid structure

## Out of scope

- full parameter-controller / parameter-presenter split
- full legend-controller / legend-presenter split
- standalone HTML live widget runtime
- Plotly sizing hardening beyond the shell hooks needed for later reflow work

## Exit criteria

- [ ] Shell arrangement can be changed through a spec/preset layer rather than by editing fixed sidebar code.
- [ ] The default arrangement remains functionally familiar.
- [ ] The full-width checkbox is no longer part of the default shell UI.
- [ ] Legend placement is expressible as hidden/left/right/bottom/tab at the shell-policy level.
- [ ] Tests describe shell placements in terms of arrangement outcomes rather than one hard-coded sidebar object.
