# Project 030: Dedicated Per-Tab Legend Side Panel (Plan)

## Detailed blueprint for implementation

### Phase 0 — Contract lock and migration guardrails

1. Lock v1 scope: per-view filtered rows, toggle visibility, LaTeX labels.
2. Define `LegendPanelManager` interface and event contract:
   - `on_plot_added(plot)`
   - `on_plot_updated(plot)`
   - `on_plot_removed(plot_id)`
   - `set_active_view(view_id)`
   - `refresh(reason=...)`
3. Decide migration behavior for Plotly legend:
   - feature flag for dual-mode,
   - default target mode `showlegend=False`.
4. Decide visibility semantics:
   - UI control emits boolean visible state,
   - compatibility handling for `"legendonly"` only where needed.

**Deliverable:** frozen API contract and rollout policy.

---

### Phase 1 — Extend `FigureLayout` for legend section

1. Add layout primitives:
   - `legend_header` (`widgets.HTML`)
   - `legend_box` (`widgets.VBox`)
2. Insert legend widgets into `sidebar_container` ordering (params, info, legend).
3. Extend `update_sidebar_visibility` signature to:
   - `update_sidebar_visibility(has_params, has_info, has_legend)`.
4. Keep existing responsive behavior intact:
   - full-width mode,
   - wrap behavior,
   - Plotly reflow callback triggers.

**Deliverable:** layout can host legend content without regressions.

---

### Phase 2 — Implement `LegendPanelManager`

1. Create new module (recommended: `figure_legend.py`) with:
   - row dataclass/model,
   - widget creation/update helpers,
   - active-view filtering logic.
2. Row contents (v1):
   - visibility toggle,
   - `HTMLMath` label,
   - stable plot-id binding.
3. Internal manager responsibilities:
   - maintain deterministic insertion order,
   - idempotent refresh,
   - avoid full widget tree rebuild where possible.
4. Add `has_legend` property for sidebar visibility orchestration.

**Deliverable:** standalone legend manager with deterministic behavior.

---

### Phase 3 — Wire manager into `Figure`

1. Initialize legend manager after layout/managers are created.
2. Update all sidebar visibility calls to include legend presence.
3. Hook lifecycle events:
   - during plot create/update in `Figure.plot(...)`,
   - during plot removal flows,
   - during `add_view`, `set_active_view`, and `remove_view`.
4. Ensure manager reads/writes `Plot` state directly (no duplicate state store).

**Deliverable:** legend panel stays synchronized with plot/view lifecycle.

---

### Phase 4 — Visibility semantics and Plotly legend migration

1. Add feature flag/config switch for migration:
   - temporary dual-mode (optional),
   - canonical side-panel mode.
2. Set Plotly layout default to `showlegend=False` in canonical mode.
3. Ensure parity:
   - toggle off => plot hidden in active view renders,
   - toggle on => plot re-renders and remains in panel.
4. Handle legacy `"legendonly"` states safely during migration.

**Deliverable:** toolkit legend replaces Plotly legend for primary interactions.

---

### Phase 5 — LaTeX labels and row UX hardening

1. Render labels through `HTMLMath`.
2. Define plain-text fallback and escaping behavior.
3. Validate label sources:
   - explicit `label=...`,
   - default `id`,
   - mixed math/plain text.
4. Add empty/error-safe row rendering policy.

**Deliverable:** reliable label rendering for notebook usage.

---

### Phase 6 — Optional row actions (deferred v1.1 track)

1. Reserve action slot (e.g., cog button) per row.
2. Implement minimal style editing if approved:
   - opacity,
   - color,
   - dash,
   - thickness,
   - sampling points.
3. Route updates through existing plot setters or `plot.update(...)`.
4. Keep advanced actions behind feature flag until stable.

**Deliverable:** extensible row action foundation without destabilizing v1.

---

### Phase 7 — Documentation and migration notes

1. Update `docs/README.md` and relevant guide pages with new legend workflow.
2. Add migration note mapping old Plotly legend interactions to new panel controls.
3. Update project and bug references impacted by legend behavior changes.

**Deliverable:** docs aligned with shipped behavior.

---

## Description of test suite for acceptance

### Unit tests

1. **Legend manager lifecycle**
   - row add/update/remove,
   - stable ordering,
   - idempotent refresh.
2. **View filtering**
   - only active-view-member plots appear,
   - switching active view updates visible rows.
3. **Visibility synchronization**
   - row toggle updates `plot.visible`,
   - programmatic visibility update updates row state.
4. **Label rendering**
   - plain text,
   - LaTeX markup,
   - malformed input fallback.
5. **Sidebar visibility orchestration**
   - params/info/legend combinations correctly show/hide sections and container.

### Integration tests

1. `Figure.plot()` + tab switching + legend toggles remain consistent.
2. `remove_view` and plot membership changes do not leave orphan rows.
3. Plot reflow and resize behavior remains stable when sidebar sections appear/disappear.

### Regression tests

1. Parameter workflows unchanged.
2. Info panel workflows unchanged.
3. Callable-first plotting workflows unchanged.
4. Snapshot/codegen behavior remains correct when legend is disabled in Plotly layout.

## Preferable implementation sequence with safe checkpoints

- **Checkpoint A (after Phase 1):** layout supports legend section, no behavior change.
- **Checkpoint B (after Phase 3):** manager wired and synchronized, Plotly legend still available.
- **Checkpoint C (after Phase 4):** side-panel legend canonical, compatibility path still available.
- **Checkpoint D (after Phase 5):** label rendering hardened, ready for broad usage.

Each checkpoint must leave the toolkit in a releasable, functioning state.

## If consistency cannot be maintained in one phase

- Use feature flags to keep incomplete legend behavior isolated.
- Avoid partial replacement of Plotly legend without complete toggle parity.
- Gate optional row actions until core lifecycle/visibility is stable.

## Risks and mitigation

1. **Widget churn/performance for many plots**
   Mitigation: incremental updates, debounced refresh, avoid full rebuild by default.

2. **State mismatch across views**
   Mitigation: single-source `Plot` state, explicit lifecycle hooks in `Figure`.

3. **Migration confusion**
   Mitigation: release notes + dual-mode transition window.

4. **Notebook frontend variance**
   Mitigation: keep manager logic in Python and minimize frontend-specific assumptions.

## Definition of done

- Legend panel is present and synchronized with active view tabs.
- Plot visibility is controlled primarily through the legend panel.
- Labels support LaTeX rendering in notebook UI.
- Plotly internal legend is no longer required by default.
- Acceptance and regression tests pass for lifecycle, filtering, and compatibility.
