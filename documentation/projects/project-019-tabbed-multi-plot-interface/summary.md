# Project 019: Tabbed Multi-Plot Interface

**Priority:** High  
**Effort:** Large  
**Impact:** Introduces a multi-view plotting workspace with tabbed navigation, per-view viewport control, and visibility-aware rendering.

---

## Problem Statement

The current plotting architecture is effectively single-canvas:

- `Figure` owns one `FigureWidget` and one sidebar layout.
- Range semantics are blurred between defaults and live viewport state.
- Plot-to-canvas binding is implicit and rigid (single handle per plot).
- Rendering re-evaluates all plots on parameter changes regardless of visibility.

This prevents a first-class workflow for one shared parameter workspace with multiple independent visual views (e.g., time/frequency, macro/zoom, raw/transformed).

---

## Required Capabilities (from discussion)

1. **Per-view ranges, not figure-global ranges**
   - Treat default x/y ranges as view-specific.
   - Track current viewport ranges separately per view.

2. **Clear plot identity and membership**
   - Every plot must have a stable identifier.
   - Membership in one or more views must be explicit, not inferred from one private handle.

3. **Visibility-gated computation**
   - Inactive tabs should not regenerate plot data.
   - Inactive views become stale and re-render when activated.

4. **Tabbed interface with shared parameter controls**
   - Parameters remain workspace-level.
   - Multiple plotting views are organized via tabs.

5. **Info-panel scoping model (decided)**
   - Support **both** shared and per-view info cards.
   - Shared info cards are always visible.
   - Per-view info cards occupy the same area but only appear when that view is active.

6. **View metadata (decided)**
   - Support figure-level title.
   - Support per-view title and per-view x/y axis labels.

7. **Autoscaling rule (decided)**
   - If `y_range` is explicitly set on a view, do not autoscale y.
   - If `y_range` is not set, allow y autoscaling for that view.

8. **Legacy info helper cleanup (decided)**
   - Remove `fig.get_info_output()` and `fig.add_info_component()`.
   - Do not keep backward compatibility for this old unused path.

---


## Implemented Clarification: Viewport Controls in Current `Figure`

The current single-view `Figure` now treats viewport ranges as **controls** instead of passive cached fields:

- `_viewport_x_range` / `_viewport_y_range` are control-backed properties.
- **Read** behavior queries the live Plotly widget range (`layout.xaxis.range` / `layout.yaxis.range`).
- **Write** behavior moves only the current viewport window and does **not** mutate defaults (`x_range`, `y_range`).
- Writing `None` re-applies the default axis range for that axis.
- Plotly home/reset behavior remains anchored to default ranges.

This is the concrete bridge between today’s single-view implementation and Project 019’s per-view range model.

---

## Out of Scope / Deferred

- Per-view parameter dependency subsets (optimization): deferred.
- Drag-and-drop plot reassignment between tabs: deferred.
- Side-by-side grid layout: deferred (future project).

---

## Deliverables

- `plan.md` with phased implementation covering model, rendering, layout, API, and tests.
- Explicit decision log integrated into the plan (no unresolved ambiguity for items already decided).

---

## Implementation Status Checklist (updated)

### Completed

- [x] Clarified viewport control semantics in current single-view `Figure` as an explicit bridge toward per-view viewport handling.
- [x] Removed legacy info helper APIs called out in this project as cleanup targets:
  - [x] `Figure.get_info_output()`
  - [x] `Figure.add_info_component()`
  - [x] Associated module-level helper exports
- [x] Added regression coverage to lock in the legacy-info-helper removal behavior.

### Remaining

- [ ] Introduce first-class `View` abstraction and tab container wiring (`ipywidgets.Tab`).
- [ ] Implement per-view default range + viewport state ownership.
- [ ] Implement explicit `PlotHandle` multi-view membership model (`plot_id -> handles by view_id`).
- [ ] Add visibility-gated render behavior (active view renders; inactive views marked stale).
- [ ] Implement stale-on-inactive and one-time refresh on tab activation.
- [ ] Add per-view info card scoping (`view=None` shared, `view="..."` scoped).
- [ ] Add/validate API for view lifecycle and targeting (`add_view`, `view(...)` context, `plot(..., view=...)`).
- [ ] Add comprehensive tests for the remaining multi-view/tabbed behavior in Phase 1-6 of `plan.md`.
- [ ] Add/refresh notebook integration examples in `documentation/Toolkit_overview.ipynb` for GUI-dependent checks.
