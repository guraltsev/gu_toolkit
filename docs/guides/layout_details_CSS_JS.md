# Layout, Geometry, CSS, and JS Architecture Guide

This guide replaces the older modal-only `layout_details_CSS_JS.md`.

The previous version documented only the slider settings modal and still described an outdated figure layout in terms of `plot_container` and tab hosting. The current code has moved to a different architecture:

- one stable `FigureWidget` and one stable `PlotlyPane` per view
- one persistent page host per view inside `FigureLayout.view_stage`
- a lightweight selector bar instead of `widgets.Tab`
- browser-side measurement and resize handled by `PlotlyResizeDriver`

Read this document together with `docs/develop_guide/develop_guide.md`. That file explains ownership by concern. This file explains the concrete layout, geometry, CSS, and frontend-JS contracts.

---

## 1. Authoritative source files

When the code and docs disagree, trust the current source files below.

| File | What it currently owns |
|---|---|
| `src/gu_toolkit/figure_layout.py` | Figure widget tree and geometry intent |
| `src/gu_toolkit/Figure.py` | Layout orchestration, view switching, explicit reflow requests |
| `src/gu_toolkit/figure_view.py` | Stable per-view runtime (`FigureWidget`, `PlotlyPane`, ranges, labels) |
| `src/gu_toolkit/figure_view_manager.py` | View registry, active-view state, stale flags |
| `src/gu_toolkit/PlotlyPane.py` | Pane wrapper, frontend resize driver, browser-side Plotly sizing |
| `src/gu_toolkit/figure_plot.py` | Per-view trace allocation and active-view rendering |
| `src/gu_toolkit/figure_parameters.py` | Parameter control attachment into sidebar |
| `src/gu_toolkit/Slider.py` | Slider modal CSS and hosted/global overlay behavior |
| `src/gu_toolkit/figure_info.py` | Info section outputs/cards and view-scoped visibility |
| `src/gu_toolkit/figure_legend.py` | Legend sidebar rows and light appearance CSS |

---

## 2. Mental model: four different layout layers

The current stack has four layers that must be kept separate when reasoning about bugs.

### Layer A — Python orchestration state
This is the world of `Figure`, `View`, `FigureLayout`, and the managers.

Examples:

- which view is active
- whether the sidebar is visible
- whether full-width mode is on
- which widget is attached to which view page
- what `ipywidgets.Layout(...)` traits have been assigned

This layer knows intent. It does **not** know actual pixel sizes.

### Layer B — ipywidgets widget tree and layout traits
This layer is the tree of `VBox`, `HBox`, `Box`, `ToggleButtons`, `Output`, and so on.

Examples:

- `view_stage.layout.height = "60vh"`
- `sidebar_container.layout.flex = "0 1 380px"`
- `host_box.layout.display = "flex"` or `"none"`

This layer is still declarative. It describes how the browser should lay out the widgets, but it does not measure the result.

### Layer C — explicit CSS classes and inline DOM styling
This layer comes from two places:

1. CSS injected through widget HTML/style helpers (`Slider.py`, tiny legend styling)
2. inline DOM styles written by frontend JS (`PlotlyResizeDriver`)

Examples:

- `.smart-slider-settings-modal-hosted`
- `.smart-slider-modal-host`
- `plotEl.style.height = "...px"`
- `plotEl.style.maxWidth = "...px"`

### Layer D — actual browser geometry
This is the only layer where real measured size exists.

Examples:

- `host.getBoundingClientRect()`
- `.js-plotly-plot` rect
- clip ancestor rect
- Plotly runtime layout size after `Plots.resize(...)`

Only the browser can tell you the true final width/height. Python cannot infer this reliably from `ipywidgets.Layout` traits alone.

**Key rule:** layout bugs often happen because Layer A/B intent and Layer D measured reality diverge.

---

## 3. Ownership map for layout and responsive behavior

### `FigureLayout`
`FigureLayout` owns the widget tree and geometry intent only.

It owns:

- title row
- full-width checkbox
- view selector bar
- persistent `view_stage`
- persistent per-view page hosts
- sidebar containers
- print/output area

It does **not** own:

- plot data
- render policy
- Plotly resize behavior
- DOM measurement

### `Figure`
`Figure` is the coordinator.

It owns:

- creating the layout and managers
- creating per-view runtimes
- activating a view
- asking the active pane to reflow after geometry changes
- routing Plotly relayout events through a debouncer
- rendering active-view plots

It does **not** directly measure DOM pixels.

### `View`
Each `View` owns one stable plotting runtime for its full lifetime.

It owns:

- `figure_widget`
- `pane`
- default x/y ranges
- remembered viewport x/y ranges
- axis labels
- selector title

It does **not** decide the outer layout.

### `PlotlyPane` / `PlotlyResizeDriver`
This is the browser-sizing layer.

It owns:

- the pane wrapper and host boxes
- the hidden anywidget driver
- host resolution in the DOM
- clip-ancestor discovery
- measured size calculation
- writing width/height hints into Plotly DOM
- calling Plotly resize/autorange

This is the part of the system that actually knows whether the plot filled its available area. It now publishes an explicit frontend geometry snapshot (state, visibility, measured size, last request ids, and resize counters) back to Python for notebook diagnostics and log capture.

### `Plot`
`Plot` is about traces and data, not layout.

It owns:

- per-view trace handles
- numeric sampling
- updating active-view trace data

It should not be the place where geometry problems are debugged unless the issue is only apparent after rendering.

---

## 4. Current widget tree

The current widget tree is best understood from the inside out.

### High-level tree

```text
Figure
└── FigureLayout.root_widget  (VBox, width=100%, position=relative)
    ├── title bar
    │   ├── title_html
    │   └── full_width_checkbox
    ├── content_wrapper  (Box, flex row-wrap by default)
    │   ├── left_panel   (VBox)
    │   │   ├── view_selector  (ToggleButtons; hidden for single-view figures)
    │   │   └── view_stage     (Box; main plot-height source)
    │   │       ├── host_box[view_id="main"]
    │   │       │   └── View.pane.widget
    │   │       ├── host_box[view_id="detail"]
    │   │       │   └── View.pane.widget
    │   │       └── ...
    │   └── sidebar_container  (VBox)
    │       ├── legend_header
    │       ├── legend_box
    │       ├── params_header
    │       ├── params_box
    │       ├── info_header
    │       └── info_box
    └── print_area
        ├── print_header
        └── print_panel
            └── print_output
```

### The pane subtree for one view

```text
View.pane.widget            == PlotlyPane._wrap
└── PlotlyPane._host
    ├── View.figure_widget  (Plotly FigureWidget)
    └── PlotlyResizeDriver  (hidden anywidget)
```

### Important consequences of this tree

1. The active plot area is not the whole left panel. It is specifically `view_stage` plus the active `host_box` plus the pane subtree.
2. The view selector sits **above** `view_stage`, so it is not part of the plot-height contract.
3. Every view has a persistent `host_box`, but only the active one is visible.
4. `root_widget` is also the host used for slider settings modals, which is why it is `position="relative"`.

---

## 5. Display lifecycle: when geometry actually exists

The browser-side layout does not exist until the figure is displayed.

### Before display
Before `display(fig)` or `fig.show()`:

- Python objects exist
- widget layout traits exist
- `FigureLayout.root_widget` exists
- `View.figure_widget` and `PlotlyPane` objects exist
- no real DOM nodes or browser measurements exist yet

### After display
`Figure._ipython_display_()` displays `FigureLayout.output_widget`, which itself displays `root_widget`.

At that point:

- ipywidgets creates frontend DOM for the widget tree
- the `PlotlyResizeDriver` frontend mounts
- `ResizeObserver` and `MutationObserver` can begin observing
- the driver can search for `.js-plotly-plot`
- measured sizes become meaningful

### Why this matters
A layout bug can have two very different sources:

- Python state says the pane should be `100%` high, but the DOM never received a real pixel height
- the DOM has a real height, but the Plotly inner DOM was not resized to match

The first distinction is impossible to make before display.

### Practical debugging rule
Treat `root_widget` as the real figure root for geometry reasoning. The transient `output_widget` is a display wrapper, not the meaningful layout root.

---

## 6. Height contract

### The main source of plot height
The authoritative outer height for the plot area is `FigureLayout.view_stage`.

Current `view_stage` layout:

- `width="100%"`
- `height="60vh"`
- `min_width="0"`
- `min_height="260px"`
- `flex="1 1 560px"`
- `display="flex"`
- `flex_flow="column"`
- `overflow="hidden"`

This means the current design expects the plot area to derive its height from `view_stage`, not from the Plotly widget itself.

### Height propagation down the active plot path
For the active view, the height chain is intended to be:

```text
view_stage.height (60vh)
→ active host_box.height (100%)
→ PlotlyPane._wrap.height (100%)
→ PlotlyPane._host.height (100%)
→ Plotly DOM height set by frontend JS
```

### The active view page host
Each `_ViewPage.host_box` is created with:

- `width="100%"`
- `height="100%"`
- `min_width="0"`
- `min_height="0"`
- `display="none"` initially
- `flex="1 1 auto"`
- `overflow="hidden"`

Only the active page is switched to `display="flex"`.

### The pane wrapper and host
`PlotlyPane` adds two nested containers:

- `_wrap`: visual wrapper with `height="100%"`, padding, border, radius, overflow
- `_host`: inner host with `height="100%"`, flex column, overflow hidden

Important consequence: the *visible plot area* is smaller than `_wrap` when padding/border are present.

### What the Python side does **not** do
The current code does **not** set an explicit pixel height on the Plotly figure layout from Python. It only applies fill hints such as `width="100%"`, `height="100%"`, `min_width="0"`, and `min_height="0"` when the embedded widget exposes a real `ipywidgets.Layout`. For Plotly `FigureWidget`, the pane instead uses a dedicated plot slot container with those fill semantics so it does not confuse Plotly's graph layout with widget shell layout.

Instead, the frontend JS later writes height into:

- `.js-plotly-plot`
- `.plot-container`

That is why height bugs often appear as “the host has room, but the plot did not fill it.”

### Hidden views and height
Inactive views are `display="none"`. A hidden page should be expected to have no meaningful measurable height.

Do not interpret zero height on an inactive page as a bug by itself.

---

## 7. Width contract

### Outer layout width sharing
The default content layout is driven by `FigureLayout.content_wrapper`.

Default state:

- `display="flex"`
- `flex_flow="row wrap"`
- `align_items="stretch"`
- `width="100%"`
- `gap="8px"`

This means the left plot area and the right sidebar share a row when space allows.

### Left panel width behavior
`left_panel` uses:

- `width="100%"`
- `flex="1 1 560px"`

So the plot side is flexible and can grow/shrink with the row.

### Sidebar width behavior
`sidebar_container` uses:

- `flex="0 1 380px"`
- `min_width="260px"`
- `max_width="400px"`
- `display="none"` initially
- left padding in non-full-width mode

When the sidebar is visible, it reduces the width available to the left panel.

### Full-width toggle behavior
`FigureLayout._on_full_width_change(...)` changes the width-sharing contract.

When full-width is enabled:

- `content_wrapper.flex_flow = "column"`
- `left_panel.flex = "0 0 auto"`
- `sidebar_container.flex = "0 0 auto"`
- `sidebar_container.max_width = ""`
- `sidebar_container.width = "100%"`
- `sidebar_container.padding = "0px"`

When full-width is disabled, the layout returns to row-wrap mode.

### Browser-side width clamping
Even after Python lays out the widgets, `PlotlyResizeDriver` applies its own width rules inside the Plotly DOM.

It computes:

```text
effective width = min(host.width, clip_ancestor.width)
```

Then it writes:

- `plotEl.style.width = "100%"`
- `plotEl.style.minWidth = "0"`
- `plotEl.style.maxWidth = "<effective_w>px"`
- equivalent rules on `.plot-container`

This is specifically intended to prevent Plotly overflow when some ancestor clips the visible area.

### Why width bugs can still happen
A width problem can arise from any of these mismatches:

- the sidebar changed available width, but no active-pane reflow followed
- the clip ancestor is narrower than the host, so the plot must be clamped further than Python expects
- the host width is right, but Plotly inner DOM still reflects the previous size

---

## 8. Visibility and activation contract

### View selector
`view_selector` is a `ToggleButtons` bar.

- hidden when there is only one view
- shown when there are at least two views
- synced to `FigureLayout._active_view_id`
- selection changes call back into `Figure.set_active_view(...)`

### Persistent per-view pages
Each view has one persistent `_ViewPage.host_box` stored inside `FigureLayout`.

That host is never recreated just because the view becomes inactive. Instead:

- all hosts remain children of `view_stage`
- only the active page uses `display="flex"`
- inactive pages use `display="none"`

This is a major difference from the old `view_tabs` / `plot_container` world.

### Sidebar visibility
`FigureLayout.update_sidebar_visibility(has_params, has_info, has_legend)` controls:

- individual header display (`block` / `none`)
- section box display (`flex` / `none`)
- `sidebar_container.display`

`Figure` uses the returned boolean to decide whether a geometry-affecting visibility change occurred and whether the active pane should be reflowed.

### View-scoped info visibility
`InfoPanelManager` can create cards scoped to a specific view. Those cards are shown/hidden by switching the output widget `display` state based on the active view.

That does not change the page host contract, but it can change sidebar content size and therefore available plot width.

---

## 9. Responsive event pipeline

The current responsive story is split across Python and JS.

### Python-side pipeline
Typical geometry-affecting sequence:

1. Some change occurs:
   - full-width checkbox toggled
   - active view changed
   - sidebar visibility changed
   - view added/removed
2. `FigureLayout` mutates widget layout traits and/or visible page state.
3. `Figure` decides that the active pane should reflow.
4. `Figure` calls `self.views.current.pane.reflow()`.
5. The pane sends a custom message to the frontend driver.

There is no Python-side pixel measurement in this path.

### Plotly relayout pipeline
Separate from widget geometry, Plotly viewport changes follow another path:

1. a view’s `FigureWidget.layout` reports `xaxis.range` / `yaxis.range` changes
2. `Figure._queue_relayout(...)` stores the target view id and schedules the figure-level `QueuedDebouncer`
3. `_dispatch_relayout()` either:
   - renders the active view immediately, or
   - marks the inactive target view stale

This pipeline is about pan/zoom state and rendering. It is not itself proof that DOM resizing succeeded.

### JS-side pipeline in `PlotlyResizeDriver`
When the frontend is mounted:

1. the driver resolves its host element
2. it optionally finds the nearest clip ancestor with non-visible overflow
3. it hides the host if `defer_reveal=True`
4. it sets up:
   - `ResizeObserver` on host
   - `ResizeObserver` on clip ancestor when distinct
   - `MutationObserver` on host subtree
5. any trigger calls `schedule(reason)`
6. `schedule(...)` debounces resize work and also schedules two follow-up resizes
7. `doResize(reason)` then:
   - resolves host again
   - finds `.js-plotly-plot`
   - measures effective size
   - skips if width/height are not positive
   - skips tiny jitter after reveal
   - applies width/height hints to Plotly DOM
   - calls Plotly resize
   - optionally calls Plotly autorange
   - reveals the host after first successful resize

### Important consequence
A responsive failure can happen in either half of this pipeline:

- Python requested the wrong thing or at the wrong time
- JS received the request but measured/handled it badly

You need both halves to debug the current issue correctly.

---

## 10. CSS surface area in the current codebase

Most of the figure layout is **not** in standalone CSS files. It is in `ipywidgets.Layout(...)` trait assignments.

### Primary geometry surface: widget layout traits
Most important geometry declarations live in:

- `figure_layout.py`
- `PlotlyPane.py`
- smaller sidebar widgets in `figure_info.py` / `figure_legend.py` / `Slider.py`

That means many geometry bugs are really “Python layout trait contract” bugs rather than stylesheet bugs.

### Explicit CSS in `Slider.py`
`Slider.py` injects a real `<style>` block for two reasons:

1. compact min/max editor appearance
2. modal overlay positioning

Important slider classes:

- `.smart-slider-limit`
- `.smart-slider-settings-modal`
- `.smart-slider-settings-modal-hosted`
- `.smart-slider-settings-modal-global`
- `.smart-slider-modal-host`
- `.smart-slider-settings-panel`

### Small appearance-only CSS in `figure_legend.py`
The legend manager injects a tiny style block for `.gu-legend-toggle` appearance. This is not a geometry engine; it is only a local appearance rule.

### Frontend DOM styling in `PlotlyResizeDriver`
The JS driver directly mutates inline styles on:

- `.js-plotly-plot`
- `.plot-container`
- sometimes the host itself via deferred reveal

This is the main CSS/JS boundary for responsive Plotly behavior.

---

## 11. `PlotlyResizeDriver` frontend contract

This is the most important JS behavior in the current layout stack.

### Host resolution
By default, the driver uses its DOM parent as the host because the hidden driver widget is inserted as a sibling of the `FigureWidget` inside `PlotlyPane._host`.

### Plotly element discovery
It searches under the host for `.js-plotly-plot`.

Until that element exists, the driver cannot size Plotly.

### Clip ancestor heuristic
The driver walks up the DOM and picks the nearest ancestor whose overflow is not `visible`.

Purpose:

- the host may be nominally wide, but some ancestor may clip the visible width
- the plot should not size to a width larger than the visible clip viewport

### Effective size calculation
Current rule:

- width = `min(host.width, clip.width)` if a clip ancestor exists
- height = `host.height`

This is important: the current implementation only clamps width to clip ancestry. Height is taken from the host.

### Direct DOM mutation before Plotly resize
Before calling Plotly resize, the driver writes:

- plot height in pixels
- `.plot-container` height in pixels
- plot width/min-width/max-width
- `.plot-container` width/min-width/max-width

This is why a height issue may show up inside Plotly even when outer widgets look correctly sized.

### Deferred reveal
If `defer_reveal=True`, the host is hidden with:

- `opacity: 0`
- `pointer-events: none`

until the first successful resize.

This helps avoid initial wrong-size flash, but it also means the driver manages some visibility state itself.

### Scheduling policy
`PlotlyResizeDriver` does not resize immediately on every trigger. It:

- debounces resize work
- drops queue overflow inside the frontend debouncer
- schedules two follow-up resizes to survive animated transitions

This is useful for notebook environments, but it is also a source of observability gaps when debugging.

---

## 12. Slider modal overlay contract

This section preserves the part of the old guide that is still valid.

### Why `root_widget` is positioned relatively
`Figure` constructs `ParameterManager` with:

- `modal_host=self._layout.root_widget`

`root_widget` itself uses:

- `position="relative"`

That makes it a valid containing block for slider settings modals hosted inside the figure.

### Hosted mode
When `Slider.set_modal_host(host)` is called with a host box:

- the modal is re-parented under that host
- the host gets class `.smart-slider-modal-host`
- the modal gets class `.smart-slider-settings-modal-hosted`
- the modal uses `position: absolute; inset: 0; width: 100%; height: 100%`

Result: the settings panel overlays the whole figure root rather than the browser viewport.

### Global mode
When no modal host is used:

- the modal stays attached to the slider widget subtree
- it gets `.smart-slider-settings-modal-global`
- it uses `position: fixed; inset: 0; width: 100vw; height: 100vh`

Result: the panel overlays the browser viewport.

### Important rule
Hosted and global classes are mutually exclusive positioning contracts. Do not mix them.

---

## 13. Separation of concerns: what not to mix up

### Do not confuse geometry intent with measured geometry
Examples:

- `view_stage.layout.height == "60vh"` is intent
- `host.getBoundingClientRect().height == 423` is measured geometry

Both are necessary. They are not interchangeable.

### Do not confuse render state with layout state
Examples:

- a stale view may need a rerender but still have the right DOM size
- a freshly rendered plot may still be the wrong pixel size

`figure_plot.py` and the relayout/render pipeline are not proof that the pane sized correctly.

### Do not move JS sizing responsibility back into `FigureLayout`
`FigureLayout` should stay a pure widget/geometry-intent layer.

It should not become the owner of Plotly resize callbacks, DOM measurement, or browser heuristics again.

### Do not debug historical architecture
The current layout is **not**:

- `view_tabs`
- `plot_container`
- one shared `FigureWidget`

Some old tests and historical docs still say those names, but they are no longer the authoritative design.

---

## 14. Legacy and stale references to ignore carefully

A few stale references still exist in the repository and can mislead maintenance work.

### Stale test references
Examples currently still referencing old or removed state:

- `tests/test_project019_phase12.py` refers to `fig._layout.view_tabs`
- `tests/test_project019_phase56.py` refers to `view_tabs` and `plot_container`
- `tests/test_figure_display_contract.py` refers to `fig._has_been_displayed`

These are not reliable descriptions of the current layout implementation.

### Historical docs
Closed historical project docs also still describe the old architecture. They are useful for refactor history, but not as the source of truth for current behavior.

### Compatibility wrappers that still exist
`FigureLayout` still provides temporary compatibility wrappers such as:

- `set_plot_widget(...)`
- `set_view_plot_widget(...)`
- `set_view_tabs(...)`
- `observe_tab_selection(...)`

These are shims onto the current persistent-page system. They are not proof that real tab hosting still exists.

---

## 15. Practical debugging checklist for layout bugs

Use this checklist before changing code.

### 1. Confirm the figure is actually displayed
If the figure has not been rendered in the notebook, no DOM geometry exists yet.

### 2. Confirm the target view is active and visible
The only page that should have meaningful geometry is the active one.

Check conceptually:

- active view id in `Figure`
- active page visibility in `FigureLayout`
- active `host_box.layout.display == "flex"`

### 3. Trace the height chain, not only one node
The current height chain is:

```text
view_stage
→ active host_box
→ PlotlyPane._wrap
→ PlotlyPane._host
→ Plotly DOM
```

A break at any step can produce under-fill or overflow.

### 4. Trace the width chain including clip ancestry
The plot width is affected by:

- outer row/column arrangement
- sidebar visibility
- full-width toggle
- clip ancestor width in the DOM
- Plotly DOM width clamp

### 5. Distinguish hidden-view zero size from broken active-view zero size
Inactive pages are `display:none`. That is expected.

### 6. Distinguish geometry failures from render failures
If ranges/traces are wrong, that is a different pipeline than outer sizing.

### 7. Remember wrapper padding and border
`PlotlyPane._wrap` adds visible chrome. The inner plot area is smaller than the outer widget box.

### 8. Check whether a geometry change had an explicit reflow request
The current design relies on `Figure` to request active-pane reflows after geometry changes.

---

## 16. Where to edit code depending on the problem

| Problem area | Primary file |
|---|---|
| widget tree structure, page hosts, sidebar layout, full-width mode | `src/gu_toolkit/figure_layout.py` |
| active-view switching, explicit reflow triggers, view runtime creation | `src/gu_toolkit/Figure.py` |
| per-view runtime state and remembered ranges | `src/gu_toolkit/figure_view.py` |
| view registry/selection policy | `src/gu_toolkit/figure_view_manager.py` |
| browser-side measurement and Plotly resize | `src/gu_toolkit/PlotlyPane.py` |
| per-view traces and rendering | `src/gu_toolkit/figure_plot.py` |
| parameter controls attached to sidebar | `src/gu_toolkit/figure_parameters.py` |
| slider modal CSS and hosted/global overlay behavior | `src/gu_toolkit/Slider.py` |
| info card/sidebar content that changes sidebar size | `src/gu_toolkit/figure_info.py` |
| legend sidebar rows and minor styling | `src/gu_toolkit/figure_legend.py` |

---

## 17. Bottom line

The current architecture is intentionally split:

- Python decides widget ownership and layout intent.
- The browser decides actual pixel geometry.
- `PlotlyResizeDriver` is the bridge that turns container size into Plotly size.

So when the plot under-fills, overflows, or fails to resize automatically, the right way to debug it is to trace **both**:

1. the Python widget/layout state and explicit reflow requests, and
2. the frontend measurement/resize path inside `PlotlyResizeDriver`.

That is the architecture this guide documents, and it is the architecture the logging project should instrument.
