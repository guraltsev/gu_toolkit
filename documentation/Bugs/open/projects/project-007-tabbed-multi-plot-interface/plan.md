# Project 007: Tabbed Multi-Plot Interface — Implementation Plan

**Companion document:** `summary.md` (problem statement, motivation, scope)

---

## Table of Contents

1. [Terminology](#1-terminology)
2. [Design Principles](#2-design-principles)
3. [Phase 0 — Prerequisite Refactors](#3-phase-0--prerequisite-refactors)
4. [Phase 1 — Range Model Rework](#4-phase-1--range-model-rework)
5. [Phase 2 — Plot Identity & Multi-Handle Support](#5-phase-2--plot-identity--multi-handle-support)
6. [Phase 3 — Canvas Abstraction](#6-phase-3--canvas-abstraction)
7. [Phase 4 — Visibility-Gated Rendering](#7-phase-4--visibility-gated-rendering)
8. [Phase 5 — Tabbed Layout](#8-phase-5--tabbed-layout)
9. [Phase 6 — Public API](#9-phase-6--public-api)
10. [Phase 7 — Testing & Migration](#10-phase-7--testing--migration)
11. [Open Questions](#11-open-questions)
12. [Risk Register](#12-risk-register)

---

## 1. Terminology

| Term | Definition |
|------|-----------|
| **Workspace** | The top-level coordinator (currently `Figure`). Owns parameters, canvases, and the root widget. |
| **Canvas** | One independent plotting surface: one Plotly `FigureWidget`, its own axes, its own default x/y range, and its own viewport state. Corresponds to one tab in the UI. |
| **Plot** | A single curve (SymPy expression compiled to NumPy). May appear on one or more canvases. |
| **PlotHandle** | A concrete Plotly trace on a specific canvas. A Plot with N canvas memberships has N PlotHandles. |
| **Default range** | The x/y range a canvas starts with (set by the user at creation time or inherited from the workspace). |
| **Viewport range** | The x/y range the user is currently viewing after pan/zoom. Per-canvas, ephemeral. |
| **Active canvas** | The canvas currently displayed (selected tab). Only active canvases render on parameter changes. |

---

## 2. Design Principles

1. **Backward compatibility**: A `Figure` with zero explicit canvases behaves identically to today. The single-canvas case is the default, not a special case.
2. **Shared parameters, independent viewports**: All canvases in a workspace share one `ParameterManager`. Each canvas has its own range state and pan/zoom viewport.
3. **Lazy rendering**: Plots on inactive canvases are not re-evaluated until the canvas becomes active. On activation, stale plots are re-rendered once.
4. **Explicit identity**: Every plot and every canvas has a user-visible, stable string ID. Auto-generated IDs remain available but are documented as a convenience, not the norm.
5. **Composition over inheritance**: New concepts (Canvas, PlotHandle) are new classes, not subclasses of existing ones.
6. **Minimal API surface**: The common case (one canvas, a few plots, a few sliders) should require no more code than today.

---

## 3. Phase 0 — Prerequisite Refactors

These changes are independent of the tabbed interface and can be landed first.

### 0.1 Separate default range from viewport range on Figure

**Files:** `Figure.py`

Currently `Figure._x_range` and `Figure._y_range` serve double duty: they are both the "initial range" and the "source of truth when no user pan/zoom has occurred". The viewport is read from `self._figure.layout.xaxis.range`, which is `None` until the first Plotly relayout event.

**Change:**
- Rename `_x_range` / `_y_range` to `_default_x_range` / `_default_y_range`.
- Add `_viewport_x_range` / `_viewport_y_range` (initially `None`, updated by `_on_relayout`).
- `current_x_range` returns `_viewport_x_range if _viewport_x_range is not None else _default_x_range`.
- `x_range` getter returns `_default_x_range` (the user-set initial range).
- `x_range` setter sets `_default_x_range` AND resets `_viewport_x_range` to `None` (i.e. user explicitly setting range also resets viewport).

This clarifies semantics without changing external behavior.

### 0.2 Make Plot.id a first-class required attribute

**Files:** `figure_plot.py`, `Figure.py`

Currently the `id` is stored as a key in `Figure.plots` dict but not on the `Plot` instance itself. The Plot knows its figure via `_smart_figure` but does not know its own id.

**Change:**
- Add `self._id: str` to `Plot.__init__`.
- Expose as read-only property `Plot.id`.
- `Figure.plot()` passes the (auto-generated or user-supplied) id into the constructor.
- `Plot.__repr__` includes the id.

### 0.3 Expose Plot.figure as a public property (already exists, verify)

**Files:** `figure_plot.py`

Verify that `Plot.figure` (or `Plot.workspace`) is a clean public property. Currently `Plot._smart_figure` is the back-reference. Ensure there is a public `Plot.figure` property (there appears to be one at `figure_plot.py:320-340`). If it exists, keep it. If not, add it.

---

## 4. Phase 1 — Range Model Rework

### 1.1 Introduce per-canvas range state

**New concept.** Once the Canvas abstraction exists (Phase 3), each canvas carries:

```python
class _CanvasRangeState:
    default_x_range: Tuple[float, float]
    default_y_range: Tuple[float, float]
    viewport_x_range: Optional[Tuple[float, float]]  # None = not panned/zoomed
    viewport_y_range: Optional[Tuple[float, float]]
```

Until Phase 3 is reached, the Figure itself holds this state (Phase 0.1 already prepared it).

### 1.2 Plot x_domain remains per-plot

The existing `Plot.x_domain` property (an optional explicit domain override) stays as-is. It is orthogonal to the canvas range: it says "this function is only defined on [a, b]", regardless of which canvas viewport is active.

### 1.3 Render uses effective range

The render method computes:

```
effective_x_min = max(viewport_x_min, plot.x_domain[0]) if plot.x_domain else viewport_x_min
effective_x_max = min(viewport_x_max, plot.x_domain[1]) if plot.x_domain else viewport_x_max
```

This is largely what `figure_plot.py:529-551` already does, but the viewport will now come from the **canvas**, not from the workspace-level figure.

---

## 5. Phase 2 — Plot Identity & Multi-Handle Support

### 2.1 PlotHandle class

**New file:** `figure_plot_handle.py` (or inner class of `figure_plot.py`)

```python
class PlotHandle:
    """A concrete Plotly trace on one canvas for one Plot."""

    def __init__(self, plot: Plot, canvas: Canvas, trace: go.Scatter):
        self._plot = plot
        self._canvas = canvas
        self._trace = trace
        self._x_data: Optional[np.ndarray] = None
        self._y_data: Optional[np.ndarray] = None

    @property
    def plot(self) -> Plot:
        return self._plot

    @property
    def canvas(self) -> Canvas:
        return self._canvas

    def update_data(self, x: np.ndarray, y: np.ndarray) -> None:
        """Push new sample data into the Plotly trace."""
        self._x_data = x
        self._y_data = y
        self._trace.x = x
        self._trace.y = y
```

### 2.2 Refactor Plot to support multiple handles

**Files:** `figure_plot.py`

Currently `Plot` has:
- `self._plot_handle` — a single Plotly `go.Scatter` trace
- `self._x_data`, `self._y_data` — cached data for that trace

**Change:**
- Replace `_plot_handle` with `_handles: Dict[str, PlotHandle]` keyed by canvas id.
- `_x_data` / `_y_data` move into `PlotHandle`.
- `Plot.render()` becomes `Plot.render(canvas_id: Optional[str] = None)`:
  - If `canvas_id` is given, render only that handle.
  - If `None`, render all handles whose canvas is active.

### 2.3 Plot.add_to_canvas / Plot.remove_from_canvas

```python
def add_to_canvas(self, canvas: Canvas) -> PlotHandle:
    """Create a new Plotly trace on the given canvas and register a PlotHandle."""

def remove_from_canvas(self, canvas: Canvas) -> None:
    """Remove the trace from the canvas and discard the PlotHandle."""
```

### 2.4 Backward compatibility

When a workspace has only the implicit default canvas, `Plot._plot_handle` (deprecated property) returns `_handles[DEFAULT_CANVAS_ID]`. This ensures any existing code that accidentally accesses the private attribute still works.

---

## 6. Phase 3 — Canvas Abstraction

### 3.1 Canvas class

**New file:** `figure_canvas.py`

```python
class Canvas:
    """One independent plotting surface within a Workspace."""

    def __init__(
        self,
        id: str,
        workspace: "Figure",
        x_range: Tuple[float, float],
        y_range: Tuple[float, float],
        title: str = "",
        sampling_points: int = 500,
    ):
        self._id = id
        self._workspace = workspace
        self._figure_widget = go.FigureWidget(...)  # Own Plotly widget
        self._pane = PlotlyPane(self._figure_widget, ...)
        self._range_state = _CanvasRangeState(x_range, y_range)
        self._is_active = False
        self._is_stale = False  # True if params changed while inactive
        self._handles: Dict[str, PlotHandle] = {}  # plot_id -> handle

    @property
    def id(self) -> str: ...

    @property
    def is_active(self) -> bool: ...

    def activate(self) -> None:
        """Called when user switches to this tab."""
        self._is_active = True
        if self._is_stale:
            self._render_all()
            self._is_stale = False

    def deactivate(self) -> None:
        self._is_active = False

    def mark_stale(self) -> None:
        """Called when a parameter changes while this canvas is inactive."""
        self._is_stale = True

    def _render_all(self) -> None:
        for handle in self._handles.values():
            handle.plot.render(canvas_id=self._id)

    # Range properties
    @property
    def x_range(self) -> Tuple[float, float]: ...        # default range
    @property
    def current_x_range(self) -> Tuple[float, float]: ...  # viewport or default
    # ... y equivalents ...
```

### 3.2 Integrate Canvas into Figure (Workspace)

**Files:** `Figure.py`

Add to `Figure.__init__`:
```python
self._canvases: Dict[str, Canvas] = {}
self._active_canvas_id: Optional[str] = None
```

The existing `self._figure` (single `FigureWidget`) and `self._pane` become the **default canvas** — created lazily on first `fig.plot()` call if no explicit canvas has been added.

### 3.3 Default canvas backward compatibility

If `Figure.plot()` is called and no canvases exist, auto-create a default canvas with id `"default"` using the workspace's `x_range` / `y_range`. This canvas is always active. The existing `fig.x_range`, `fig.y_range`, `fig.current_x_range` properties delegate to the default canvas when only one canvas exists. When multiple canvases exist, `fig.x_range` raises a deprecation warning directing users to `fig.canvases["name"].x_range`.

---

## 7. Phase 4 — Visibility-Gated Rendering

### 4.1 Modify Figure.render()

**Files:** `Figure.py:818-862`

Current behavior:
```python
for plot in self.plots.values():
    plot.render()
```

New behavior:
```python
for canvas in self._canvases.values():
    if canvas.is_active:
        canvas._render_all()
    else:
        canvas.mark_stale()
```

### 4.2 Tab-switch triggers re-render

When a tab becomes active (see Phase 5), `canvas.activate()` checks `_is_stale` and calls `_render_all()` if needed. This gives immediate visual update on tab switch with no wasted computation while the tab was hidden.

### 4.3 Per-canvas relayout throttling

Each canvas has its own `QueuedDebouncer` for pan/zoom events, since each canvas has its own `FigureWidget`. The existing throttle logic in `Figure._throttled_relayout` is moved into `Canvas` (or a per-canvas callback is registered).

---

## 8. Phase 5 — Tabbed Layout

### 5.1 TabbedLayout class

**New file:** `figure_tabbed_layout.py` (or extend `figure_layout.py`)

Uses `ipywidgets.Tab` to host multiple canvases:

```python
class TabbedLayout:
    """Layout manager for multi-canvas workspaces."""

    def __init__(self, workspace: "Figure"):
        self._workspace = workspace
        self._tab_widget = widgets.Tab()
        self._tab_widget.observe(self._on_tab_change, names="selected_index")

        # Shared sidebar (parameters + info) sits outside the tabs
        self._sidebar = widgets.VBox(...)
        self._root = widgets.HBox([
            widgets.VBox([self._tab_widget]),
            self._sidebar,
        ])

    def add_canvas(self, canvas: Canvas, label: str) -> None:
        """Add a new tab for the given canvas."""
        children = list(self._tab_widget.children) + [canvas.pane.widget]
        self._tab_widget.children = children
        self._tab_widget.set_title(len(children) - 1, label)

    def remove_canvas(self, canvas_id: str) -> None: ...

    def _on_tab_change(self, change) -> None:
        old_idx = change.get("old")
        new_idx = change["new"]
        if old_idx is not None:
            self._workspace._canvases_by_index[old_idx].deactivate()
        self._workspace._canvases_by_index[new_idx].activate()
```

### 5.2 Layout selection

`FigureLayout` remains the layout for single-canvas (default) workspaces. `TabbedLayout` is used when `len(canvases) > 1`. The switch happens automatically when the first non-default canvas is added, or the user can opt in explicitly:

```python
fig = Figure(layout="tabbed")  # explicit
# or
fig.add_canvas("freq", x_range=(0, 1000))  # triggers switch from single to tabbed
```

### 5.3 Shared sidebar

The parameter sliders and info panel are **shared** across tabs — they sit outside the `Tab` widget. This matches the use case: parameters are workspace-level, not canvas-level. The info panel may optionally be per-canvas in a future phase.

### 5.4 Responsive behavior

Each `Canvas` owns its own `PlotlyPane` instance. `PlotlyPane` already handles ResizeObserver and responsive sizing. When a tab is hidden, the browser does not fire resize events for it, so no special handling is needed. On tab activation, a manual resize trigger may be needed to ensure the plot fills the container. This can be done by calling `PlotlyPane._trigger_resize()` in `Canvas.activate()`.

---

## 9. Phase 6 — Public API

### 6.1 Canvas creation

```python
# Method 1: On Figure
fig = Figure(x_range=(-5, 5), y_range=(-3, 3))
time_canvas = fig.add_canvas("time", title="Time Domain", x_range=(0, 10))
freq_canvas = fig.add_canvas("freq", title="Frequency Domain", x_range=(0, 500))

# Method 2: Context manager style
with fig.canvas("time"):
    plot(t, signal_expr)
with fig.canvas("freq"):
    plot(f, fft_expr)
```

### 6.2 Plotting on a specific canvas

```python
# Explicit canvas target
fig.plot(x, sin(x), canvas="time", id="sin")

# Or via canvas object
time_canvas.plot(x, sin(x), id="sin")

# Or via context manager (module-level helpers)
with fig.canvas("time"):
    plot(x, sin(x), id="sin")
```

### 6.3 Plotting on multiple canvases

```python
# A plot can appear on multiple canvases
fig.plot(x, sin(x), canvas=["time", "overview"], id="sin")
```

### 6.4 Single-canvas API (unchanged)

```python
# This still works exactly as before — no canvas argument needed
fig = Figure(x_range=(-5, 5))
fig.plot(x, sin(x))
fig.plot(x, cos(x))
```

### 6.5 Module-level helpers

The existing module-level `plot()`, `parameter()`, etc. in `figure_context.py` / `Figure.py` continue to work. When a canvas context is active (via `with fig.canvas("name"):`), `plot()` targets that canvas. Otherwise it targets the default canvas.

```python
with fig:
    parameter(a)
    with fig.canvas("tab1"):
        plot(x, a * sin(x))
    with fig.canvas("tab2"):
        plot(x, a * cos(x))
```

### 6.6 Accessing canvases

```python
fig.canvases                      # Dict[str, Canvas] (read-only view)
fig.canvases["time"]              # Access by id
fig.active_canvas                 # Currently displayed Canvas
fig.active_canvas_id              # str id of active canvas
```

---

## 10. Phase 7 — Testing & Migration

### 7.1 Unit tests

| Test area | What to test |
|-----------|-------------|
| Range model | Default range vs. viewport range; setting x_range resets viewport; per-canvas ranges are independent |
| Plot identity | `Plot.id` is set and stable; auto-generated IDs are unique |
| PlotHandle | Creating/removing handles; data pushed to correct trace |
| Canvas | activate/deactivate; stale flag; render-on-activate |
| Visibility gating | Parameter change only renders active canvas; inactive canvas marked stale |
| Tabbed layout | Tab switch calls activate/deactivate; widget children correct |
| Public API | `fig.plot(canvas="x")` routes correctly; context manager targets correct canvas; single-canvas backward compat |
| Backward compat | Existing single-figure notebooks produce identical output |

### 7.2 Migration guide

No breaking changes for single-canvas usage. Document:

- `fig.x_range` now returns the **default** range, not the viewport. Use `fig.current_x_range` for viewport. (This is already the case — just make it clearer.)
- New `fig.add_canvas()` / `fig.canvas()` API for multi-plot usage.
- `Plot._plot_handle` is deprecated; use `Plot.handles` dict or `Plot.handle(canvas_id)`.

### 7.3 Example notebooks

Create at least two example notebooks:

1. **Basic tabbed demo**: Two tabs with different functions, shared slider.
2. **Signal processing demo**: Time domain + frequency domain tabs with shared parameters.

---

## 11. Open Questions

1. **Info panel scope**: Should info components be per-canvas or per-workspace? Current design keeps them shared (workspace-level). Per-canvas info could be a follow-up.

2. **Per-canvas parameter subsets**: Should canvases be able to declare which parameters they care about, so that changing an irrelevant parameter doesn't mark the canvas stale? This is an optimization that could come later.

3. **Canvas-specific y_range auto-scaling**: Should each canvas independently auto-scale y-range based on its visible plots? Plotly supports this natively (`yaxis.autorange`), but it interacts with the default range concept.

4. **Drag-and-drop plot reassignment**: Should the UI allow dragging a plot from one tab to another? This is a UX nicety that could come much later.

5. **Side-by-side vs. tabbed**: Should we also support a grid layout (2x2 canvases visible simultaneously) in addition to tabs? The Canvas abstraction supports this — only the layout manager changes.

6. **Canvas-level titles and axis labels**: Should each canvas have its own title, x-label, y-label? Likely yes, as different tabs will represent different physical quantities.

7. **Naming**: Is `Canvas` the right name, or should it be `PlotPane`, `Subplot`, `View`, or `Tab`? `Canvas` avoids collision with Plotly's subplot concept and HTML canvas.

---

## 12. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Breaking existing notebooks | Medium | High | Phase 0 refactors are non-breaking; default canvas auto-creation preserves single-canvas behavior; comprehensive backward-compat tests |
| PlotlyPane resize issues in hidden tabs | High | Medium | Trigger manual resize in `Canvas.activate()`; test across JupyterLab and VS Code notebook environments |
| Performance regression (multiple FigureWidgets) | Medium | Medium | Each canvas only renders when active; benchmark with 4 canvases x 5 plots |
| ipywidgets.Tab styling conflicts | Low | Low | Use custom CSS classes; test with default JupyterLab theme |
| Scope creep into subplot/grid layout | Medium | Medium | Explicitly defer grid layout to a separate project; keep this project focused on tabs |
| Complex context manager nesting (`with fig: with fig.canvas:`) | Low | Medium | Clear error messages for misuse; document the nesting rules |

---

## Implementation Order Summary

```
Phase 0  (prerequisite, can land independently)
  0.1  Separate default range from viewport range
  0.2  Add Plot.id attribute
  0.3  Verify Plot.figure public property

Phase 1  (range model, builds on Phase 0)
  1.1  _CanvasRangeState data class
  1.2  Confirm Plot.x_domain stays per-plot
  1.3  Render uses canvas-sourced effective range

Phase 2  (plot identity & multi-handle, builds on Phase 0)
  2.1  PlotHandle class
  2.2  Refactor Plot for multiple handles
  2.3  add_to_canvas / remove_from_canvas
  2.4  Backward compat shim for _plot_handle

Phase 3  (canvas abstraction, builds on Phases 1 & 2)
  3.1  Canvas class
  3.2  Integrate into Figure
  3.3  Default canvas backward compat

Phase 4  (visibility gating, builds on Phase 3)
  4.1  Conditional render in Figure.render()
  4.2  Re-render on tab switch
  4.3  Per-canvas relayout throttling

Phase 5  (tabbed layout, builds on Phases 3 & 4)
  5.1  TabbedLayout class
  5.2  Layout selection logic
  5.3  Shared sidebar
  5.4  Responsive resize on tab switch

Phase 6  (public API, builds on Phase 5)
  6.1  Canvas creation API
  6.2  Plotting with canvas target
  6.3  Multi-canvas plot membership
  6.4  Single-canvas unchanged API
  6.5  Module-level helpers with canvas context
  6.6  Canvas accessors

Phase 7  (testing & docs, throughout)
  7.1  Unit tests per phase
  7.2  Migration guide
  7.3  Example notebooks
```
