# Project 030: Dedicated Per-Tab Legend Side Panel (Summary)

**Status:** Discovery  
**Type:** Architecture proposal (no implementation in this project record)

## Goal/Scope

Design and document a migration path away from Plotly's built-in legend (`layout.showlegend`) toward a dedicated, notebook-native side panel legend that is rendered next to each plot tab/view.

The proposal must support, at minimum:

1. **Show/Hide per plot row** (replacement for Plotly legend click behavior).
2. **LaTeX-capable labels** in legend rows.
3. **One legend panel per view tab** (same tab model already used by `Figure` view switching).

And define a long-term architecture for:

1. Opening per-plot properties (cogwheel) and editing style/runtime attributes:
   - opacity,
   - color,
   - line style (dash),
   - width (thickness),
   - sampling points.
2. Editing defining equations through pipeline:
   - MathLive -> SymPy -> numpify.
3. Adding new plots through the same pipeline:
   - MathLive -> SymPy -> numpify.

Non-goals for this documentation project:

- No runtime code changes.
- No public API behavior changes yet.
- No deprecation warnings yet.

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

#### C. Plot-level state and style mutation APIs already exist

`Plot` currently exposes mutable properties and an update path that cover most requested “future cogwheel” controls:

- visibility (`plot.visible`, including Plotly `True/False/"legendonly"` semantics),
- label (`plot.label`),
- color (`plot.color`),
- dash (`plot.dash`),
- thickness (`plot.thickness`),
- opacity (`plot.opacity`),
- sampling points (`plot.sampling_points`),
- combined update (`plot.update(...)`).

**Implication:** The side-panel legend should initially be a thin UI layer over existing `Plot` setters; no immediate core math/render refactor is required to unlock toggles and style edits.

#### D. Equation parsing/compilation pieces already exist, but not as an editor flow

- SymPy LaTeX parsing wrapper exists (`parse_latex`) with fallback behavior.
- Symbolic-to-numeric compilation path exists (`numpify`, `numpify_cached`).
- `Figure.plot(...)` already supports expression/callable/`NumericFunction` input normalization.

**Gap:** There is no existing widget-level MathLive integration, no expression-editor modal contract, and no explicit transactional update path for “edit equation then replace plot expression.”

#### E. Plotly internal legend is currently enabled globally

- Default figure layout sets `showlegend=True` and configures `layout.legend` styling.

**Implication:** migration requires a controlled step to disable Plotly legend and ensure replacement UI parity before permanent removal.

### 2) Proposed target architecture

#### A. New manager layer: `LegendPanelManager` (workspace-level with per-view filtering)

Introduce a manager analogous to `InfoPanelManager`/`ParameterManager` that:

- owns legend row widgets,
- maps rows to `Plot` IDs,
- understands per-view membership (`plot.view_ids`),
- updates row visibility when active view changes,
- can operate in read-only (v1) and editable (future cogwheel) modes.

Proposed primary responsibilities:

1. **Render rows** for plots relevant to active view.
2. **Bidirectional sync**:
   - UI toggle -> `plot.visible`.
   - Programmatic plot updates -> row state refresh.
3. **Label rendering** with `HTMLMath` to support LaTeX labels.
4. **Action slot** per row for future cogwheel/properties popover.

#### B. Layout extension in `FigureLayout`

Add a dedicated legend section in the right sidebar:

- `legend_header`
- `legend_box`

And extend sidebar visibility logic to include `has_legend` as a third contributor (`has_params`, `has_info`, `has_legend`).

Design constraint: the new legend block should not break existing full-width behavior or responsive wrapping controlled by `content_wrapper` and `PlotlyPane` reflow callbacks.

#### C. Runtime source of truth

Keep **`Plot` object state** as source of truth for visibility/style/label. The legend panel is a presentation/editor layer only.

This avoids dual state systems and leverages existing trace fan-out logic across per-view handles.

#### D. Migration strategy for Plotly legend

Phase migration:

1. **Dual mode (temporary):** Internal Plotly legend can remain enabled behind an internal flag while panel behavior is validated.
2. **Panel-default mode:** Dedicated legend panel enabled and Plotly legend disabled by default (`showlegend=False`).
3. **Removal mode:** Remove fallback internal legend path once acceptance and regression coverage are complete.

### 3) Long-term extensibility path

#### A. Cogwheel / properties editor

Define row-level “properties” action that opens either:

- inline expandable row section, or
- modal anchored in `FigureLayout.root_widget` (similar host concept already used in parameter controls).

Property edits should map to existing `Plot` setters and `plot.update(...)` where possible.

#### B. Equation editor (MathLive -> SymPy -> numpify)

Planned flow per selected plot:

1. Open math editor pre-populated from current symbolic expression/label.
2. Convert MathLive output to LaTeX string.
3. Parse with `parse_latex`.
4. Resolve plotting variable and parameters (via existing normalization conventions).
5. Update plot function (`set_func` / equivalent `plot.update(var=..., func=..., parameters=...)`).
6. Re-render and refresh legend row metadata.

#### C. Add-plot UX via same pipeline

Planned flow:

1. “+ Plot” action in legend panel.
2. MathLive authoring.
3. Parse/normalize/compile.
4. Create `Figure.plot(...)` entry with generated id.
5. Attach to active view by default (optional future multi-view targeting).

## Open questions

1. **Legend row ordering**: insertion order, alphabetical by id, or explicit user-reorder?
2. **Per-view vs global label/style overrides**: should style edits be global to a plot object or scoped by view?
3. **Visibility semantics**: keep supporting `"legendonly"` internally, or collapse to boolean in panel UI?
4. **Equation variable inference UX**: when ambiguous callable/symbol sets occur, should UI force explicit variable selection before commit?
5. **Failure UX for parsing/compilation**: inline row error vs modal error box vs info panel broadcast?
6. **Persistence/snapshot format**: should legend/editor UI state be part of `FigureSnapshot` now or later?

## Challenges and mitigations

1. **State synchronization drift** between panel rows and trace handles.  
   *Mitigation:* keep `Plot` as sole source of truth and add explicit panel refresh hooks on plot create/update/remove.

2. **Per-view row filtering complexity** with plots attached to multiple views.  
   *Mitigation:* reuse existing view-membership semantics already used by `PlotHandle` and stale render logic.

3. **LaTeX rendering consistency** between labels, sliders, and equation editor previews.  
   *Mitigation:* standardize on `HTMLMath` for display surfaces and `parse_latex` for symbolic parse boundary.

4. **Gradual migration risk** from Plotly legend interactions users may rely on.  
   *Mitigation:* staged rollout with temporary fallback flag and clear docs migration notes.

5. **MathLive integration surface area** (frontend comms, packaging, notebook compatibility).  
   *Mitigation:* isolate MathLive adapter behind a dedicated small widget bridge and keep parser/compile pipeline Python-owned.

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
