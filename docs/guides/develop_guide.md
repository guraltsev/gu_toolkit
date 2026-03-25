# gu_toolkit development guide

This guide reflects the refactored architecture where:

- `Figure` is the coordinator and public entry point.
- `View` is the real public per-view object.
- `FigureLayout` is a pure layout engine that owns widget composition only.

The package is organized around *ownership by concern*. When changing behavior,
start by finding which module owns the state and lifecycle for that concern.

---

## 1. High-level mental model

```text
Figure (coordinator / entry point)
├── FigureLayout          # widget tree, view selector, stage, sidebars, output area
├── ViewManager           # registry, active view id, stale-state policy
├── FigureViews           # user-facing mapping facade over ViewManager
├── View                  # public per-view object + widget runtime + ranges/labels
├── ParameterManager      # parameters, ParamRef registry, hooks
├── InfoPanelManager      # Info section, info cards, raw outputs
├── LegendPanelManager    # toolkit-owned legend sidebar
├── Plot registry         # plot_id -> Plot
└── Snapshot / codegen    # FigureSnapshot + figure_to_code()
```

A good rule for maintenance is: **if a feature has its own state and its own
lifecycle, it should usually live in its own module rather than adding more
fields and branches to `Figure`.**

---

## 2. Ownership map

| Concern | Owner | Notes |
|---|---|---|
| Current-figure context stack | `figure_context.py` | Thread-local stack used by module-level helpers and `with fig:` |
| Widget tree and layout | `FigureLayout` | Title bar, selector bar, persistent view hosts, sidebar, output area |
| Public view state + runtime | `View` | Axis labels, default ranges, remembered viewport, `FigureWidget`, `PlotlyPane` |
| View registry and selection policy | `ViewManager` | Registration, active id, stale flags, removal rules |
| Parameters and hooks | `ParameterManager` | Parameter-name -> `ParamRef`, symbol aliases via `symbol.name`, control reuse, hooks, snapshots |
| One plotted curve | `Plot` | Numeric compilation, sampling, trace updates, styling |
| Info section | `InfoPanelManager` | Raw outputs, simple cards, view scoping |
| Legend sidebar | `LegendPanelManager` | Rows filtered by active view |
| Serializable state | `FigureSnapshot`, `PlotSnapshot`, `ParameterSnapshot` | Immutable snapshots |
| Recreated source code | `codegen.py` | Converts snapshots into Python |

---

### Parameter identity rule

Parameter-facing APIs are **name-authoritative**. The canonical identity of a
parameter is its string name (`symbol.name`), not the exact `Symbol` object
instance.

That means:

- mapping-like parameter registries iterate names,
- symbol inputs are normalized to their `.name` before lookup, and
- same-name symbols share one logical parameter/control entry.

Representative `Symbol` objects are still retained where needed for expression
round-tripping and code generation, but they are not the primary lookup key.

---

## 3. View system

### Public API

The public mental model is:

- `fig.views["id"]` returns the public `View` object.
- `fig.views.current` and `fig.views.current_id` are the canonical active-view accessors.
- `with fig.views["id"]:` temporarily makes both the figure *current* and that view *active*.
- `Figure.x_range` / `Figure.y_range` are convenience shorthands for the current view.

### What `View` owns

A `View` owns one plotting workspace and one stable widget runtime for its whole lifetime:

- `id`
- `title`
- `x_label`, `y_label`
- `default_x_range`, `default_y_range`
- `viewport_x_range`, `viewport_y_range`
- `is_active`, `is_stale`
- `figure_widget`
- `pane`

A `View` does **not** own plots, parameters, or layout policy.

### What `ViewManager` owns

`ViewManager` remains the registry/policy layer:

- registration
- active view id bookkeeping
- stale-state tracking
- removal validation

It should stay free of widget ownership.

---

## 4. Layout invariants

These invariants are the core of the current layout design and should be kept
intact in future changes.

1. **Each view’s plot widget has one stable host for its whole lifetime.**
2. **There is one plot-area widget tree, not two competing hosts.**
3. **`FigureLayout` owns widgets and geometry only. It does not own render callbacks.**
4. **View activation flows one way:** UI selector -> `Figure.set_active_view()` -> manager state -> layout selection -> reflow/render.
5. **Geometry changes trigger explicit reflow from `Figure`.**
6. **Main-view defaults and active-view state are different concepts.**

### Practical shape of `FigureLayout`

`FigureLayout` now uses:

- a lightweight selector bar (`view_selector`)
- a persistent stage (`view_stage`)
- one persistent page host per view
- only the active page visible at a time

It no longer stores render or reflow callback registries.

---

## 5. FigureLayout responsibilities

`FigureLayout` owns:

- title bar
- full-width toggle
- view selector
- persistent view pages
- sidebar section widgets
- output area below the figure

It exposes layout operations such as:

- `ensure_view_page(view_id, title)`
- `attach_view_widget(view_id, widget)`
- `remove_view_page(view_id)`
- `set_view_order(view_ids)`
- `set_active_view(view_id)`
- `set_view_title(view_id, title)`
- `observe_view_selection(callback)`
- `observe_full_width_change(callback)`
- `update_sidebar_visibility(...) -> bool`

That final method returning `bool` is important: `Figure` uses the return value
to decide when geometry changed and an explicit active-view reflow is needed.

---

## 6. `Figure` responsibilities

`Figure` still owns orchestration:

- create managers and layout
- create/register views
- coordinate active-view switching
- attach relayout callbacks
- trigger pane reflows
- render plots
- mark inactive views stale on parameter changes
- route module-level helper context
- snapshot and code generation entry points

### Important coordinator policies

- `Figure.__enter__` / `__exit__` are nesting-safe through `_context_depth`.
- relayout handling is figure-level (`_relayout_debouncer`) rather than per-view.
- `fig.info_manager` is the advanced access point for the Info section.
- `figure_widget`, `pane`, `x_range`, `y_range`, `current_x_range`, and `current_y_range` are current-view delegates.

---

## 7. Snapshot and code generation semantics

This is a subtle but important invariant.

### Main-view defaults vs active view

`Figure.snapshot()` stores top-level `x_range` / `y_range` as **main-view defaults**,
not the defaults of whichever view is currently active.

`codegen.figure_to_code()` reconstructs the initial figure constructor from the
serialized `main` view entry when available.

That means round-tripping remains correct even when the active view is not
`"main"` at snapshot time.

### Reconstruction rules

Code generation should:

1. build `Figure(...)` from main-view defaults and axis labels,
2. restore the main view title if needed,
3. add non-main views,
4. restore remembered per-view viewport ranges,
5. restore the active view.

---

## 8. Plot system and style metadata

`figure_plot.py` owns the cartesian per-curve render model.

`figure_parametric_plot.py` owns parametric `(x(t), y(t))` curve rendering and
the helper used by `Figure.parametric_plot(...)`.

The public style contract is centralized in `figure_plot_style.py` through
structured `PlotStyleSpec` metadata. That metadata now drives:

- discoverability text (`plot_style_options()`),
- alias resolution (for example `width -> thickness`, `alpha -> opacity`),
- lightweight validation for fixed-choice options such as `dash`.

When adding a new public style keyword, update:

1. `figure_plot_style.py`
2. `Figure.plot(...)`
3. `figure_api.plot(...)`
4. `Plot.update(...)` / `Plot.snapshot()` if needed
5. code generation if it must round-trip

When adding parametric-curve behavior, update the corresponding pieces in:

1. `figure_parametric_plot.py`
2. `Figure.parametric_plot(...)`
3. `figure_api.parametric_plot(...)`
4. `PlotSnapshot` / `codegen.py` if it must round-trip

---

## 9. Info section

The Info section has two supported lanes:

1. **Raw outputs** via `InfoPanelManager.get_output(...)`
2. **Simple info cards** via `Figure.info(...)` / `InfoPanelManager.set_simple_card(...)`

A simple info card may contain:

- static string segments,
- dynamic callable segments, or
- a mixed sequence of both.

Dynamic callables receive:

- the owning `Figure`
- an `InfoChangeContext` containing `reason`, `trigger`, `t`, and `seq`

Cards can also be scoped to a specific view. Scoped cards are hidden when that
view is inactive.

Only simple cards participate in snapshot/code generation, and dynamic callable
segments are serialized as `"<dynamic>"` placeholders.

---

## 10. Module-level helpers and current-figure routing

`figure_api.py` provides notebook-friendly free functions such as:

- `plot(...)`
- `parameter(...)`
- `info(...)`
- `render(...)`
- `set_x_range(...)`, `set_y_range(...)`, `set_title(...)`

These route through the thread-local current-figure stack in `figure_context.py`.

Key behaviors:

- `with fig:` makes `fig` current.
- `with fig.views["detail"]:` makes `fig` current and activates `detail`.
- `plot(...)` auto-creates a figure when none exists.
- most other helpers require an active figure.

---

## 11. Contributor checklist

When changing behavior, prefer subsystem-local changes over coordinator growth.

### Adding a new per-view property

Update at least:

1. `View`
2. `ViewManager` if selection/removal policy changes
3. `Figure` coordination logic
4. `ViewSnapshot`
5. `Figure.snapshot()`
6. `codegen.figure_to_code()`

### Adding a new style option

Update at least:

1. `figure_plot_style.py`
2. `Figure.plot(...)`
3. `figure_api.plot(...)`
4. `Plot.update(...)`
5. snapshots/codegen if it must round-trip

### Adding a new layout mode

Respect the layout invariants:

- keep one stable host per view
- keep render policy out of `FigureLayout`
- ensure `Figure` can request an explicit reflow when geometry changes

---

## 12. Bottom line

The package is healthiest when these boundaries stay clear:

- `Figure` coordinates.
- `View` is the real public per-view object.
- `FigureLayout` owns widget composition only.
- `ViewManager` owns registry/selection policy.
- `Plot` owns curve-level sampling/rendering.
- `InfoPanelManager` owns the Info section.
- snapshots/codegen own reproducibility.

When in doubt, follow the ownership map first and only touch `Figure` when the
change truly spans multiple subsystems.
