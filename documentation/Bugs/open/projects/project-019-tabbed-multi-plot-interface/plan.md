# Project 019: Tabbed Multi-Plot Interface — Implementation Plan

**Companion document:** `summary.md`

---

## 1) Terminology

- **Workspace**: top-level coordinator (current `Figure`) holding parameters, views, and layout.
- **View**: one independent plot surface (one tab), with its own default ranges and viewport state.
- **Plot**: one mathematical expression/rendering definition.
- **PlotHandle**: one concrete trace of a plot on one view.
- **Default range**: user-defined initial x/y range for a view.
- **Viewport range**: current pan/zoom range for that view.

> Naming decision: use **View** in user-facing API; internal class may still be named `Canvas` during transition.

---

## 2) Design Principles

1. **Independent view state**: each view owns default range and viewport range.
2. **Shared parameter model**: one parameter manager per workspace.
3. **Visibility-aware render**: only active view computes; inactive views are marked stale.
4. **Explicit identity**: every plot and every view has stable IDs.
5. **Simple default API**: single-view usage remains straightforward.
6. **Resolve decided items now**: no open-question placeholders for already decided behavior.

---

## 3) Phase 0 — Prerequisite Refactors

### 0.1 Range semantics cleanup in `Figure`

- Split range data into:
  - `_default_x_range`, `_default_y_range`
  - `_viewport_x_range`, `_viewport_y_range` (nullable)
- `current_*_range` returns viewport when present, otherwise default.
- Setting default range resets viewport to `None` for that axis.

### 0.2 Plot identity as first-class attribute

- Add required `Plot.id`.
- Ensure `Figure.plot(...)` assigns deterministic IDs when omitted.
- Include `id` in plot repr/debug output.

### 0.3 Explicit plot-to-view membership model

- Replace implicit single private handle ownership with explicit membership map (`plot_id -> handles by view_id`).

---

## 4) Phase 1 — View Model

### 1.1 Introduce `View` abstraction

Suggested fields:

- `id: str`
- `title: str`
- `x_label: str | None`
- `y_label: str | None`
- `default_x_range: tuple[float, float]`
- `default_y_range: tuple[float, float] | None`  *(None = autoscale y)*
- `viewport_x_range: tuple[float, float] | None`
- `viewport_y_range: tuple[float, float] | None`
- `is_active: bool`
- `is_stale: bool`
- Own `FigureWidget` + pane object

### 1.2 Autoscaling policy (decided)

- If view has explicit `default_y_range`, keep autorange disabled.
- If view has `default_y_range is None`, enable y autorange for that view.
- Keep x-range explicit unless future requirement changes.

---

## 5) Phase 2 — PlotHandle & Multi-View Plot Membership

### 2.1 Introduce `PlotHandle`

A `PlotHandle` binds one `Plot` + one `View` + one plotly trace and stores per-view sampled data cache.

### 2.2 `Plot` handle structure

- `Plot._handles: dict[str, PlotHandle]` keyed by `view_id`.
- `Plot.render(view_id: str | None = None)`:
  - with `view_id`: render only that view
  - without `view_id`: render only active-view handles

### 2.3 Membership APIs

- `plot.add_to_view(view)`
- `plot.remove_from_view(view)`
- `plot.views` returns membership IDs

---

## 6) Phase 3 — Rendering Pipeline

### 3.1 Visibility-gated updates

On parameter changes:

- active view(s): render immediately
- inactive views: `is_stale = True`

On tab switch to a stale view:

- render once
- clear stale flag

### 3.2 Relayout handling per view

- Register relayout callback per view.
- Maintain independent debounce/throttle per view.

---

## 7) Phase 4 — Tabbed Layout

### 4.1 Tab container

- Use `ipywidgets.Tab` for view switching.
- Each tab child is a view pane.

### 4.2 Shared sidebar with scoped info cards (decided)

Sidebar structure:

1. parameter controls (workspace-scoped)
2. shared info cards (always shown)
3. per-view info cards region (changes by active view)

### 4.3 Title and labels (decided)

- Workspace title appears above tab region.
- Active view title appears above its plotting pane.
- Per-view x/y labels map to that view’s axes.

---

## 8) Phase 5 — Public API

### 5.1 View lifecycle

```python
fig = Figure(title="Signal Analysis")
fig.add_view("time", title="Time Domain", x_range=(0, 10), y_range=None)
fig.add_view("freq", title="Frequency Domain", x_range=(0, 500), y_range=(0, 1))
```

### 5.2 View selection context

```python
with fig.view("time"):
    plot(t, signal, id="signal")
    info("Time-domain note", view="time")
```

### 5.3 Plot targeting

```python
fig.plot(x, expr, view="time", id="curve_1")
fig.plot(x, expr2, view=["time", "freq"], id="shared_curve")
```

### 5.4 Info APIs (decided + cleanup)

- Keep/introduce one primary API shape: `fig.info(..., view: str | None = None)`.
- `view=None` => shared info card.
- `view="time"` => visible only when that view is active.
- **Remove** old methods:
  - `fig.get_info_output()`
  - `fig.add_info_component()`
- No backward compatibility requirement for these removed methods.

---

## 9) Phase 6 — Testing Plan

### 6.1 Unit tests

- range semantics: defaults vs viewport per view
- autoscale y policy by `y_range is None` rule
- plot identity uniqueness and stability
- multi-view plot handle creation/removal
- active-only rendering + stale-on-inactive
- tab switch triggers stale render once
- info-card visibility rules (shared + per-view)
- figure title and per-view title/axis labels

### 6.2 Integration notebook checks

- two-tab shared-parameter demo
- time/frequency demo with mixed y autoscale behavior
- per-view info cards disappear/appear correctly on tab switch

---

## 10) Deferred Items Register

1. Per-view parameter dependency subsets for smarter stale marking.
2. Drag-and-drop moving plots between views.
3. Non-tab layouts (grid/split).

---

## 11) Risks & Mitigations

- **Hidden-tab sizing quirks**: trigger resize on view activation.
- **State drift between model and plotly widget**: keep a single update path per view.
- **Performance with many views**: rely on stale flags + active-only computation.
- **API confusion (`canvas` vs `view`)**: document `view` as preferred public name and treat `canvas` as transitional alias if temporarily needed.

---

## 12) Implementation Sequence

1. Phase 0 range/identity groundwork
2. Phase 1 `View` abstraction + autoscale semantics
3. Phase 2 PlotHandle multi-view support
4. Phase 3 visibility-gated rendering
5. Phase 4 tabbed layout + scoped info cards + titles/labels
6. Phase 5 API wiring and old-info API removal
7. Phase 6 tests and examples
