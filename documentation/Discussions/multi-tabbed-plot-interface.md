# Goal
I want to adapt the code to support mutiple plots in a tabbed interface. This requires multiple changes, not least the following:
- do not treat ranges as intrinsic to the figure but rather to each separate plotting instance
- distinguish between default x and y ranges (for a given figure) and current viewport ranges (for that figure)
- Make sure plots have identifiers. Make sure plot objects store on which plot they are appearing in a more transparent way (not just via one internal handle)
- Potentially, allow plots to have multiple plot handles and make them generate the corresponding data for each plot separately. 
- disable data generation if plot is not currently being displayed. Regenerate on display
- implement a tabbed interface 
- develop an intuitive public api for creating new plot outputs. 
More?

write a summary and a comprehensive and detailed plan for this functionality into documentation\bugs\open\projects\project-019-NAME_TO_DESCRIBE_THIS PROJECT\summary.md and documentation\bugs\open\projects\project-019-NAME_TO_DESCRIBE_THIS PROJECT\plan.md

# Plan Summay 

### Summary highlights

The **summary** documents the core problem: `Figure` is a single-canvas system where ranges, rendering, and layout are all tied to one Plotly widget. It maps each constraint to its current file/line location and lists four motivating use cases (lecture demos, signal processing, comparative exploration, performance).

### Plan highlights

The **plan** is organized into 8 phases:

| Phase | Focus |
|-------|-------|
| **0** | Prerequisite refactors — separate default range from viewport range, add `Plot.id` attribute |
| **1** | Range model rework — `_CanvasRangeState` data class, per-canvas range independence |
| **2** | Plot identity & multi-handle — `PlotHandle` class so one `Plot` can appear on multiple canvases |
| **3** | Canvas abstraction — `Canvas` class wrapping its own `FigureWidget` + `PlotlyPane` + range state |
| **4** | Visibility-gated rendering — only active tab re-evaluates; inactive tabs marked stale |
| **5** | Tabbed layout — `TabbedLayout` using `ipywidgets.Tab`, shared sidebar for parameters |
| **6** | Public API — `fig.add_canvas()`, `fig.canvas()` context manager, `canvas=` argument on `plot()`, full backward compat for single-canvas usage |
| **7** | Testing & migration — unit tests per phase, migration guide, example notebooks |

It also includes 7 open questions (info panel scope, per-canvas parameter subsets, grid layout, naming) and a risk register.

# Open questions

Here are the 7 open questions from the plan:

---

**1. Info panel scope**: Should info components be per-canvas or per-workspace? The current design keeps them shared (workspace-level). Per-canvas info could be a follow-up.

**2. Per-canvas parameter subsets**: Should canvases be able to declare which parameters they care about, so that changing an irrelevant parameter doesn't mark the canvas stale? This is an optimization that could come later.

**3. Canvas-specific y_range auto-scaling**: Should each canvas independently auto-scale y-range based on its visible plots? Plotly supports this natively (`yaxis.autorange`), but it interacts with the default range concept.

**4. Drag-and-drop plot reassignment**: Should the UI allow dragging a plot from one tab to another? This is a UX nicety that could come much later.

**5. Side-by-side vs. tabbed**: Should we also support a grid layout (2x2 canvases visible simultaneously) in addition to tabs? The Canvas abstraction supports this — only the layout manager changes.

**6. Canvas-level titles and axis labels**: Should each canvas have its own title, x-label, y-label? Likely yes, as different tabs will represent different physical quantities.

**7. Naming**: Is `Canvas` the right name, or should it be `PlotPane`, `Subplot`, `View`, or `Tab`? `Canvas` avoids collision with Plotly's subplot concept and HTML canvas.

---

Which ones would you like to weigh in on first, or shall we go through them all in order?

# Answers

1. Make both available. Design a system that by default displays for all canvases but allows a simple way to make each info card be per-canvas.  the per-canvas info cards should also go in the general area but should disappear on canvas switch. 
2. Let us postpone this for now. 
3. If y_range is set, no autoscaling. If it is, then yes autoscaling.  also, the plot constructor x_ranges and y_ranges should just be the ones being set on the default first plot canvas. Each additional plot canvas should have its  own.
4. later
5. later
6. yes. Support titles both for the full figure (top, centered) and for single canvases (centered over canvas display, below general title. per/canvas x-label and y-label. View is good.

#Comment
Good call. A concrete API for that could be:

```python
# Default: workspace-level, visible on all tabs
fig.info("This shows on every tab")

# Per-canvas: pass canvas= to scope it
fig.info("Only on time tab", canvas="time")

# Or via context manager
with fig.canvas("time"):
    info("Only on time tab")
```

Implementation-wise, this means:
- **info cards** go in the sidebar (outside the `Tab` widget), as currently planned.
- The `canvas=` argument (or active canvas context) is the only differentiator — no separate method name needed.

The same pattern would apply to `fig.get_info_output()` and `fig.add_info_component()` — they'd accept an optional `canvas=` parameter, defaulting to `None` (= shared).

I'll update the plan with this decision. What's your take on **question 2** — per-canvas parameter subsets (so changing an irrelevant parameter doesn't trigger a stale-mark on canvases that don't use it)?

# Additional Comment

Remove `fig.get_info_output()` and `fig.add_info_component()`. This is old unused codepath. Do not worry about backwards compatibility. 