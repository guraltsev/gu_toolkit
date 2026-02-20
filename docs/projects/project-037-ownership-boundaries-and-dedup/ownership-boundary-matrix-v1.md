# Project 037 — Ownership Matrix v1 and Boundary Rules (`Figure.py` ecosystem)

## Status

**Draft published for external architecture review**

## Scope and intent

This document delivers the first revision of:

1. ownership boundaries for `Figure.py` orchestration methods and key collaborators, and
2. boundary rules (allowed/forbidden dependency directions) to reduce duplication and prevent architectural drift.

This is an execution artifact for project-037 and is intentionally implementation-adjacent so project-033 (dedup) and project-023 (package reorg) can consume it directly.

---

## Step 1 — Ownership matrix revision v1

### Ownership domains used in this matrix

- **Figure Orchestrator (`Figure`)**: cross-component coordination, public API surface, view lifecycle, render triggering.
- **View runtime (`ViewManager`, `View`, `_ViewRuntime`)**: per-view workspace/runtime creation, active view selection.
- **Layout (`FigureLayout`)**: widget composition, frame/sidebar arrangement, visibility synchronization.
- **Parameters (`ParameterManager`, `ParamRef`, `ParamEvent`)**: parameter registration, controls, snapshot and change hooks.
- **Plot runtime (`Plot`, normalization/style modules)**: expression binding, per-plot update/render behavior, style resolution.
- **Info and legend (`InfoPanelManager`, `LegendPanelManager`)**: informational output and legend control surfaces.
- **Platform adapters (`PlotlyPane`, `go.FigureWidget`, `InputConvert`)**: notebook rendering shell and value normalization.

### Method-level ownership matrix (first revision)

| Area | Representative API/methods in `Figure.py` | Current owner | Target owner | Action | Boundary rationale | Approval |
| --- | --- | --- | --- | --- | --- | --- |
| Figure construction + collaborator wiring | `Figure.__init__`, `_create_view_runtime`, `_runtime_for_view` | `Figure` | `Figure` (thin orchestrator) + factories in collaborators | **retain + thin** | Keep orchestration in one place, but push object-specific setup into owning collaborator factories where possible. | Approved |
| Workspace/view lifecycle | `add_view`, `set_active_view`, `view`, `remove_view`, `active_view_id`, `views` | `Figure` + `ViewManager` | `ViewManager` as owner, `Figure` as façade | **move (internals)** | View concerns should stay out of plot/parameter logic; API remains on `Figure` for notebook ergonomics. | Approved |
| Layout/sidebar synchronization | `_sync_sidebar_visibility`, `title` property accessors, display wrapper calls | `Figure` + `FigureLayout` | `FigureLayout` authoritative | **move (logic), retain (entrypoints)** | Layout policy belongs to layout layer; `Figure` should call intent-level methods only. | Approved |
| Plot host access | `figure_widget`, `figure_widget_for`, `pane`, `pane_for` | `Figure` | `View runtime` owner exposed through `Figure` | **retain façade** | Keeps stable public API while runtime ownership is explicit in view layer. | Approved |
| Parameter API | `parameter`, `add_param`, `parameters`, `params`, `add_param_change_hook`, `snapshot` | `Figure` + `ParameterManager` | `ParameterManager` authoritative | **retain façade + delegate** | Parameter semantics must be centralized for dedup/error consistency. | Approved |
| Range and viewport state | `x_range`, `y_range`, `_viewport_x_range`, `_viewport_y_range`, `current_x_range`, `current_y_range` | Mixed (`Figure`, Plotly widget state, InputConvert) | `View` Each view has its own default "home" range. Each view has its current viewport range. Clarify difference between these methods and collapse. TODO: revise this decision.  | **significant repactor** TODO: clarify | TODO: revise  | REVISE |
| Sampling policy | `sampling_points` property | `Figure` | `View` Each view has its own default sampling policy | TODO: revise | Sampling is view-level render policy consumed by plots. | REVISE |
| Plot registration and style normalization | `plot`, `plot_style_options` | `Figure` + style/normalization modules + `Plot` | Plot module exposes registry and single `Plot` class. Figure exposes registry and forwards plot queries to registry. | TODO: revise | API continuity requires `Figure.plot`; internals should remain in dedicated plot modules. | REVISE |
| Render orchestration | `render`, `_throttled_relayout`, `_run_relayout`, `_log_render` | `Figure` | `Figure` orchestrator + debouncer utility | TODO: revise | Render triggering is cross-cutting; `Figure` is responsible for wiring hooks and between components. Is this a good idea? See also Hook Management | REVISE |
| Info panel/public info hooks | `info`, `info_output` | `Figure` + `InfoPanelManager` | `InfoPanelManager` authoritative | **retain façade + delegate** | Info surface should be pluggable and isolated from render/control plane internals. | Approved |
| Hook management | `add_hook` and wrappers | `Figure` + `ParameterManager` | `ParameterManager` for param hooks; `Figure` for render hooks | **split ownership** | Prevent one generic hook channel from becoming a God-object; classify by trigger domain. | REVISE |
| Notebook integration/context | `_ipython_display_`, `__enter__`, `__exit__` + figure context imports | `Figure` + `figure_context` | same | **retain** | Notebook protocol and active-figure context are orchestrator-facing concerns. | Approved |
| Code generation/export | `to_code`, `code`, `get_code` | `Figure` + `CodegenOptions`/snapshot | `Figure` API + dedicated codegen module for heavy logic | **retain façade + move heavy logic** | Keep UX simple while extracting non-UI transformation logic for reuse/testing. | Approved |

### Key collaborator ownership summary

| Collaborator | Owns | Must not own |
| --- | --- | --- |
| `Figure` | Cross-domain orchestration, public façade, render and lifecycle coordination | Widget-tree internals, low-level parameter state store, per-plot numeric algorithms |
| `FigureLayout` | Layout tree, sidebar visibility behavior, display composition | Parameter semantics, plot evaluation decisions |
| `ParameterManager` | Parameter registry, controls, snapshots, param events and observers | Plot rendering loop, layout policy |
| `Plot` (+ normalization/style helpers) | Plot-level expression/runtime conversion and trace update behavior | Global view lifecycle, notebook display lifecycle |
| `ViewManager` / `View` | View definitions, active-view resolution, per-view runtime addressing | Plot math, parameter registry |
| `InfoPanelManager` / `LegendPanelManager` | Sidebar informational components and legend control behavior | Core render trigger policy |
| `PlotlyPane` | Plotly container and resize behavior | Figure business logic |

---

## Step 2 — Boundary-rule table (allowed/forbidden directions)

### Direction legend

- `A -> B` means module/domain `A` may depend on `B`.
- “Forbidden” means no direct calls/imports; use façade or event contract.

| Rule ID | Direction | Status | Why |
| --- | --- | --- | --- |
| BR-01 | `Figure` -> `FigureLayout`, `ParameterManager`, `InfoPanelManager`, `LegendPanelManager`, `ViewManager`, `Plot` | **Allowed** | `Figure` is orchestration root and may coordinate all collaborators. |
| BR-02 | `FigureLayout` -> `Figure` | **Forbidden** | Prevent circular orchestration and layout-driven business logic creep. |
| BR-03 | `ParameterManager` -> `Figure` | **Forbidden** | Parameter subsystem emits events/returns snapshots; it must not trigger orchestration directly. |
| BR-04 | `Plot` -> `ParameterManager` (read-only snapshot/contracts). Upon creating, plot gets provided a Parameter context provider. In does not know that it is the ParameterManager. It just has to expose the snapshot protocol. This protocol should get registered with all NumericFunctions. REVISE | **Allowed (contract-only)** | Plot runtime may consume normalized parameter values via stable interfaces. |
| BR-05 | `Plot` -> `FigureLayout` | **Forbidden** | Rendering math/runtime should not depend on widget layout tree. |
| BR-06 | `InfoPanelManager`/`LegendPanelManager` -> `ParameterManager` (through contract API). See BR-04 convention.t APIs) | **Allowed (read + observe)** | Sidebar components can reflect state but must not mutate via hidden coupling. |
| BR-07 | `ViewManager` -> `Plot` / `ParameterManager` internals | **Forbidden** | View layer handles routing/runtime lookup only, not domain logic. |
| BR-08 | Any collaborator -> `Figure` private methods | **Forbidden** | Keep private orchestrator internals one-way and prevent back-edge drift. |
| BR-09 | Shared utility modules (`InputConvert`, style normalization, debouncing) -> domain modules | **Forbidden (reverse import)** | Utilities remain reusable and acyclic; domain modules may depend on utilities, not vice versa. |
| BR-10 | Notebook/display adapters (`PlotlyPane`) -> orchestration/policy modules | **Forbidden** | Adapter layer should stay platform-focused and policy-agnostic. |

### Allowed interaction patterns

1. **Facade delegation:** user-facing call enters `Figure`, which delegates to owner collaborator.
2. **Event/observer propagation:** parameter changes flow as `ParamEvent`/hook notifications, not back-calls into random subsystems.
3. **Snapshot transfer:** plots consume immutable or stable parameter snapshots rather than live widget internals.
4. **View-scoped runtime access:** view switching resolves through `ViewManager` + runtime records, then consumed by `Figure`.

### Forbidden interaction patterns (anti-pattern list)

- Layout component directly mutates plot registry.
- Plot internals read/write widget tree state.
- Parameter widgets call `Figure.render()` from inside control implementation code paths without a manager-level contract.
- Collaborators importing `Figure` for helper shortcuts.
- Utility modules importing orchestrator/collaborators.

---

## Review notes for project-033 and project-023 consumers

- **For dedup work (033):** prioritize range normalization, hook registration semantics, and codegen/snapshot extraction where ownership is “retain façade + move heavy logic.”
- **For package reorg (023):** preserve directionality above when choosing destination packages; reject moves that introduce back-edges.

## External review checklist (required before status upgrade)

- [ ] Confirm matrix rows cover all public `Figure` methods and major orchestration helpers.
- [ ] Confirm BR-01..BR-10 are compatible with project-035 invariants.
- [ ] Confirm at least one candidate dedup cluster is selected from “merge helper logic” / “split ownership” rows.
- [ ] Confirm no proposed ownership move requires immediate breaking API changes.

