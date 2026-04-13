# Project 057: Figure shell presentation/runtime refactor


## Summary
Refactor the figure shell around **filtered presentations over global plot/parameter stores** and **transport-neutral mount surfaces**, while preserving the existing stable Plotly runtime strengths internally.

Design note: the earlier Phase 003 framing around peer sections and soft associations was too abstract. The revised Phase 003 blueprint treats the architectural center as:

- global plots
- global parameters
- explicit filters
- legend and parameter presentations built from those filters
- a small mount manager that places those presentation roots

A "stage" in the revised design is only the user’s name for a Plotly plot widget/container. It is not a new central architecture object.

Where this document still uses earlier “peer section” wording below, treat Phase 003 as the authoritative correction. The implementation blueprint for handoff is in `project-057-phase-003-parameter-legend-and-tabs-presentation-split.md`.

The reviewed correction is: filters first, management/presentation split second, mounting last. That ordering is now authoritative for implementation.

The end state must support three environments with the same core figure logic:

- JupyterLab
- JupyterLite + Pyodide
- standalone HTML with inline PyScript + a Pyodide kernel + an injected live widget runtime

This revision changes the architectural center of gravity.

The shell must no longer be organized around:

- one singleton legend section,
- one singleton info section,
- or active-view-driven shell visibility.

Instead, the shell must organize **peer section instances** such as:

- plot/stage sections,
- legend sections,
- info-card / info-output sections,
- parameter sections,
- output sections,
- optional page containers.

Those sections may carry **association metadata** that says which plots they are naturally related to, but those associations are **advisory**. They are used by default layout builders, not enforced as ownership or containment.

The preferred implementation is still **not** a custom DOM rewrite. The preferred implementation is a slot-based shell that reuses live `ipywidgets` / `anywidget` components and can either:

1. compose them inside notebook widget containers, or
2. mount the same section-root widgets into named HTML `<div>` slots controlled by responsive CSS.

This revision also adopts a simpler visibility rule:

- the notebook / HTML shell owns **who is visible**,
- hidden sections stay mounted where practical,
- plot-bearing sections may defer expensive updates while hidden,
- visible transitions trigger refresh / reflow.

Tabs and page buttons are therefore treated as **shell controls**, not as a new standalone architecture that needs its own presenter hierarchy.

## Hard requirements

1. Parameter handling and legend handling must each have explicit controller/state versus widget-surface responsibilities.
2. The shell model must support **multiple legend sections** and **multiple info sections/cards** as peer items.
3. Associations between sections and plots must be **soft metadata**, not parent/child ownership. The layout is allowed to place plot 1 beside legend 2 if explicitly asked.
4. The arrangement of sections must be declarative and configurable.
5. Legend placement must support at least:
   - hidden
   - left of the plot/stage
   - right of the plot/stage
   - below the plot/stage
   - separate page / tab from the plot/stage
6. The default layout must remain functionally close to the current one, except the inline full-width toggle should disappear.
7. Plotly must obey the size of the **currently visible layout region**.
8. Hidden plot-bearing sections must be allowed to defer rendering and then refresh / reflow when they become visible.
9. The implementation must preserve the live widget model instead of replacing it with custom HTML controls.
10. JupyterLab, JupyterLite + Pyodide, and standalone HTML + PyScript + Pyodide must share the same core section model.

## General instructions

- Preserve the current strengths of the runtime:
  - one stable `View` runtime per view
  - one stable `PlotlyPane` per view
  - browser-measured Plotly sizing through the existing pane / driver model
- Treat the current view runtime as an **internal plotting runtime**, not as the organizing primitive for shell sections.
- Do not build more architecture around active-view-centric shell rules.
- Treat the current singleton shell sections (`legend`, `parameters`, `info`) as a stepping stone, not as the long-term API.
- Prefer:
  - section registries,
  - stable section-root widgets,
  - association metadata,
  - shell mount surfaces,
  - visibility lifecycle hooks,
  over more booleans, more widget re-parenting, or more presenter families.
- Reuse existing toolkit UI primitives where possible, especially section chrome, modal helpers, and `TabListBridge` where it helps accessibility.
- Do not rewrite plotting, sampling, code generation, or unrelated notebook helpers.
- Do not switch away from `ipywidgets` / `anywidget` unless a concrete requirement forces it.
- Do not solve the HTML requirement with static embedding. The HTML target explicitly requires a live Pyodide-backed widget runtime.
- Keep public authoring APIs stable unless a new layout / section option genuinely needs a small extension.

## Evidence of the current problem

### 1. The shell spec still models singleton section types, not section instances
`src/gu_toolkit/figure_shell.py:15-16` hard-codes `_VALID_SECTION_IDS = ("legend", "parameters", "info")`.

`src/gu_toolkit/figure_shell.py:78-104` then validates that:

- each section id may be mounted only once, and
- each shell preset has exactly one stage page.

That means the current shell model cannot represent:

- multiple legend sections,
- multiple info-card sections,
- or peer section instances with distinct identities.

This is a direct mismatch with the new requirement.

### 2. `FigureLayout` still creates exactly one legend section and one info section
`src/gu_toolkit/figure_layout.py:326-505` builds:

- one `view_selector`
- one `view_stage`
- one `legend_panel`
- one `params_panel`
- one `info_panel`
- one `_section_widgets["legend"]`
- one `_section_widgets["info"]`

So even after the earlier shell refactor, the shell still thinks in terms of **singleton section categories**, not peer section instances.

### 3. `Figure` still owns one legend manager, one info manager, and one boolean visibility sync
`src/gu_toolkit/Figure.py:423-437` wires exactly one `InfoPanelManager` and one `LegendPanelManager`.

`src/gu_toolkit/Figure.py:1256-1263` reduces shell state to three booleans:

- `has_params`
- `has_info`
- `panel_visible` for the singleton legend manager.

That means the figure orchestration layer can currently answer only:

- “do we have any legend?”
- “do we have any info?”

It cannot express:

- multiple legend sections,
- multiple info sections,
- or visibility per section instance.

### 4. Legend behavior is still keyed to the active view
`src/gu_toolkit/figure_legend.py:1529-1652` shows that `LegendPanelManager` still owns:

- `_active_view_id`
- `set_active_view(...)`
- `_plot_in_active_view(...)`
- `refresh(...)` filtering based on `plot.views`

That means legend visibility is still conceptually driven by **active view membership**, not by section identity plus declared plot membership.

### 5. Info outputs and info cards still live inside one layout box and can be view-scoped
`src/gu_toolkit/figure_info.py:332-342` appends each output directly into one `_layout_box.children` list.

`src/gu_toolkit/figure_info.py:641-697` then stores `card.view_id` and hides or shows cards according to the active view.

So info content is still modeled as children of one singleton info section, with visibility tied to view selection.

### 6. Shell visibility is still computed from one active shell page plus singleton section ids
`src/gu_toolkit/figure_layout.py:2192-2249` computes:

- `_visible_shell_page_ids`
- `_active_shell_page_id`
- `active_sections`
- per-page `display` values

and then toggles `legend_panel`, `params_panel`, and `info_panel` based on which singleton section ids are active on the selected page.

That is a page-switching mechanism over singleton section types. It is not yet a general visibility lifecycle for peer section instances.

### 7. Display transport is still notebook-specific
`src/gu_toolkit/figure_layout.py:629-635` materializes display by wrapping `root_widget` in `OneShotOutput`.

`src/gu_toolkit/Figure.py:3818-3901` then calls `display(self._layout._materialize_display_output())` in `_ipython_display_()` and `show()`.

That works for notebooks, but it is not a mount-surface contract for standalone HTML slots.

### 8. The repository already has the right browser-side visibility boundary inside `PlotlyPane`
`src/gu_toolkit/PlotlyPane.py:643-655` computes DOM host visibility using browser state.

`src/gu_toolkit/PlotlyPane.py:942-952` explicitly waits for visibility and measurable geometry before resizing.

This is important evidence: the repo already contains the correct low-level boundary for DOM-owned visibility. The shell should align with that instead of inventing a parallel Python-only visibility system.

### 9. The render pipeline already has a useful “active now, stale later” pattern
`src/gu_toolkit/figure_diagnostics.py:411-456` renders the current view immediately and marks non-current views stale on parameter changes.

That is a strong hint for the revised shell design:

- hidden plot-bearing sections should not necessarily render immediately,
- they can be marked dirty / stale,
- and refreshed when they become visible.

## Symptoms

The current design produces these symptoms:

- multiple legends and multiple info sections are structurally awkward or impossible
- layout flexibility still depends on singleton shell sections
- legend and info behavior are still view-centric even though the shell should not be
- shell tabs / pages are still too tied to Python-side page selection over singleton sections
- standalone HTML is still blocked by notebook-specific display materialization
- Plotly visibility / sizing logic is stronger than the shell model above it, so the shell is still fighting the best existing sizing boundary

## Core source of the problem

The core source is **not** just “the legend is on the wrong side” or “the layout needs more flags.”

The real structural source is now this three-part mismatch:

### A. The shell still thinks in singleton section categories
The current architecture still assumes one legend section, one info section, one parameters section, and one stage page.

That makes later layout work harder because the shell cannot naturally represent multiple peer sections.

### B. View identity still leaks into shell section behavior
The plotting runtime may continue to use views internally, but the shell model should not use active-view membership as the organizing rule for legend or info visibility.

### C. Visibility and transport are still too Python / notebook owned
The current shell still centers Python-side page selection and notebook display materialization, even though the existing Plotly driver already uses DOM visibility and measured geometry as the truth.

These are structural boundaries, not surface symptoms.

## Why this identifies the root cause rather than a symptom

A stopgap fix would look like one of these:

- keep `_VALID_SECTION_IDS` and add more singleton section names
- add more shell presets for more singleton arrangements
- build a generic tabs / navigation presenter hierarchy without fixing singleton sections
- make legend / info “attached to plots” as hard ownership
- keep active-view filtering and only add more exceptions
- solve HTML with a custom parallel UI
- push more width / height values from Python

Those would still leave the real issue in place:

- the shell would still not have peer section instances,
- layout would still not be free to place sections arbitrarily,
- and visibility would still not line up with the DOM-driven sizing/runtime boundary already present in `PlotlyPane`.

## Recommended solution

### 1. Preserve the current view runtime, but stop using views as the shell primitive
`View`, `ViewManager`, and `PlotlyPane` remain important internal runtime pieces.

But the shell should no longer be organized around “active view decides which legend / info exists.”

Views stay internal to plotting. The shell moves to section instances.

### 2. Introduce a peer section registry
Create an internal registry of section instances. Each section instance should have at least:

- a stable section id
- a section kind (`stage`, `legend`, `info`, `parameters`, `output`, ...)
- controller / state ownership
- a stable widget surface root
- optional association metadata
- optional default placement hints

This is the level that can support:

- multiple legends
- multiple info-card sections
- multiple plot-bearing sections later
- conventional layouts and deliberately weird layouts

### 3. Treat associations as soft metadata
A legend or info section may declare that it is naturally associated with:

- one plot id
- a plot group
- a semantic tag
- or some other higher-level content group

But that association must not create parent/child ownership.

The default layout builder may use associations to co-locate related sections. The shell spec is still allowed to override that and place sections arbitrarily.

### 4. Split parameter handling into controller/state versus widget surface
Parameter logic should own:

- registry
- refs
- render-trigger semantics
- custom binding policy

The widget surface should own:

- concrete control widgets
- modal host wiring
- stable widget roots
- ordering inside parameter sections

### 5. Split legend handling into controller/state versus widget surface
Legend logic should own:

- plot membership / ordering
- row state
- style state
- sound state
- editor intent

The widget surface should own:

- row widgets
- toolbar widgets
- dialog widgets
- anywidget bridges
- stable widget roots
- modal placement

The new legend controller must be keyed by declared plot membership or other explicit section inputs, not by `active_view_id`.

### 6. Promote info content into the peer-section model
Info cards and raw outputs can no longer remain only as children of one singleton info box.

They do not need a giant new architecture, but they must become promotable into **section instances** so the shell can place multiple info sections independently.

### 7. Make shell visibility a presentation responsibility
Notebook and HTML shells should decide who is visible.

That means:

- page tabs / buttons are shell controls, not a major standalone subsystem
- hidden sections stay mounted where practical
- visible / hidden transitions are shell lifecycle events
- the shell does not need a big presenter hierarchy just to render tabs in multiple styles

### 8. Add notebook and HTML mount surfaces over the same section registry
The same section widget roots should be mountable into:

- notebook widget containers, and
- HTML `<div>` slots.

That creates a real transport boundary without duplicating UI logic.

### 9. Reuse the existing PlotlyPane visibility boundary
The existing `PlotlyResizeDriver` already knows how to:

- detect whether the DOM host is visible
- wait for measurable geometry
- resize only when the host is ready

The revised shell should emit visibility / geometry intent and let `PlotlyPane` continue to own browser measurement.

### 10. Defer hidden plot work and refresh on visible transitions
The render pipeline already has a stale-marking pattern for inactive views.

Generalize that idea so hidden plot-bearing sections can:

- skip immediate expensive render work while hidden
- be marked dirty / stale
- refresh and reflow when they become visible again

## Why this approach is the best fit

### It solves the actual modeling problem
The central problem is no longer just shell layout flexibility. It is that the shell needs **peer section instances** with soft associations. This approach introduces exactly that boundary.

### It matches the requested flexibility without enforcing bad structure
The model allows the common case:

- plot + associated legend + associated info cards

without enforcing it as ownership. That is exactly the requested behavior.

### It aligns with the strongest existing browser/runtime code
`PlotlyPane` already trusts DOM visibility and measured size. Making the shell visibility presentation-owned is therefore not speculative; it aligns the shell with the best code path already in the repo.

### It does not rewrite unrelated systems
This approach mainly touches:

- shell section modeling
- section controller / widget-surface boundaries
- mount surfaces
- visibility lifecycle / reflow triggers

It does **not** require rewriting plotting, sampling, code generation, or `PlotlyPane` itself.

## Alternatives rejected

### Rejected: a generic navigation / presenter hierarchy as the center of the design
Tabs and page buttons are just shell controls over visibility. They are not important enough to deserve a large independent abstraction stack.

### Rejected: plot-subordinate legends or info cards
That would enforce ownership that the user explicitly does not want.

### Rejected: extending the singleton section-id shell model
More singleton ids or more shell presets would still avoid the real problem.

### Rejected: a separate custom HTML UI
That would duplicate the live widget stack and violate the stated requirement.

### Rejected: Python-driven width / height sizing
The browser is still the source of truth for geometry. `PlotlyPane` already proves that.

## Scope discipline / non-goals

This project is **not** a rewrite of the whole package.

It should not:

- rewrite `View` / `ViewManager`
- replace `PlotlyPane`
- replace Plotly rendering
- rewrite plot normalization or code generation
- build a parallel custom DOM UI
- force plot / legend / info into parent/child ownership
- remove legacy view APIs from the public surface unless that becomes necessary later

## Project phases

1. [Phase 001 - architecture and boundaries](project-057-phase-001-architecture-and-boundaries.md)
   - define the internal contracts and narrow notebook-specific ownership
2. [Phase 002 - slot-based shell and arrangement spec](project-057-phase-002-slot-based-shell-and-arrangement-spec.md)
   - introduce the first shell presets and page regions as a stepping stone
3. [Phase 003 - filter-driven legends, parameter presentations, and mount management](project-057-phase-003-parameter-legend-and-tabs-presentation-split.md)
   - replace view-driven shell behavior with explicit filters over global plots/parameters and split state from presentation
4. [Phase 004 - Jupyter shell surface and default-layout migration](project-057-phase-004-jupyter-presenters-and-default-layout-migration.md)
   - migrate notebook behavior onto the peer-section model and a notebook mount surface
5. [Phase 005 - HTML PyScript live widget shell surface](project-057-phase-005-html-pyscript-live-widget-runtime.md)
   - support standalone HTML with live widget mounting into responsive external slots
6. [Phase 006 - visibility lifecycle, Plotly sizing, and validation](project-057-phase-006-plotly-sizing-and-validation.md)
   - harden hidden / visible behavior, reflow, and validation across supported environments

## Acceptance criteria

- [ ] Parameter handling has an explicit controller/state versus widget-surface boundary.
- [ ] Legend handling has an explicit controller/state versus widget-surface boundary.
- [ ] The shell model supports multiple legend sections and multiple info sections/cards as peer items.
- [ ] Associations between plots and companion sections are soft metadata, not enforced ownership.
- [ ] Shell arrangement is driven by a section-instance registry plus layout spec rather than one fixed singleton sidebar contract.
- [ ] The default layout remains functionally close to the current one, except the full-width toggle is gone.
- [ ] JupyterLab remains supported.
- [ ] JupyterLite + Pyodide remains supported.
- [ ] Standalone HTML + inline PyScript + Pyodide can mount the same live widget sections into HTML slots.
- [ ] Plotly respects the currently visible layout region in every supported arrangement.
- [ ] Hidden plot-bearing sections can defer expensive work and then refresh / reflow when they become visible.
- [ ] The implementation reuses the existing widget/runtime infrastructure instead of creating a parallel custom UI system.
