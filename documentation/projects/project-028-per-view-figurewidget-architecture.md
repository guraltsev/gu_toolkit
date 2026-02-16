# Project 028: Per-View FigureWidget Architecture Proposal

**Status:** Proposal (not implemented)
**Priority:** High
**Depends on:** Project 019 tabbed multi-view foundation

---

## 1) Request Summary

The current multitab behavior uses one shared Plotly `FigureWidget` and switches visible traces by active view.
The new requested direction is stronger isolation:

- one **Plotly FigureWidget per view**,
- plots only materialized in the views they belong to,
- no cross-view trace handles to hide/show.

This document is a planning proposal only. No runtime behavior is changed in this project file.

---

## 2) Current State (as observed)

- `Figure` owns a single `go.FigureWidget()` and a single `PlotlyPane` instance.
- `FigureLayout` mounts a single `plot_container` into the active tab pane.
- `Plot` now has per-view trace handles, but those traces still live inside one shared figure widget.

Consequence:

- We reduced wasted handles for non-member views at the plot level,
- but we still share one global figure object and one trace registry across all views.

---

## 3) Desired End State

### Functional target

1. Each view owns its own `FigureWidget`/`PlotlyPane` pair.
2. Switching tabs switches the **entire active figure widget**, not only trace visibility.
3. A plot with `views=("frequency",)` creates runtime handles only in the frequency view's figure.
4. Per-view ranges/labels/layout are naturally isolated by separate figures.

### Performance target

- Zero compute/update activity for non-active views except explicit stale marking.
- No memory spent on plotly traces in views where a plot is not a member.

---

## 4) Non-Goals

- No redesign of parameter API semantics.
- No changes to symbolic function model.
- No alternate layouts (grid/split).
- No immediate persistence-format breaking changes without compatibility path.

---

## 5) Proposed Architecture

## 5.1 New runtime composition

Replace single-figure ownership with view-scoped figures:

- `Figure` keeps a registry like `_view_runtime[view_id]` containing:
  - `figure_widget: go.FigureWidget`
  - `pane: PlotlyPane`
  - relayout observers/debouncers scoped per view
- `FigureLayout` hosts one active pane inside the active tab child.

## 5.2 Plot runtime model

`Plot` stores per-view handle objects where each handle references:

- owning `view_id`,
- trace object in that view's `FigureWidget`,
- cached x/y for that view (optional extension).

No handle is created for non-member views.

## 5.3 Events and rendering

- Parameter change:
  - render active view handles immediately,
  - mark inactive member views stale.
- Tab activation:
  - mount the activated view pane,
  - if stale, render only that view's plot handles,
  - trigger pane reflow.

## 5.4 Layout synchronization

Layout defaults (theme, margins, axes style) should be copied to each view figure at creation time from a shared style factory helper.

---

## 6) API Compatibility Strategy

Public APIs should stay stable where possible:

- keep `Figure.plot(..., view=...)`, `add_view`, `set_active_view`, `view(...)`.
- keep `Figure.figure_widget` for backward compatibility but define behavior:
  - returns active view's widget,
  - add new optional `Figure.figure_widget_for(view_id)` for explicit access.

Deprecation candidate:

- direct assumptions that `figure_widget.data` contains traces from all views.

---

## 7) Implementation Plan (Phased)

### Phase P1 — View runtime scaffolding

- Introduce internal per-view runtime container (`figure_widget`, `pane`, callbacks).
- Move figure/pane initialization from global singleton to per-view creation path.
- Keep existing behavior by creating runtime only for default view initially.

**Exit criteria:** single-view notebooks unchanged.

### Phase P2 — Layout host refactor

- Update `FigureLayout` to host active view pane rather than one shared pane.
- Preserve existing tab UX where plot is inside active tab content.

**Exit criteria:** switching views swaps pane host without blank gaps or bounce.

### Phase P3 — Plot binding migration

- Update `Plot` trace creation/update/remove to target the owning view's figure runtime.
- Remove global assumptions that all handles share one `figure_widget.data` list.

**Exit criteria:** view-scoped plots allocate traces only in member views.

### Phase P4 — Relayout/range/event routing

- Route relayout observers and viewport capture per active view figure.
- Ensure per-view viewport persistence survives tab switches.

**Exit criteria:** pan/zoom state isolated per view and restored on return.

### Phase P5 — Stale/render policy hardening

- Keep active-only rendering for heavy compute.
- Mark inactive member views stale on parameter changes.
- Render stale views once when activated.

**Exit criteria:** predictable compute profile with no hidden background render loops.

### Phase P6 — Compatibility + docs + cleanup

- Add compatibility accessors and warnings where needed.
- Update tests, docs, and examples.
- Remove obsolete shared-widget pathways.

**Exit criteria:** test parity and documentation completeness.

---

## 8) Test Plan

### Unit tests

- Per-view figure runtime creation/removal.
- Plot membership creates handles only in owning view runtimes.
- `remove_from_view` removes trace from that view figure only.
- Style updates propagate to all existing member-view handles.

### Integration tests

- Tab switch preserves per-view pan/zoom state.
- Parameter update marks inactive views stale and defers render.
- Activation renders stale view exactly once.
- Layout contains active pane within tab body (no detached gap).

### Regression tests

- Existing Project-019 behavior expectations remain valid for user API.
- Single-view workflows remain unchanged.

---

## 9) Risks and Mitigations

1. **Risk:** higher memory overhead with many views due to multiple full figures.
   - **Mitigation:** lazy runtime creation on first activation; optional runtime disposal for dormant views.

2. **Risk:** event wiring complexity (multiple relayout callbacks).
   - **Mitigation:** encapsulate observer setup/teardown in a dedicated runtime helper.

3. **Risk:** compatibility friction for users inspecting `figure_widget.data` globally.
   - **Mitigation:** document active-view semantics and add explicit per-view accessors.

4. **Risk:** tab switch flicker or sizing issues.
   - **Mitigation:** enforce reflow callback on activation and avoid unnecessary widget reconstruction.

---

## 10) Open Questions

1. Should inactive view runtimes be created eagerly at `add_view` or lazily at first activation?
ANSWER: Created eagerly
2. Should `Figure.snapshot()` capture per-view widget layout overrides if users mutate underlying plotly layout directly?
ANSWER: Yes
3. Do we want an explicit memory policy (`auto_dispose_inactive_views=True/False`) in a later phase?
ANSWER: No autodisposal

---

## 11) Acceptance Criteria

- One Plotly FigureWidget per view at runtime.
- No cross-view trace handles.
- Active-tab rendering remains responsive and visually correct.
- Per-view viewport and labeling isolation retained.
- Existing public APIs remain usable with documented active-view `figure_widget` semantics.
