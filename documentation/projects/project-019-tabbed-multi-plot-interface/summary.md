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
- Public API additions (`add_view`, `view(...)`, `plot(..., view=...)`, `info(..., view=...)`).
- Updated snapshot/codegen to represent views and scoped info cards.
- Full unit/integration tests for the above.

### Out of scope (deferred)
- Per-view parameter dependency subsets.
- Drag-and-drop plot reassignment.
- Non-tab layouts (grid/split).

---

## 5) Clarifications needed before implementation starts

To avoid rework, these questions should be answered/confirmed explicitly:

1. **Default view identity:** should the implicit first view always be `"main"`, or should it be user-configurable at `Figure(...)` construction?
2. **Backwards compatibility for `plot(id=...)`:** if an existing plot is updated with a narrower `view=` set, should removed memberships be deleted automatically, or only when explicitly removed?
3. **View deletion semantics:** do we need `remove_view(...)` in this project, and what should happen to plots scoped only to that view?
4. **Snapshot compatibility strategy:** should `FigureSnapshot` be versioned (e.g., `schema_version`) to preserve loading/codegen behavior for older snapshots?
5. **Initial tab selection behavior:** should stale-refresh run on first display for non-active tabs only, or should all views render once at startup then switch to visibility-gated mode?

---

## 6) Execution note

A detailed, phase-by-phase delivery plan is provided in `plan.md` and is now aligned with the observed implementation boundaries in `Figure.py`, `figure_plot.py`, `figure_layout.py`, `figure_info.py`, and snapshot/codegen modules.
