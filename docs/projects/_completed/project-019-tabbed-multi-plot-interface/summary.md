# Project 019: Tabbed Multi-Plot Interface (Refined Summary)

**Priority:** High
**Effort:** Large
**Impact:** Evolve `Figure` from a single-canvas coordinator into a multi-view workspace with tabbed navigation, per-view viewport state, and visibility-aware rendering.

---

## 1) What the current codebase does today (analysis)

This summary is grounded in the current implementation:

- `Figure` orchestrates exactly one Plotly `FigureWidget` and one `PlotlyPane` inside one `FigureLayout.plot_container`.
- `FigureLayout` has a single plot area + one shared sidebar (`params_box`, `info_box`); there is no tab container yet.
- `Plot` currently owns one `_plot_handle` (single trace binding), so plot membership is implicitly single-view.
- `InfoPanelManager` supports shared info cards by ID, but has no built-in view scoping model.
- `FigureSnapshot`/`codegen` are single-view oriented (`x_range`, `y_range`, one plot map), so serialization must be extended for multi-view.

---

## 2) Confirmed decisions carried forward

1. **Per-view range model**
   Keep default ranges and viewport ranges distinct. The existing viewport control behavior in `Figure` is the bridge and should become per-view.

2. **Info-card scoping model**
   Support both:
   - shared info (`view=None`) visible on all tabs,
   - view-scoped info (`view="..."`) visible only for active view.

3. **Autoscale rule**
   For each view:
   - explicit `y_range` => no y autoscale,
   - `y_range is None` => y autoscale enabled.

4. **Legacy info helper cleanup**
   `get_info_output` and `add_info_component` remain removed (no compatibility layer).

5. **Terminology**
   Public API should use **View** (not Canvas) going forward.

---

## 3) Gap between current code and target

The major architectural gap is that the current runtime model is `Figure -> many Plot`, where each `Plot` maps to one trace on one widget. Project 019 needs `Figure(workspace) -> many View`, and `Plot -> many PlotHandle(view-specific traces)`.

Because of that, implementation must touch **state model**, **render pipeline**, **layout composition**, **public API**, and **snapshot/codegen** simultaneously (or in tightly controlled phases).

---

## 4) Refined scope and expected deliverables

### In scope
- New `View` abstraction with ID/title/labels/range state.
- Tabbed UI (`ipywidgets.Tab`) containing one plot pane per view.
- Explicit multi-view plot membership (`PlotHandle` per view).
- Visibility-gated rendering (active renders now, inactive marked stale).
- Shared + view-scoped info cards in shared sidebar.
- Public API additions (`add_view`, `view(...)`, `plot(..., views=...)`, `info(..., view=...)`, 
`plots['id'].views` return  tuple of handles, `plots['id'].add_views(viewid or viewhandel or tuple thereof)` `plots['id'].remove_views(viewid or viewhandel or tuple thereof)` (ignore already absent views).
- Updated snapshot/codegen to represent views and scoped info cards.
- Full unit/integration tests for the above.

### Out of scope (deferred)
- Per-view parameter dependency subsets.
- Drag-and-drop plot reassignment.
- Non-tab layouts (grid/split).

---


## 5) Incremental phases that preserve a working system

Each phase below is intended to be mergeable while keeping notebook workflows functional and tests green:

1. **Phase S1 — Foundation compatibility pass**
   Land view registry internals behind the existing single-view public behavior (default view only), with no tab UI exposure yet.

2. **Phase S2 — Multi-view model without UI switch**
   Add `View` and `PlotHandle` data structures plus membership APIs, but keep rendering pinned to one active default view until tab wiring is ready.

3. **Phase S3 — Tab UI + active-view routing**
   Introduce `ipywidgets.Tab` and active view selection while preserving a default single-view code path for old notebooks.

4. **Phase S4 — Visibility-gated rendering**
   Enable stale-marking for inactive views and refresh-on-activation semantics, with regression tests proving no behavior regressions for single-view figures.

5. **Phase S5 — Public API completion**
   Expose `add_view`, `view(...)`, `plot(..., view=...)`, and `info(..., view=...)` with docs/examples, while keeping no-`view` calls mapped to the active/default view.

6. **Phase S6 — Snapshot/codegen parity + hardening**
   Extend snapshot/codegen schemas, finalize migration tests, and only then remove temporary compatibility shims introduced in earlier phases.

---

## 6) Clarifications incorporated into implementation direction

The pending questions are now resolved and should be treated as implementation constraints:

1. **Default view identity**
   The implicit first view remains `"main"` by default, but this must be configurable in `Figure(...)` construction.

2. **`plot(id=...)` view narrowing behavior**
   Re-scoping an existing plot to a narrower `view=` set should automatically remove dropped view memberships.

3. **View deletion semantics**
   Project scope includes `remove_view(...)`. Its behavior should be a thin wrapper around membership updates, and plots with no remaining view memberships are valid state.

4. **Snapshot compatibility strategy**
   Snapshot schema versioning (e.g., `schema_version`) is required, but scheduled as a final-priority part of the snapshot/codegen workstream.

5. **Initial rendering policy for inactive tabs**
   Non-visible views should not render at startup. Rendering should occur only when a view is visible/activated.

---

## 7) Execution note

A detailed, phase-by-phase delivery plan is provided in `plan.md` and is now aligned with the observed implementation boundaries in `Figure.py`, `figure_plot.py`, `figure_layout.py`, `figure_info.py`, and snapshot/codegen modules.


## Goal/Scope
Deliver a tabbed multi-view plotting interface while preserving default single-view behavior.


## Summary of design
The design introduces per-view runtime state, explicit plot-to-view memberships, and lazy rendering for inactive views.


## Open questions
- None currently; unresolved items should be tracked here.


## Challenges and mitigations
- Hidden-tab rendering quirks are mitigated with activation-time reflow and stale-view refresh policy.


## Status
Completed (2026-02-16)


## TODO checklist
- [x] Keep phase progress synchronized with implementation status.


## Exit criteria
- [x] Multi-view behavior is implemented with backward-compatible single-view defaults.
