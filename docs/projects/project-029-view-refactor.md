**`View` becomes the real public per-view object.**
`Figure` stays the coordinator.
`FigureLayout` becomes a pure layout engine, not a semi-coordinator.

That matches the TODOs, your feedback, and the code’s actual pain points.

There are four concrete issues worth fixing as part of the same pass:

* The current layout splits plot hosting between `plot_container` and `view_tabs`. That is the main brittleness source.
* View teardown is incomplete: layout-side view widget bookkeeping is not cleaned up when a view is removed.
* `Figure.snapshot()` / `codegen.py` currently confuse **active view defaults** with **main view defaults**, so round-tripping is wrong when the active view is not `"main"`.
* `with fig.views["id"]:` will need nested-context-safe figure context handling; the current `Figure.__enter__` / `__exit__` is not robust enough for that.

## The design I would lock in

### 1. Canonical public semantics

These become the official mental model:

* `fig.views["id"]` returns the public `View` object.
* `with fig.views["id"]:` temporarily activates that view **and** makes `fig` the current figure for module-level helpers.
* `fig.views.current` and `fig.views.current_id` are the canonical “current view” access points.
* `Figure.view("id")` goes away as the primary API. If compatibility matters, keep it as a one-line deprecated alias for one release only.
* `Figure.x_range` / `Figure.y_range` remain **current-view** shorthands.
* Constructor `x_range` / `y_range` should become `default_x_range` / `default_y_range` so they do not read like runtime setters.

I would keep `sampling_points` as-is. It already reads naturally and is not ambiguous in the same way as `x_range`.

---

## The layout invariants that should drive the refactor

These are the rules I would enforce in code comments and tests.

1. **Each view’s plot widget has one stable host for its whole lifetime.**
   No repeated reparenting between “single-view host” and “tab host”.

2. **There is one plot-area widget tree, not two competing trees.**
   The current `plot_container` vs `view_tabs` split is the main fragility.

3. **`FigureLayout` never stores render or reflow callbacks.**
   Layout owns widgets and geometry. `Figure` decides when to reflow or render.

4. **View activation is one-way data flow.**
   UI selector → `Figure.set_active_view()` → manager state → layout selection → reflow/render.

5. **Geometry changes always trigger an explicit reflow of the active view.**
   Do not rely only on passive observer behavior when the sidebar appears, disappears, or the layout changes.

6. **Main-view defaults and active-view state are different concepts.**
   Snapshot/codegen must use main-view defaults for reconstruction, not whichever view happens to be active.

---

## The layout approach I recommend

I would stop using `widgets.Tab` as the primary content host.

Keep the **concept** of tabs, but implement it as:

* a lightweight **view selector bar** at the top of the plot area,
* a **persistent page host** for each view underneath,
* only the active page visible,
* each page permanently owns exactly one `PlotlyPane.widget`.

That can still look like tabs to the user, but it avoids the worst part of `widgets.Tab`: content hosting and child rebuilding becoming entangled with selection state.

### Why this is better than the current layout

The current code does all of these at once:

* maintains `_tab_view_ids`,
* stores `_view_plot_widgets`,
* rebuilds tab children when the set changes,
* toggles between `plot_container` and `view_tabs`,
* stores per-view reflow callbacks,
* and also handles full-width changes.

That is too much state spread across too many moving pieces.

### Recommended internal shape for `FigureLayout`

Replace the current view-host logic with something like this internally:

* `_view_pages: dict[str, _ViewPage]`
* `_ordered_view_ids: tuple[str, ...]`
* `_active_view_id: str | None`
* `view_selector`
* `view_stage`

Where `_ViewPage` is a tiny internal record:

* `view_id`
* `title`
* `host_box`
* `widget`

No reflow callback. No render logic. Just layout state.

### Core layout methods

I would make `FigureLayout` expose only these view-specific operations:

* `ensure_view_page(view_id, title)`
* `attach_view_widget(view_id, widget)`
* `remove_view_page(view_id)`
* `set_view_order(view_ids)`
* `set_active_view(view_id)`
* `set_view_title(view_id, title)`
* `observe_view_selection(callback)`
* `observe_full_width_change(callback)`

And I would make `update_sidebar_visibility(...)` return whether the visible geometry changed, so `Figure` can explicitly reflow the active pane afterward.

### Height / sizing rule

The plot area should have **one source of truth** for height.

Right now that is `plot_container` with `height="60vh"`. In the new design, that fixed height should live on the persistent `view_stage` container. Each view page host and each `PlotlyPane.widget` should be `height="100%"`.

That way:

* the active view always has a real pixel height,
* hidden views do not control layout,
* PlotlyPane gets a stable outer contract.

---

## Public view object design

I would refactor `figure_view.py` so `View` is no longer just a passive dataclass. It should become a small public class.

### What `View` should own

This is the split you asked for:

* `id`
* `title`
* `x_label`
* `y_label`
* `default_x_range`
* `default_y_range`
* `viewport_x_range`
* `viewport_y_range`
* `is_active`
* `is_stale`
* `figure_widget`
* `pane`

That gives the view ownership of its widget runtime.

### What `View` should expose publicly

I would make these the main public properties/methods:

* `view.activate()`
* `with view: ...`
* `view.x_range`
* `view.y_range`
* `view.current_x_range`
* `view.current_y_range`
* `view.figure_widget`
* `view.pane`
* `view.plotly_layout`

I would name the layout property `plotly_layout`, not just `layout`, because `layout` is too ambiguous in this project.

### Important behavior details

* `view.x_range` and `view.y_range` should update both the stored defaults and the view’s own Plotly widget.
* `view.current_x_range` / `view.current_y_range` should read from the widget when possible and keep `viewport_*` in sync.
* `view.x_label` and `view.y_label` should finally be wired into the Plotly axis titles. Right now they are stored but effectively inert.
* `view.title` should update the selector label in `FigureLayout`.

### Context manager behavior

`with fig.views["zoom"]:` should:

1. remember the previous active view id,
2. enter the parent figure context,
3. activate the target view,
4. return the `View` object,
5. restore the previous active view on exit,
6. exit the parent figure context.

That means `View` needs a back-reference to its parent `Figure`.

Because of that, I would make `Figure.__enter__` / `__exit__` nesting-safe by adding a `_context_depth` counter.

Without that, nested `with fig:` / `with fig.views["id"]:` will close the print-capture area too early.

---

## What stays in `Figure`

`Figure` should continue to own:

* view activation coordination,
* render orchestration,
* relayout handling,
* stale-view policy,
* current-figure stack behavior,
* sidebar visibility synchronization,
* manager wiring.

### Remove these from `Figure`

* `_ViewBackend`
* `_view_backends`
* `_current_view()`

Once `View` is the real public object, `_current_view()` becomes redundant. I would standardize on `self.views.current`.

### Keep these as convenience delegates

* `Figure.figure_widget`
* `Figure.pane`
* `Figure.x_range`
* `Figure.y_range`
* `Figure.current_x_range`
* `Figure.current_y_range`

But all of them should delegate to `self.views.current`.

For compatibility, I would probably keep:

* `figure_widget_for(view_id)`
* `pane_for(view_id)`

as thin advanced delegates to `fig.views[view_id].figure_widget` and `.pane`.

---

## Figure activation / switching pipeline

This is the order I would use inside `Figure.set_active_view()`.

1. Read and store the outgoing view’s live viewport from its widget.
2. Ask `ViewManager` to switch the active id.
3. Tell `FigureLayout` to select the new active view.
4. Tell `InfoPanelManager` and `LegendPanelManager` about the new active view.
5. Apply the incoming view’s stored viewport (or defaults) to its widget.
6. Explicitly reflow the incoming view’s pane.
7. Render active-view plots.
8. Clear stale state on the new active view if needed.
9. Recompute sidebar visibility and reflow again if the visible sidebar geometry changed.

That order is more robust than the current “render first, then sync layout” shape.

---

## Relayout / debouncing design

I agree with the TODO direction here: use a **single figure-level relayout debouncer**.

### Why a single debouncer is better now

Pros:

* simpler lifecycle,
* no per-view debouncer cleanup,
* matches the fact that only one view is interactively visible at a time,
* clearer ownership: relayout policy belongs to `Figure`.

Cons:

* a relayout event can still fire after a view switch.

That is easy to handle. Store the latest pending `view_id` and verify on dispatch:

* if the pending view is still the active view, render relayout,
* if it still exists but is inactive, mark it stale,
* if it no longer exists, drop the event.

So I would replace per-view `relayout_debouncer` with:

* `Figure._relayout_debouncer`
* `Figure._queue_relayout(view_id, *args)`
* `Figure._dispatch_relayout()`

Each view widget’s `layout.on_change(...)` callback just queues a relayout tagged with its `view_id`.

---

## Constructor and routing plan

I would make the constructor explicit but routed.

### Recommended constructor

```python
Figure(
    *,
    title: str = "",
    sampling_points: int = 500,
    default_x_range: RangeLike = (-4, 4),
    default_y_range: RangeLike = (-3, 3),
    x_label: str = "",
    y_label: str = "",
    show: bool = False,
    **compat_kwargs,
)
```

### Compatibility behavior

Accept these old names temporarily:

* `x_range` → `default_x_range`
* `y_range` → `default_y_range`
* `display` → `show`

I would remove or finish deprecating:

* `debug`
* `default_view_id`
* `plotly_legend_mode`
* `active_view_id` property

### Why this matches your routing preference

It keeps the student-facing API light, but it still makes the routing explicit:

* figure-level: `title`, `show`, `sampling_points`
* main-view seeded values: `default_x_range`, `default_y_range`, `x_label`, `y_label`

That is much clearer than overloading constructor `x_range` to mean something different from runtime `fig.x_range`.

---

## Snapshot and code generation fixes

This part needs attention because the current behavior is semantically wrong in multi-view cases.

### Current bug

`Figure.snapshot()` currently stores top-level `x_range` / `y_range` from the **active view**, while `codegen.py` uses those values to reconstruct the initial main view.

So if the active view is not `"main"`, the generated code reconstructs the wrong defaults for the main view.

### Fix plan

Use the `"main"` view as the source of constructor defaults in code generation.

Specifically:

* snapshot should either:

  * make top-level `x_range` / `y_range` mean **main-view defaults**, or
  * keep them as compatibility fields but stop codegen from trusting them.
* codegen should read the main view entry from `snapshot.views`.

### Also fix main-view metadata loss

Right now codegen skips the main view entirely when adding views later, so the main view’s:

* title,
* `x_label`,
* `y_label`

are not reliably reconstructed.

With the new design, codegen should do this:

* build `Figure(...)` with main-view defaults and axis labels,
* then, if needed, set `fig.views["main"].title = ...`,
* then add non-main views,
* then restore active view via `fig.views.current_id = ...` or `fig.views["id"].activate()`.

---

## File-by-file refactor plan

### `figure_view.py`

Refactor into the main public view API module.

Do this:

* move `FigureViews` here from `Figure.py`,
* convert `View` from passive dataclass to public class,
* add runtime-owned widget fields,
* add activation and context-manager behavior,
* add `plotly_layout`,
* make `title`, `x_label`, `y_label`, `x_range`, `y_range` real properties with side effects.

### `figure_view_manager.py`

Keep it focused on:

* registry ownership,
* active id bookkeeping,
* stale marking,
* validation.

I would stop having it manufacture views from raw constructor parameters. Let `Figure` create the `View` and register it.

That matches the new ownership model better.

### `Figure.py`

This is the main cleanup target.

Do this:

* rewrite module docstring with glossary and navigation map,
* remove `_ViewBackend`,
* remove `_view_backends`,
* remove `_current_view`,
* add `_context_depth`,
* add `_relayout_debouncer`,
* add `_pending_relayout_view_id`,
* add small helpers:

  * `_create_view(...)`
  * `_attach_view_callbacks(view)`
  * `_request_active_view_reflow(reason)`
  * `_sync_sidebar_visibility()` returning whether geometry changed
* remove `view()`,
* add `info_manager`,
* make current-view convenience properties delegate to `self.views.current`.

### `figure_layout.py`

This is the most important structural change.

Do this:

* replace dual hosting (`plot_container` + `view_tabs`) with one persistent page system,
* remove reflow callback registries,
* add explicit page add/remove/select methods,
* add an observer for selector changes,
* add an observer for full-width changes,
* make sidebar visibility updates geometry-aware,
* keep the sidebar/title/output areas largely unchanged.

### `figure_plot.py`

Mostly keep rendering logic intact.

Change only the view access layer:

* `fig.figure_widget_for(view_id)` → `fig.views[view_id].figure_widget`
* `fig.pane_for(view_id)` → `fig.views[view_id].pane`
* use `fig.views.current` / `current_id` consistently

Do not rewrite the math/render core in the same pass.

### `figure_plot_style.py`

Second-tier cleanup after the view/layout refactor.

Change `PLOT_STYLE_OPTIONS` from `dict[str, str]` into structured metadata, for example:

```python
@dataclass(frozen=True)
class PlotStyleSpec:
    name: str
    aliases: tuple[str, ...]
    type_doc: str
    default_doc: str
    description: str
```

Then keep explicit kwargs in `Figure.plot(...)`, but derive:

* discoverability text,
* alias resolution,
* validation docs,

from the metadata.

### `figure_info.py`

Add or improve:

* public docs for “info card”, “Info section”, and view-scoped cards,
* `Figure.info_manager` as the primary advanced access point.

Keep `info_output` as a compatibility alias if needed.

### `figure_api.py`

Update examples and docs to favor:

```python
with fig.views["detail"]:
    plot(...)
```

Also explain that module-level helpers target the current figure, and that view contexts temporarily set both the figure and the active view.

### `codegen.py` and `FigureSnapshot.py`

Fix main-view reconstruction and naming.

### `develop_guide.md`

Update the architecture map so it reflects the split modules and the new view ownership model.

Also add a short “layout invariants” section so future contributors do not reintroduce the brittle structure.

---

## Documentation changes that should happen with the refactor

`Figure.py` should become the documentation hub.

Its module docstring should include:

* what a figure is,
* what a view is,
* what the sidebar is,
* what an info card is,
* what “current figure” means,
* how module-level helpers work,
* where to find deeper docs.

`View` docs should explain:

* that it owns one plotting workspace,
* that it owns its widget runtime,
* that it can be used as a context manager,
* that it does not own plots or parameters.

`FigureLayout` docs should explicitly say:

* it owns widget composition only,
* it does not decide rendering,
* it does not own plot data,
* it should not store reflow callbacks.

Logging docs should include one concrete snippet, for example enabling `gu_toolkit.Figure` or the package logger through Python’s standard `logging` module.

---

## Recommended implementation order

I would not do this as one giant edit.

### Phase 1

Make figure/view contexts nesting-safe and introduce rich `View` objects, while keeping old delegates working.

### Phase 2

Refactor layout hosting to stable view pages and remove reflow callback storage from `FigureLayout`.

### Phase 3

Delete `_ViewBackend`, remove `Figure.view()`, and switch internal code to `self.views.current`.

### Phase 4

Fix snapshot/codegen semantics for main-view reconstruction.

### Phase 5

Finish docs, `info_manager`, and plot-style metadata cleanup.

That order keeps the risky layout work isolated and testable.

---

## Test plan

There is no `tests/` directory in the provided archive, so I would add one now.

### Unit tests

At minimum:

* `with fig.views["id"]:` activates the view and restores the previous one.
* `with fig.views["id"]:` makes module-level helpers target the right figure.
* nested `with fig:` and `with fig.views["id"]:` does not break print capture.
* `view.x_range` / `view.y_range` updates widget state.
* `view.x_label` / `view.y_label` updates axis titles.
* removing a view cleans layout-side page registries.
* switching views preserves per-view viewport memory.
* constructor alias routing works.
* codegen round-trip is correct when active view is not main.

### Notebook/manual regression tests

Because layout is the brittle part, add at least one notebook test focused on:

* adding a second view,
* switching views after zooming both,
* toggling full-width mode,
* adding/removing parameters so the sidebar appears/disappears,
* removing a non-active view,
* switching back to a stale view and confirming redraw,
* using `with fig.views["id"]:` with module-level `plot()` / `info()`.

That notebook should explicitly say what visual failures to watch for: clipped plot, wrong active page, stale width, missing reflow, lost zoom memory, wrong sidebar visibility.

---

## The end-state API I would aim for

```python
fig = Figure(
    title="Interactive demo",
    default_x_range=(-4, 4),
    default_y_range=(-3, 3),
    x_label="x",
    y_label="y",
    show=True,
)

fig.views.add("zoom", title="Zoom", x_range=(-1, 1), y_range=(-1, 1))

with fig.views["zoom"] as view:
    plot(...)
    info("Local behavior")
    view.x_range = (-2, 2)

fig.views["zoom"].activate()
fig.views["zoom"].figure_widget
fig.views["zoom"].pane
fig.views.current_id = "main"
```

That is the simplest version of the API that matches the TODOs, your preferences, and the actual structure of the code.

The most important implementation choice in all of this is the layout one: **stable host per view, no dual plot host, and no reflow callback storage inside `FigureLayout`**. Everything else gets cleaner once that is true.
