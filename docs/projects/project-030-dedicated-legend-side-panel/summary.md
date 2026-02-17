# Project 030: Dedicated Per-Tab Legend Side Panel (Summary)

**Status:** In progress (Phases 1-3 implemented)
**Type:** Architecture and implementation plan

## Goal/Scope

Replace Plotly's built-in legend with a **toolkit-owned legend panel** that is scoped to the active view tab and supports notebook-native interactions.

Primary scope for this project:
1. Per-row show/hide controls for plots in the active view.
2. LaTeX-capable legend labels.
3. One legend surface per active view/tab (following the existing view architecture).
4. A migration path from Plotly legend semantics (`showlegend`, `"legendonly"`) to toolkit-managed behavior.

Out of scope for v1:
- Drag-and-drop legend reordering.
- Large new expression-authoring UX beyond minimal equation edit hooks.
- Non-notebook frontends.

## Summary of design

### 1) What already exists (validated baseline)

- The toolkit already has a **per-view runtime model** (`Figure` + `_ViewRuntime`) with tab selection and active-view synchronization.
- `FigureLayout` already supports a right sidebar with section headers/content blocks and global sidebar visibility orchestration.
- `ParameterManager` and `InfoPanelManager` provide proven patterns for manager-owned widget lifecycle + active-view-aware filtering.
- Plot visibility and labeling are already first-class at `Plot` level, with updates propagated to per-view trace handles.

**Consequence:** The legend panel should be implemented as a manager integrated into existing layout and view lifecycles, not as a separate ad-hoc UI stack.

### 2) Target architecture

#### A. `LegendPanelManager`

Introduce a new manager responsible for legend row lifecycle and synchronization:
- Registry of rows keyed by `plot_id`.
- Active-view filtering based on `plot.views` membership.
- Toggle events mapped to `plot.visible`.
- Label rendering via `ipywidgets.HTMLMath`.
- Refresh hooks for plot add/update/remove and active-view changes.

#### B. `FigureLayout` extension

Extend sidebar composition with a dedicated legend section:
- `legend_header`
- `legend_box`

And expand sidebar visibility API to include legend presence:
- from `update_sidebar_visibility(has_params, has_info)`
- to `update_sidebar_visibility(has_params, has_info, has_legend)`.

#### C. State model decisions

- **Single source of truth:** `Plot` remains canonical for visibility/label/style.
- **Visibility policy:** legend UI uses boolean visible/invisible semantics for user interaction; internal compatibility with existing `"legendonly"` may be retained only during migration.
- **Ordering policy (v1):** insertion order.
- **Scope policy:** labels/styles are global per plot, while row visibility in the panel is filtered by active view membership.

#### D. Plotly legend migration

- Transitional dual-mode supported briefly (feature flag).
- End state: Plotly internal legend disabled by default (`showlegend=False`), toolkit legend is canonical interaction surface.

## Open questions

1. Should hidden plots remain listed as disabled rows for non-member views, or be fully omitted?
2. Should future per-view label overrides be supported, or remain global per plot?
3. Should legend row state (expanded/collapsed editor state) be serialized in snapshots, or treated as ephemeral UI?

## Challenges and mitigations

1. **Sync drift risk between UI rows and plot registry**
   Mitigation: manager subscribes to plot lifecycle and performs idempotent rebuild/refresh.

2. **View-tab switching complexity**
   Mitigation: reuse existing `set_active_view` flow and call legend manager updates in the same place as info updates.

3. **LaTeX rendering edge cases**
   Mitigation: use `HTMLMath` consistently and keep plain-text fallback behavior deterministic.

4. **Migration breakage for users accustomed to Plotly legend clicks**
   Mitigation: rollout flag + release notes + parity tests.

## Status

- Codebase reviewed for current architecture and integration points.
- Summary and plan rewritten for implementation-ready execution.
- Phases 1-3 are now implemented in code and covered by project tests.

## TODO

- [x] Add `LegendPanelManager` module and wire into `Figure` lifecycle.
- [x] Extend `FigureLayout` sidebar model with legend section.
- [x] Add visibility/label synchronization tests.
- [x] Add active-view filtering tests.
- [ ] Add migration tests for Plotly legend disablement.
- [ ] Update docs/examples to show side-panel legend workflow.

## Exit criteria

- Dedicated legend panel works across multi-view tabs with correct filtering.
- Toggling legend rows updates rendered plot visibility deterministically.
- LaTeX labels render correctly in legend rows.
- Plotly internal legend is no longer required for normal workflows.
- Tests cover manager lifecycle, view switching, and regressions.
