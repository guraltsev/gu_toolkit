# Project 019: Tabbed Multi-Plot Interface (Refined Implementation Plan)

**Companion document:** `summary.md`

---

## 1) Objective and success criteria

### Objective
Implement a multi-view plotting workspace where one `Figure` owns shared parameters and info-sidebar infrastructure, while each view owns independent plot surface and range state.

### Success criteria
- Users can create multiple named views in tabs.
- Plots can belong to one or multiple views with stable IDs.
- Parameter changes render only active view(s); inactive views are marked stale and refresh once on activation.
- Info cards can be shared (all views) or view-scoped (active view only in the same sidebar region).
- Existing single-view usage remains simple and intuitive.
- Snapshot/codegen reflect the new view model.

---

## 2) Baseline constraints from current code

1. `Figure` currently builds one `FigureWidget` and one `PlotlyPane`; no notion of view collection.
2. `Plot` owns one `_plot_handle`; no membership graph.
3. `FigureLayout` currently has one plot container and one shared sidebar.
4. `InfoPanelManager` assumes one global info stream (card IDs only).
5. `FigureSnapshot` and code generation currently serialize a single-view shape.

These constraints define where refactors must happen.

---

## 3) Workstream A — Data model and state ownership

### A1. Introduce `View` model

Create a dedicated view model (class/dataclass) with:
- identity: `id`, `title`, `x_label`, `y_label`
- range state:
  - `default_x_range`
  - `default_y_range | None`
  - `viewport_x_range` (control-backed)
  - `viewport_y_range` (control-backed)
- render flags: `is_active`, `is_stale`
- UI handles: per-view `FigureWidget`, `PlotlyPane`, wrapper pane widgets

**Acceptance:** `Figure` can hold multiple views with independent axis states.

### A2. Workspace-level registry in `Figure`

Add view registry + active-view pointer:
- `self._views: dict[str, View]`
- `self._active_view_id: str`
- first default view created at init (with constructor `x_range`/`y_range` applying to this view only)

**Acceptance:** single-view flows continue to work through the default view.

### A3. Range behavior migration

Move current `_viewport_x_range` / `_viewport_y_range` semantics from figure-global to active-view delegated properties:
- `fig.x_range`/`fig.y_range` map to active view defaults
- `fig.current_x_range`/`fig.current_y_range` map to active view viewport

**Acceptance:** current range tests keep passing for default view; new tests prove per-view independence.

---

## 4) Workstream B — Plot membership and rendering primitives

### B1. Add explicit `Plot.id`

Ensure plot ID is first-class on `Plot` objects (not only dict key in `Figure.plots`).

### B2. Add `PlotHandle`

Implement `PlotHandle` as per-view trace runtime binding:
- `plot_id`
- `view_id`
- `trace_handle`
- optional cached x/y sampled arrays

### B3. Replace single handle with per-view handle map

In `Plot`:
- replace `_plot_handle` with `_handles: dict[str, PlotHandle]`
- add membership helpers:
  - `add_to_view(view_id)`
  - `remove_from_view(view_id)`
  - `views` property

### B4. Rendering API update

Update `Plot.render(...)` semantics:
- `render(view_id=...)` => render one membership target
- `render()` => render active-view memberships only

**Acceptance:** one plot can exist on multiple views and render independently.

---

## 5) Workstream C — Visibility-gated render pipeline

### C1. Parameter-triggered render behavior

On parameter changes:
- render active-view handles immediately
- mark all inactive views with matching plot memberships as stale

### C2. Tab activation behavior

When active tab changes:
- set new `active_view_id`
- if target view is stale, render once and clear stale flag
- trigger pane reflow/resize to avoid hidden-tab sizing issues

### C3. Per-view relayout callback/debouncer

Each view must have independent relayout event handling (x/y viewport updates and throttling), replacing the current figure-global relayout assumptions.

**Acceptance:** heavy parameter updates do not compute inactive views.

---

## 6) Workstream D — Layout and widget composition

### D1. Add tabbed plot container

Refactor `FigureLayout` to host an `ipywidgets.Tab` for views while preserving existing top title and sidebar shell.

### D2. Sidebar composition

Keep sidebar workspace-level:
1. parameters (shared)
2. shared info cards (always visible)
3. view-scoped info region (swapped on tab change)

### D3. Metadata rendering

Support:
- workspace title (existing behavior)
- per-view title (displayed above active pane)
- per-view axis labels (per view widget layout)

**Acceptance:** user can switch tabs and see correct plot + scoped info + labels.

---

## 7) Workstream E — Public API surface

### E1. View lifecycle API

Add:
- `fig.add_view(id, *, title=None, x_range=None, y_range=None, x_label=None, y_label=None)`
- `fig.remove_view(id)` is deferred (not part of this project scope)
- `fig.views` inspection helper

### E2. View context manager

Add `with fig.view("time"):` for context-targeted `plot(...)` and `info(...)` calls (equivalent to passing `view="time"`).

### E3. Plot targeting

Extend `Figure.plot(...)` and module helper `plot(...)` with `view: str | Sequence[str] | None`.

### E4. Info targeting

Extend `Figure.info(...)` and module helper `info(...)` with `view: str | None`:
- `None` => shared (visible on all views)
- `"id"` => scoped to that view

Keep rendering in one sidebar area where scoped cards swap with active tab/view.

Remove legacy helpers `fig.get_info_output()` and `fig.add_info_component()` with no compatibility bridge.

**Acceptance:** all new APIs have docstrings + examples and remain ergonomic in notebooks.

---

## 8) Workstream F — Snapshot, codegen, and migration compatibility

### F1. Snapshot schema extension

Evolve `FigureSnapshot` to represent:
- workspace metadata
- view list + active view
- per-view range/title/labels/autoscale state
- plot memberships
- shared + view-scoped info cards

### F2. Code generation update

Update `figure_to_code` pipeline so emitted code recreates view topology and scoped info cards.

### F3. Compatibility policy

Implement schema compatibility strategy (e.g., `schema_version`) while prioritizing clean multi-view semantics in current code generation paths.

**Acceptance:** snapshot and generated code round-trip for multi-view figures.

---

## 9) Workstream G — Testing and validation

### G1. Unit tests

- view creation, ID validation, and activation
- per-view default vs viewport range behavior
- autoscale policy (`y_range is None`)
- multi-view plot memberships and handle lifecycle
- parameter update active-only rendering
- stale-refresh-on-activation behavior
- shared vs scoped info visibility
- view-specific titles/axis labels

### G2. Regression tests

- keep/extend removal tests for old info helpers (`get_info_output`, `add_info_component`)
- confirm default single-view behavior remains unchanged

### G3. Integration checks

Notebook-driven checks for:
- time/frequency two-tab workflow
- shared parameter controls across tabs
- scoped info card visibility on tab switch

---

## 10) Explicitly deferred items from clarifications

- Per-view parameter dependency subsets for stale-mark filtering.
- Drag-and-drop plot reassignment across views.
- Non-tab multi-view layouts (e.g., side-by-side/grid).

---

## 11) Proposed implementation order

1. **A (model)**: view registry + range delegation foundation.
2. **B (plot handles)**: multi-view membership machinery.
3. **C (pipeline)**: stale/active render gating.
4. **D (layout)**: tab UI and scoped sidebar rendering.
5. **E (API)**: public methods/context wiring.
6. **F (snapshot/codegen)**: persistence + generated script parity.
7. **G (tests/docs)**: complete coverage and notebook examples.

This order minimizes risk by stabilizing runtime state before UI and serialization layers.

---


## 12) Consistent-state delivery phases (merge-safe checkpoints)

The following phases are explicit merge checkpoints; each checkpoint must leave the repository runnable and behaviorally coherent:

1. **Phase P1 — Internal view scaffolding (no UX change)**
   - Introduce `View` container and registry in `Figure`.
   - Keep all current APIs routed to the default view.
   - **Done criteria:** existing tests pass unchanged; no notebook breakage in single-view flows.

2. **Phase P2 — PlotHandle migration under compatibility layer**
   - Migrate `Plot` from single `_plot_handle` to per-view handle map.
   - Keep render behavior equivalent for the default view.
   - **Done criteria:** plot update/removal semantics unchanged in current tests.

3. **Phase P3 — Tab layout activation**
   - Add tab container and active-view selection plumbing.
   - Keep default figure rendering identical when only one view exists.
   - **Done criteria:** one-view notebooks render as before; two-view basic demo works.

4. **Phase P4 — Visibility-gated compute**
   - Activate stale marking and refresh-on-tab-activation logic.
   - Add performance-focused tests validating inactive-view non-rendering.
   - **Done criteria:** correctness parity + expected render suppression behavior.

5. **Phase P5 — Public API rollout**
   - Ship `add_view`, `view(...)`, and `view=` targeting in `plot/info`.
   - Finalize shared vs scoped info behavior in sidebar.
   - **Done criteria:** docs/examples/tests cover all new user-facing paths.

6. **Phase P6 — Snapshot/codegen and cleanup**
   - Add multi-view snapshot/schema support and codegen parity.
   - Remove temporary transition glue only after back-compat tests pass.
   - **Done criteria:** round-trip snapshot/codegen succeeds for multi-view figures.

---

## 13) Risks and mitigations

- **Risk:** hidden tab widgets report wrong size.  
  **Mitigation:** force pane reflow on tab activation.

- **Risk:** duplicate state paths (model vs widget) drift.  
  **Mitigation:** one canonical update path for range writes per view.

- **Risk:** rendering cost with many views.  
  **Mitigation:** strict stale-flag policy + active-only evaluation.

- **Risk:** API confusion during transition.  
  **Mitigation:** keep user-facing term `view` consistently in docs/helpers/errors.

---

## 14) Exit checklist

- [ ] Multi-view tabs are functional and documented.
- [ ] Plot membership is explicit and tested.
- [ ] Visibility-gated rendering verified.
- [ ] Shared/scoped info cards verified.
- [ ] Snapshot/codegen updated for views.
- [ ] Single-view UX remains clean.
- [ ] Docs/notebook examples updated.
