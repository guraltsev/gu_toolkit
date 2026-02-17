# Project 030: Dedicated Per-Tab Legend Side Panel (Plan)

## Detailed blueprint for implementation

### Phase 0 — Baseline and design lock

1. Confirm final UX scope for v1:
   - row toggle (show/hide),
   - LaTeX label display,
   - per-tab filtered rows.
2. Freeze a minimal internal API contract for legend manager events:
   - on plot add,
   - on plot update,
   - on plot remove,
   - on active view change.
3. Define temporary migration flag behavior for internal Plotly legend coexistence.

**Deliverable:** approved v1 contract and rollout policy.

---

### Phase 1 — Layout primitives in `FigureLayout`

1. Add legend UI containers to sidebar stack:
   - `legend_header` (HTML),
   - `legend_box` (VBox).
2. Extend visibility orchestration:
   - evolve `update_sidebar_visibility(has_params, has_info)` into a contract that includes legend presence.
3. Preserve current responsive behavior:
   - no regressions in full-width toggle,
   - no regressions in `PlotlyPane` reflow triggers.

**Deliverable:** layout supports a third sidebar section for legend content.

---

### Phase 2 — Introduce `LegendPanelManager`

1. Create manager responsible for row lifecycle and sync.
2. Define row model fields (minimum):
   - `plot_id`,
   - display label (math-capable),
   - visibility state,
   - optional per-row actions.
3. Implement active-view filtering behavior:
   - show rows for plots present in selected view,
   - hide or ghost rows not in view (decision pending from Phase 0).
4. Add debounced/guarded refresh API to avoid UI churn during batched updates.

**Deliverable:** isolated panel manager with deterministic row state.

---

### Phase 3 — Wire manager into `Figure` lifecycle

1. Initialize legend manager alongside parameter/info managers.
2. On `Figure.plot(...)` create/update flows, notify legend manager.
3. On `remove_view`, `set_active_view`, and future plot deletion flow, notify legend manager.
4. Guarantee single source of truth:
   - manager reads/writes `Plot` properties,
   - no duplicate visibility/style state store.

**Deliverable:** legend panel is always synchronized with figure plot registry and tab selection.

---

### Phase 4 — Replace Plotly internal legend interactions

1. Add configuration mode:
   - dual-mode (internal legend + side panel), then
   - panel-primary (`showlegend=False`).
2. Ensure side-panel toggle parity with legacy legend click:
   - toggle off -> `plot.visible = False` (or `"legendonly"` if chosen),
   - toggle on -> `plot.visible = True` and render behavior unchanged.
3. Confirm no regression in multi-view stale/active render behavior.

**Deliverable:** internal legend can be disabled without loss of essential functionality.

---

### Phase 5 — LaTeX labels in legend rows

1. Render row labels with `HTMLMath`.
2. Define escaping/sanitization rules for plain text labels.
3. Validate labels from common sources:
   - explicit `label=...`,
   - default id labels,
   - labels containing `$...$` math markup.

**Deliverable:** readable labels for both plain text and math-rich content.

---

### Phase 6 — Properties (cogwheel) foundation

1. Add a per-row action slot (cog icon/button).
2. Implement a minimal properties surface for existing `Plot` controls:
   - opacity,
   - color,
   - dash,
   - thickness,
   - sampling points.
3. Route edits through existing setters / `plot.update(...)`.
4. Define validation/error display policy for invalid values.

**Deliverable:** panel can edit plot appearance and sampling without introducing new core plot state.

---

### Phase 7 — Equation editing via MathLive -> SymPy -> numpify

1. Add equation-edit action per row.
2. Integrate MathLive widget bridge for authoring LaTeX expressions.
3. On submit:
   - parse via `parse_latex`,
   - normalize symbols/vars,
   - update existing plot function,
   - trigger render and panel refresh.
4. Error handling:
   - parse failures,
   - ambiguous variable inference,
   - compilation/runtime numeric errors.

**Deliverable:** user can edit an existing plot equation graphically and re-render safely.

---

### Phase 8 — Add new plot flow via MathLive -> SymPy -> numpify

1. Add “+ Plot” action in legend panel header.
2. Reuse equation editor pipeline for creation.
3. Define id generation and default label policy.
4. Attach new plot to active view by default.

**Deliverable:** users can add new plots through graphical equation input.

---

### Phase 9 — Cleanup and hardening

1. Remove temporary dual-mode fallback when stable.
2. Update docs and notebook examples to show side-panel-first workflow.
3. Add migration notes for users accustomed to Plotly legend interactions.

**Deliverable:** side panel is canonical legend/edit surface.

## Description of test suite for acceptance

### Unit tests

1. **Legend manager lifecycle**
   - add/update/remove plot row behavior,
   - active view filtering,
   - state refresh idempotency.

2. **Figure integration**
   - rows created for new plots,
   - rows updated on label/style/visibility changes,
   - rows react to `set_active_view` and `remove_view`.

3. **Visibility parity**
   - row toggle modifies `plot.visible`,
   - hidden plot skips render and re-renders on show.

4. **LaTeX label rendering**
   - plain text labels,
   - math labels with delimiters,
   - malformed label safety behavior.

5. **Properties editing**
   - opacity bounds validation,
   - line style updates, sampling point updates,
   - error propagation UX hooks.

6. **Equation edit flow**
   - parse success path,
   - parse fallback behavior,
   - ambiguous var handling,
   - numeric compile path updates.

7. **Add-plot flow**
   - creation from editor,
   - active-view assignment,
   - generated ids/labels consistency.

### Integration/browser tests

1. Tab switch while toggling legend rows (state remains consistent).
2. Sidebar width changes do not break plot resizing behavior (`PlotlyPane`).
3. Per-row property edits immediately affect rendered traces.
4. Equation edit and add-plot flows complete without notebook reload.

### Regression tests

1. Existing parameter slider behavior unchanged.
2. Existing info panel behavior unchanged.
3. Existing callable-first `plot()` flows unchanged when panel not used.

## Phased rollout that keeps toolkit consistent and functioning

- **Safe checkpoint A (after Phase 2):** Layout + manager exists but does not replace Plotly legend.
- **Safe checkpoint B (after Phase 4):** Side panel can fully replace show/hide interactions.
- **Safe checkpoint C (after Phase 6):** Style/sampling edits supported through panel.
- **Safe checkpoint D (after Phase 8):** End-to-end graphical equation editing and creation complete.

Each checkpoint should be releasable independently, with feature flags where needed.

## Risks and mitigation

1. **Notebook frontend variability for MathLive integration**  
   Mitigation: keep parser/compile logic in Python and isolate frontend bridge.

2. **UI complexity growth in sidebar**  
   Mitigation: progressive disclosure (compact rows, modal/expanders for advanced editing).

3. **Performance under many plots/tabs**  
   Mitigation: incremental row updates + debounced refresh + avoid full widget tree rebuilds.

4. **User confusion during migration**  
   Mitigation: temporary coexistence mode and clear release notes with before/after interaction mapping.

## Definition of done

- Plotly internal legend is no longer required for core show/hide workflow.
- Dedicated side-panel legend works per tab with LaTeX-capable labels.
- Row-level properties editor supports style + sampling controls.
- Equation edit and add-plot flows run through MathLive -> SymPy -> numpify path.
- Automated tests cover lifecycle, view switching, editing flows, and regressions.
