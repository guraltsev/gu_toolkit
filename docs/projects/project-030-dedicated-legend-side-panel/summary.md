# Project 030: Dedicated Per-Tab Legend Side Panel (Summary)

**Status:** Discovery  
**Type:** Architecture proposal (no implementation in this project record)

## Goal/Scope

Migrate away from Plotly's built-in legend (`layout.showlegend`) toward a dedicated, notebook-native side panel legend that is rendered next to each plot tab/view.

1. **Show/Hide per plot row** (replacement for Plotly legend click behavior).
2. **LaTeX-capable labels** in legend rows.
3. **One legend panel per view tab** (same tab model already used by `Figure` view switching).


## Summary of design

### 1) Current infrastructure analysis (what exists already)

#### A. View/tab architecture is already in place

- `Figure` uses per-view runtime bundles (`_ViewRuntime`) each containing its own `go.FigureWidget` and `PlotlyPane`.
- View registration/selection exists (`add_view`, `set_active_view`) and is already wired to `FigureLayout.observe_tab_selection`.
- `FigureLayout` already hosts tab UI through `widgets.Tab` and has per-view widget hosting (`set_view_plot_widget`, `set_view_tabs`).

**Implication:** The requested “one legend panel for each plot tab” can piggyback on the existing view model instead of inventing a separate subplot state model.

#### B. There is already a side-panel pattern for dynamic UI content

- `FigureLayout` has right-side sidebar primitives (`params_box`, `info_box`, `sidebar_container`) and visibility controls.
- `ParameterManager` demonstrates a pattern for row-like interactive controls that mutate figure behavior.
- `InfoPanelManager` demonstrates optional per-view visibility filtering (`view_id`) with shared storage and active-view sync.

**Implication:** A legend panel manager can follow the same architecture style as parameters/info and likely be integrated as a third section in the sidebar stack.

Now that Figure supports tabs, the legend should live inside the per-tab area, not outside of it like the Parameters and InfoPanel.

#### C. Plot-level state and style mutation APIs already exist

Plots already carry their relation to views. A view should have only plots in it as legend entries.

The properties should be common for all views. 

Visibility (`plot.visible`, including Plotly `True/False` semantics),
	Replace "legendonly" with False. Plots should ALWAYS be visible in legend (greyed out). They should vanish only if the plot is removed from a view.


#### E. Plotly internal legend is currently enabled globally

- Default figure layout sets `showlegend=True` and configures `layout.legend` styling.

**Implication:** Disable Plotly legend.

WARNING: Plotly dies and stops working with labels containing latex. use "id" as label in the plotly legend. Use label= as data for this new custom legend. 

### 2) Proposed target architecture

#### A. New manager layer: `LegendPanelManager` (workspace-level with per-view filtering)

Introduce a manager analogous to `InfoPanelManager`/`ParameterManager` that:

- owns legend row widgets,
- maps rows to `Plot` IDs,
- understands per-view membership (`plot.view_ids`),
- updates row visibility when active view changes,

Proposed primary responsibilities:

1. **Render rows** for plots relevant to active view.
2. **Bidirectional sync**:
   - UI toggle -> `plot.visible`.
   - Programmatic plot updates -> row state refresh.
3. **Label rendering** with `HTMLMath` to support LaTeX labels.

#### B. Layout extension in `FigureLayout`

Add a dedicated legend section in the right sidebar:

- `legend_header`
- `legend_box`

And extend sidebar visibility logic to include `has_legend` as a third contributor (`has_params`, `has_info`, `has_legend`).

Design constraint: the new legend block should not break existing full-width behavior or responsive wrapping controlled by `content_wrapper` and `PlotlyPane` reflow callbacks.

### B2. 
Expose view-based control of whether legend is visible or not. 

#### C. Runtime source of truth

Keep **`Plot` object state** as source of truth for visibility/style/label. The legend panel is a presentation/layer only.

This avoids dual state systems and leverages existing trace fan-out logic across per-view handles.

#### D. Migration strategy for Plotly legend

Phase migration:

2. **Panel-default mode:** Dedicated legend panel enabled and Plotly legend disabled by default (`showlegend=False`).
3. **Removal mode:** Remove fallback internal legend path once acceptance and regression coverage are complete.

## Open questions

1. **Legend row ordering**: insertion order, alphabetical by id, or explicit user-reorder?
ANSWER: insertion order for now. Store in sequence so that reordering can be implemeneted later.

2. **Per-view vs global label/style overrides**: should style edits be global to a plot object or scoped by view?
ANSWER: Global.
3. **Visibility semantics**: keep supporting `"legendonly"` internally, or collapse to boolean in panel UI?
ANSWER: Boolean, False means grayed out in legend but invisible in plot view. Plot retains view
6. **Persistence/snapshot format**: should legend/editor UI state be part of `FigureSnapshot` now or later?
ANSWER: Yes. After all it is a per/view boolean. Not hard. 

## Challenges and mitigations

1. **State synchronization drift** between panel rows and trace handles.  
   *Mitigation:* keep `Plot` as sole source of truth and add explicit panel refresh hooks on plot create/update/remove.

2. **Per-view row filtering complexity** with plots attached to multiple views.  
   *Mitigation:* reuse existing view-membership semantics already used by `PlotHandle` and stale render logic.

3. **LaTeX rendering consistency** between labels, sliders, and equation editor previews.  
   *Mitigation:* standardize on `HTMLMath` for display surfaces and `parse_latex` for symbolic parse boundary.

4. **Gradual migration risk** from Plotly legend interactions users may rely on.  
   *Mitigation:* staged rollout with temporary fallback flag and clear docs migration notes.

## Status

- [x] Discovery analysis completed.
- [x] Initial target architecture documented.
- [x] Migration and long-term roadmap drafted.
- [ ] Implementation plan approved.
- [ ] Runtime implementation started.

## TODO

- [ ] Confirm product decisions for open questions (ordering, scope, UX errors).
- [ ] Approve manager/layout contracts (`LegendPanelManager`, `FigureLayout` additions).
- [ ] Define temporary feature-flag strategy for dual legend mode.
- [ ] Approve equation editing transaction contract and validation UX.
- [ ] Finalize acceptance test matrix and implementation phases.

## Exit criteria

- Proposal is approved as implementation-ready architecture.
- Required manager/layout/state contracts are frozen.
- Migration sequence away from Plotly legend is agreed.
- Future equation-edit/add workflows have explicit interfaces and error handling rules.
