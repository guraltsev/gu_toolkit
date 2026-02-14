# Project 007: Tabbed Multi-Plot Interface

**Priority:** High
**Effort:** Large
**Impact:** Enables multiple independent plot canvases in a single notebook output, tabbed navigation, and per-plot viewport management

---

## Problem

The current `Figure` class is a **single-canvas** system. One `Figure` owns one Plotly `FigureWidget`, one set of axes, one x/y range, and one sidebar. There is no built-in way to:

1. **Display multiple independent plot canvases** (e.g. a time-domain view and a frequency-domain view side-by-side or in tabs) from a single coordinated workspace.
2. **Share parameters across canvases** while keeping viewport state (pan/zoom) independent per canvas.
3. **Defer or disable data generation** for plots that are not currently visible (e.g. a background tab), and regenerate when the user switches to that tab.

### Current Architecture Constraints

| Concern | Current location | Problem |
|---------|-----------------|---------|
| **x/y range** | `Figure._x_range`, `Figure._y_range` (default) and `Figure.current_x_range` (viewport) in `Figure.py:452-581` | Ranges are figure-level properties. Every plot on the figure shares the same default range and reacts to the same viewport. There is no concept of "this plot's own default range" vs. "the viewport the user is currently looking at". |
| **Plot-to-figure binding** | `Plot._smart_figure` back-reference + `Plot._plot_handle` (a single Plotly trace) in `figure_plot.py:104-126` | A `Plot` is hard-wired to exactly one figure and one trace. It cannot appear on two canvases (e.g. an overview tab and a detail tab) or switch canvases. |
| **Plot identity** | `Figure.plots` dict keyed by auto-generated `f_0`, `f_1`, ... IDs in `Figure.py:649-783` | IDs are adequate for single-figure use but there is no namespace for "which canvas" a plot belongs to. IDs are auto-generated and not required, making programmatic cross-referencing fragile. |
| **Rendering trigger** | `Figure.render()` iterates **all** plots unconditionally in `Figure.py:818-862` | No mechanism to skip rendering for plots whose canvas is not visible. Every parameter change re-evaluates every compiled expression. |
| **Layout** | `FigureLayout` builds a single VBox with one plot container and one sidebar in `figure_layout.py:180-490` | No Tab, Accordion, or multi-pane container. The layout is structurally a single-figure widget. |
| **Public API** | Module-level `plot()`, `parameter()` etc. delegate to a single current figure via `figure_context.py` | The context stack holds `Figure` instances. There is no concept of a "workspace" or "canvas collection" above `Figure`. |

### Motivating Use Cases

1. **Lecture demonstrations**: Show `sin(x)` in one tab and its derivative `cos(x)` in another, both controlled by the same amplitude slider `a`.
2. **Signal processing**: Time-domain waveform in Tab 1, FFT magnitude in Tab 2, phase in Tab 3 — all reacting to the same parameters but with different x-axes (time vs. frequency).
3. **Comparative exploration**: Same function plotted over different x-ranges (macro view vs. zoomed detail) without manual pan/zoom.
4. **Performance**: A figure with 20 expressions across 4 tabs only evaluates the 5 expressions on the active tab when a slider moves.

---

## Scope

This project touches every layer of the plotting stack:

| Layer | Files affected |
|-------|---------------|
| **Data model** | `figure_plot.py` — Plot identity, multi-handle support, visibility-gated rendering |
| **Range model** | `Figure.py` — Separate default range from viewport range; per-canvas range state |
| **Rendering** | `Figure.py` — Conditional render based on tab visibility |
| **Layout / UI** | `figure_layout.py` — Tabbed container, per-tab plot panes, shared sidebar |
| **Public API** | `Figure.py`, `figure_context.py` — New canvas/tab creation helpers |
| **Responsive container** | `PlotlyPane.py` — Multiple pane instances, resize handling per tab |
| **Parameters** | `figure_parameters.py` — Shared parameter manager across canvases |

See `plan.md` for the detailed implementation plan.
