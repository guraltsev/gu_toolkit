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

## Out of Scope / Deferred

- Per-view parameter dependency subsets (optimization): deferred.
- Drag-and-drop plot reassignment between tabs: deferred.
- Side-by-side grid layout: deferred (future project).

---

## Deliverables

- `plan.md` with phased implementation covering model, rendering, layout, API, and tests.
- Explicit decision log integrated into the plan (no unresolved ambiguity for items already decided).
