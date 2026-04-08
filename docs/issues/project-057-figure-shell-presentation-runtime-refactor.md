# Project 057: Figure shell presentation/runtime refactor

## Status
Proposed

## Summary
Refactor the figure shell so `Figure`, parameter management, legend handling, and tab/navigation handling each have a **logic half** and a **presentation half**, while preserving the existing stable per-view plotting runtime.

The end state must support three environments with the same core figure logic:

- JupyterLab (already working today)
- JupyterLite + Pyodide (already working today)
- standalone HTML with inline PyScript + a Pyodide kernel + an injected **live widget runtime**

The preferred implementation is **not** a custom DOM rewrite. The preferred implementation is a slot-based shell that reuses live `ipywidgets`/`anywidget` components and can either:

1. compose them inside notebook widget containers, or
2. mount the same section-root widgets into named HTML `<div>` slots controlled by responsive CSS.

That approach directly matches the requirement for flexibility without hand-rolling the entire widget stack.

## Hard requirements

1. `Figure`, parameter manager, legend, and tabs/navigation must each have separate but coexisting logic and presentation responsibilities.
2. The arrangement of panels must be declarative and configurable.
3. Legend placement must support at least:
   - hidden
   - left of the figure
   - right of the figure
   - below the figure
   - separate tab/page from the figure
4. Plotly must obey the size of the active layout region.
5. The default layout must remain functionally close to the current one, except the inline full-width toggle should disappear.
6. The refactor must improve maintainability and boundaries rather than adding more one-off widget wiring.
7. The solution must preserve the live widget model instead of replacing it with custom HTML controls.

## General instructions

- Preserve the current strengths of the architecture:
  - one stable `View` runtime per view
  - one stable `PlotlyPane` per view
  - browser-measured Plotly sizing through the existing pane/driver model
- Treat the current fixed right-sidebar layout as an implementation detail to replace, not as the long-term API.
- Prefer internal protocols, presenters, slot hosts, and layout specs over more boolean flags in `FigureLayout`.
- Reuse existing toolkit UI primitives where possible, especially shared section chrome and tab helpers.
- Do not rewrite plotting, view state, sampling, code generation, or unrelated notebook helpers.
- Do not switch away from `ipywidgets`/`anywidget` unless a concrete requirement forces it.
- Do not solve the HTML requirement with static embedding. The HTML target explicitly requires a live Pyodide-backed widget runtime.
- Keep public authoring APIs stable unless a new layout/presentation option genuinely needs a small extension.

## Evidence of the current problem

### 1. The shell layout is hard-coded to one composition
`src/gu_toolkit/figure_layout.py:249-423` builds a single widget tree with:

- title bar
- `view_selector`
- `view_stage`
- one `sidebar_container`
- `legend_panel`, `params_panel`, and `info_panel` stacked inside that sidebar
- `print_area` below everything

That is a concrete notebook presentation, not a reusable layout policy.

### 2. Sidebar visibility is encoded as one fixed right-side policy
`src/gu_toolkit/figure_layout.py:766-856` implements `update_sidebar_visibility(...)` by toggling display on the legend/parameter/info panels and then showing or hiding **one** `sidebar_container`.

That means the current shell can only answer one question: “is there a sidebar on the right?” It cannot express “legend below”, “legend in a separate tab”, or “legend hidden while parameters stay visible in a right column” without further hard-coded branches.

### 3. `Figure` passes concrete presentation containers into logic-heavy managers
`src/gu_toolkit/Figure.py:414-468` wires the figure like this:

- `ParameterManager(..., self._layout.params_box, modal_host=self._layout.root_widget)`
- `InfoPanelManager(self._layout.info_box)`
- `LegendPanelManager(self._layout.legend_box, modal_host=self._layout.root_widget, root_widget=self._layout.root_widget, header_toolbar=self._layout.legend_header_toolbar, ...)`

This proves the figure orchestration layer is coupled to one concrete widget composition contract.

### 4. Parameter management currently mixes registry logic and direct widget placement
`src/gu_toolkit/figure_parameters.py:198-374` shows `ParameterManager` doing all of the following inside one class:

- registry/state ownership for parameter refs
- default control creation (`FloatSlider`)
- control-to-ref binding
- render callback dispatch
- direct mutation of `self._layout_box.children`
- direct modal host attachment

That is a logic/presentation collapse, not a modular boundary.

### 5. Legend management currently mixes plot state, rows, dialog chrome, and layout mutation
`src/gu_toolkit/figure_legend.py:772-1012` and `src/gu_toolkit/figure_legend.py:1518-1587` show `LegendPanelManager` owning:

- plot ordering and active-view filtering
- row models
- row widget creation
- toolbar creation
- style dialog creation
- anywidget context bridge creation
- modal overlay hosting
- direct mutation of `layout_box.children`
- optional mutation of `header_toolbar.children`

This is exactly the kind of boundary collapse that makes later placement changes expensive and brittle.

### 6. “Tabs” are not yet a real independent presentation concept
`src/gu_toolkit/figure_layout.py:1598-1760` shows `set_view_tabs(...)` and `observe_tab_selection(...)` are compatibility wrappers over the current `view_selector` implementation. In practice, the current “tabs” are just one `ToggleButtons` strip for view selection.

That is not enough to support a shell-level “Figure / Legend / Parameters” tab region while also keeping per-view selection.

### 7. The display lifecycle is notebook-only
`src/gu_toolkit/figure_layout.py:538-587` returns a new `OneShotOutput` and displays `root_widget` into it. `src/gu_toolkit/Figure.py:3800-3883` then uses `display(self._layout.output_widget)` in both `_ipython_display_()` and `show()`.

That works for notebooks, but it is not a transport-neutral mount contract for standalone HTML.

### 8. Pyodide support exists, but standalone HTML widget-runtime support does not
`src/gu_toolkit/runtime_support.py:424-705` already understands Pyodide/browser timing backends, and `src/gu_toolkit/runtime_support.py:708-854` already probes Plotly FigureWidget support. However, the repository contains no standalone HTML widget manager/bootstrap layer, no HTML slot mount surface, and no live widget runtime injection helper.

This means the repository already supports a Pyodide-like runtime at the scheduler/runtime level, but not yet at the standalone HTML display/mount level.

### 9. Existing tests encode the fixed shell assumptions
For example:

- `tests/test_project030_phase1_layout.py` asserts the sidebar contains legend, params, info in that fixed order.
- `tests/test_project030_phase3_figure_wiring.py` asserts legend visibility is represented through the sidebar.
- `tests/test_project019_phase12.py` asserts the current view-selector behavior.

These tests are useful evidence: they show the current structure is not only implemented but also baked into the current test contract.

## Symptoms

The current design produces exactly the symptoms described by the user:

- layout flexibility requires shell rewrites instead of configuration
- legend placement is trapped inside one sidebar policy
- parameter and legend code are harder to test without concrete widget boxes
- tabs are too narrow a concept to represent shell pages
- HTML + PyScript cannot be supported cleanly because display is tied to IPython display output rather than mount surfaces
- Plotly sizing risks recurring whenever a new shell arrangement is introduced, because geometry changes are currently tied to one notebook layout tree

## Core source of the problem

The core source is **not** “legend is on the wrong side” or “the layout needs more flags.”

The core source is that the current architecture collapses three separate concerns into the same classes and APIs:

### A. Section logic is collapsed into section presentation
Parameter/legend/tab state and behavior are mixed with widget creation, widget parenting, and UI chrome.

### B. Layout policy is collapsed into one concrete notebook widget tree
The current `FigureLayout` is both the shell policy and one specific notebook presentation. Because those are the same thing, introducing another arrangement means editing the same class that owns the current shell.

### C. Display transport is collapsed into IPython display
Notebook display, widget hosting, and layout composition all currently assume “display a root widget in a notebook output area.” That assumption is precisely what breaks the standalone HTML requirement.

These are structural sources, not surface symptoms.

## Why this identifies the root cause rather than a symptom

A stopgap fix would look like one of these:

- add more booleans to `FigureLayout` for “legend_bottom”, “legend_left”, “legend_tab”, etc.
- add more special cases to `LegendPanelManager.refresh()`
- keep passing `layout_box` everywhere and just re-parent widgets more often
- add a separate HTML-only shell that duplicates notebook widget logic
- push more explicit `fig.update_layout(width=..., height=...)` calls into Python every time the shell changes

Those approaches would treat the symptom (“I want more arrangements”) while keeping the actual source untouched (“logic, presentation, and transport are fused”).

The correct approach is to break the fused boundary once and then let different presentations reuse the same section logic.

## Recommended solution

### 1. Keep the existing stable per-view plotting runtime
Preserve the current `View`/`ViewManager`/`PlotlyPane` architecture.

That part of the repository is already a strength:

- one stable plotting runtime per view
- one stable pane per view
- explicit browser-driven sizing in `PlotlyPane`
- view activation as a distinct concept

The shell refactor should build around that rather than replacing it.

### 2. Introduce a slot-based shell model
Create a small internal shell specification that describes **what goes where**, independently of notebook widget composition.

The exact class names can vary, but the boundary should exist. Example concepts:

- `FigureShellSpec`
- `FigureArrangement`
- `ShellRegion`
- `SectionPlacement`
- `FigureDisplaySurface`

The shell spec should describe regions such as:

- title
- view navigation
- figure stage
- legend
- parameters
- info
- output
- optional shell tab/page region

This is the right level for saying:

- legend is hidden
- legend is below the stage
- legend is in the right column
- legend is in a separate shell tab
- parameters and info remain in the right column
- HTML presentation uses external div slots

### 3. Split each major area into controller/state vs presenter
The exact names can vary, but the architectural rule should be explicit.

#### Figure
- **Logic:** orchestration, view activation, render/reflow requests, plot lifecycle coordination.
- **Presentation:** shell composition, slot mounting, notebook display surface, HTML mount surface.

#### Parameters
- **Logic:** parameter registry, refs, hooks, render-trigger semantics, custom-control binding policy.
- **Presentation:** built-in control factories, control wrappers, section chrome, root widget list, modal host wiring.

#### Legend
- **Logic:** plot ordering, active-view filtering, legend row state, style state, sound state, editor-intent state.
- **Presentation:** row widgets, labels/toggles, toolbar, dialog, anywidget bridge, modal overlay, section root.

#### Tabs / navigation
- **Logic:** selected item, available tabs/pages, tab descriptors, activation callbacks.
- **Presentation:** `ToggleButtons`, toolkit tab buttons, `build_tab_bar(...)`, `TabListBridge`, page visibility widgets.

This split is what creates maintainable boundaries.

### 4. Reuse the existing widget ecosystem instead of hand-rolling UI
The repository already has presentational building blocks worth reusing:

- shared section chrome from `ui_system.py`
- `build_tab_bar(...)` in `src/gu_toolkit/ui_system.py:1387-1447`
- `TabListBridge` in `src/gu_toolkit/widget_chrome.py:384-573`
- modal host helpers in `ui_system.py` / `widget_chrome.py`
- anywidget-based bridges already used by Plotly, legend, sliders, sound, and math input

This directly supports the user’s requirement to keep using widgets rather than rewriting the UI from scratch.

### 5. Use stable section-root widgets as the reusable presentation unit
Each presenter should expose one stable root widget (or a small stable widget bundle) that can be mounted into a shell slot.

That supports both target environments:

- **Notebook/Jupyter presentation:** compose the roots inside `VBox`/`HBox`/`Box` containers.
- **Standalone HTML presentation:** mount the same roots into named `<div>` slots using a live widget manager.

This is the best fit for the user’s suggestion that different output/widgets be constrained to different divs in responsive HTML.

### 6. Add a real display-surface abstraction
The figure needs a transport boundary now because there is finally a real second transport target.

The repository’s own earlier architecture notes correctly warned against adding a `FigureUIAdapter` too early. That warning no longer applies here, because the standalone HTML + PyScript target is a concrete new display transport.

The figure should no longer assume that “displaying” means only:

- create a one-shot notebook `Output`
- call `IPython.display.display(...)`

Instead, it should route presentation through a display surface / mount surface abstraction such as:

- notebook cell surface
- notebook reusable root widget surface
- HTML slotted surface

### 7. Add a standalone HTML live widget runtime bootstrap
For standalone HTML, the correct solution is a real widget runtime bootstrap, not fake rendering.

That bootstrap must:

- initialize a live widget manager in the PyScript/Pyodide page
- load `anywidget`-backed widgets correctly
- mount widget views into supplied DOM targets
- support the toolkit’s anywidget-based pieces (`PlotlyResizeDriver`, legend bridges, slider modal bridges, tab bridges, etc.)

This is the critical missing piece for the HTML target.

### 8. Keep Plotly sizing in `PlotlyPane`, but broaden the reflow contract
Do **not** move sizing responsibility into ad-hoc Python layout width/height code.

The browser still owns real measured geometry, so `PlotlyPane` remains the right sizing boundary. What needs to change is the reflow contract:

- shell arrangement changes must emit geometry-change events
- shell-tab switches must emit geometry-change events
- legend/parameter/info occupancy changes must emit geometry-change events
- HTML mount completion and external div resizes must emit geometry-change events
- those events must trigger the active pane’s reflow in a transport-neutral way

That is how Plotly will stay aligned with the new shell arrangements.

## Why this approach is the best fit

### It solves the actual transport problem
The HTML requirement is not just “another layout preset.” It is a new display transport. A display-surface boundary is justified now.

### It avoids hand-rolling widgets
The same live widget components can be reused in Jupyter and HTML. That is exactly what the user asked for.

### It localizes the shell problem
The refactor mainly touches:

- figure shell composition
- section controller/presenter boundaries
- display/mount surfaces
- geometry/reflow signaling

It does **not** require rewriting plotting, view state, or the Plotly pane architecture.

### It scales to future layouts cleanly
Once the shell is slot-based, new layouts become spec/presenter work rather than more deep wiring through `FigureLayout`, `LegendPanelManager`, and `ParameterManager`.

## Alternatives rejected

### Rejected: extend `FigureLayout` with more booleans
That would keep layout policy fused to one widget tree and would become harder to reason about with every new arrangement.

### Rejected: build a separate custom HTML UI
That would duplicate the existing widget logic and violate the user’s desire to avoid hand-rolling the entire UI stack.

### Rejected: static widget embedding
The HTML requirement explicitly calls for a live Pyodide-backed widget runtime.

### Rejected: solve sizing by pushing more pixel values from Python
The browser is still the source of truth for actual geometry. The existing `PlotlyPane` approach should be preserved and integrated with a better shell reflow contract.

## Scope discipline / non-goals

This project is **not** a rewrite of the entire package.

It should not:

- rewrite `View` / `ViewManager`
- replace `PlotlyPane`
- reimplement Plotly rendering
- rework plot normalization, code generation, or sound generation logic unless required for widget hosting boundaries
- force the info panel into the same logic/presentation split in the first pass
- change the mathematical authoring surface
- hide the problem under CSS hacks or transport-specific one-offs

The info panel is adjacent to this refactor because it occupies shell space, but it is not the primary target of the requested split. Use generic shell-slot abstractions so info can continue to work without turning this project into a broad rewrite.

## Project phases

1. [Phase 001 - architecture and boundaries](project-057-phase-001-architecture-and-boundaries.md)
   - define the internal contracts, migration map, and transport boundary before moving code
2. [Phase 002 - slot-based shell and arrangement spec](project-057-phase-002-slot-based-shell-and-arrangement-spec.md)
   - replace the fixed sidebar shell with declarative regions and placements
3. [Phase 003 - parameter, legend, and tabs logic/presentation split](project-057-phase-003-parameter-legend-and-tabs-presentation-split.md)
   - separate section state/controllers from widget presenters
4. [Phase 004 - Jupyter presenters and default-layout migration](project-057-phase-004-jupyter-presenters-and-default-layout-migration.md)
   - preserve JupyterLab/JupyterLite behavior on the new shell/presenter boundaries
5. [Phase 005 - HTML PyScript live widget runtime](project-057-phase-005-html-pyscript-live-widget-runtime.md)
   - support standalone HTML with live widget mounting into responsive div slots
6. [Phase 006 - Plotly sizing and validation](project-057-phase-006-plotly-sizing-and-validation.md)
   - harden reflow behavior and verify all supported arrangements/environments

## Acceptance criteria

- [ ] `Figure`, parameter management, legend handling, and tabs/navigation all have explicit logic/presentation boundaries.
- [ ] Shell arrangement is driven by a spec/presenter layer rather than one fixed sidebar implementation.
- [ ] The default layout remains functionally equivalent to the current layout except the full-width toggle is gone.
- [ ] Legend placement can be configured to hidden, left, right, bottom, and separate tab/page modes.
- [ ] JupyterLab remains supported.
- [ ] JupyterLite + Pyodide remains supported.
- [ ] Standalone HTML + inline PyScript + Pyodide can mount the same live widget sections into HTML slots.
- [ ] Plotly respects the active layout region in every supported arrangement.
- [ ] The implementation reuses existing widget/runtime infrastructure instead of creating a parallel custom UI system.
