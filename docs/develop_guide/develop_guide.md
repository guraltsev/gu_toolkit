# 1. Mental model of the package

At a high level, this package is a Jupyter-first interactive math toolkit built around a single coordinator object, `Figure`, that glues together several specialized managers.

```text
Figure (coordinator / entry point)
├── FigureLayout            # widget tree, sidebars, tabs, output area
├── ViewManager             # pure model of views and active view selection
├── FigureViews             # user-facing facade over ViewManager
├── _ViewBackend[view_id]   # FigureWidget + PlotlyPane + relayout debouncer
├── ParameterManager        # parameters, ParamRef registry, hooks
├── InfoPanelManager        # info cards and raw output widgets
├── LegendPanelManager      # toolkit-owned legend sidebar
├── Plot registry           # plot_id -> Plot
└── Snapshot / codegen      # FigureSnapshot + figure_to_code()
```

The key design choice is that **state ownership is split by concern** rather than collapsed into `Figure`.

## State ownership matrix

| Concern | Owner | Notes |
|---|---|---|
| Current-figure context stack | `figure_context.py` | Thread-local stack used by module-level helpers and `with fig:` |
| Widget tree and layout | `FigureLayout` | Title bar, plot host, tabs, sidebar, output panel |
| View models | `ViewManager` plus `View` | Pure state: ranges, labels, stale flags, active selection |
| Per-view Plotly widgets | `Figure` via `_view_backends` | Runtime UI bundle, not in `ViewManager` |
| Parameter refs and hooks | `ParameterManager` | Symbol to `ParamRef`, control registry, hook registry |
| One plotted curve | `Plot` | Numeric compilation, sampling, trace updates, styling |
| Info sidebar content | `InfoPanelManager` | Raw outputs and simple cards |
| Legend sidebar content | `LegendPanelManager` | Rows filtered by active view |
| Serializable state | `FigureSnapshot`, `PlotSnapshot`, `ParameterSnapshot` | Immutable snapshots |
| Recreated source code | `codegen.py` | Converts snapshots into Python |

A good maintenance rule is: **if a new feature has its own state and its own lifecycle, it probably deserves its own module rather than more `Figure` methods and fields.**

---

# 2. `Figure.py`: the entry point and composition root

`Figure.py` is the right place to start because it shows the package's real public face.

## What `Figure.py` contains today

`Figure.py` currently does four things.

### 2.1 It defines the notebook-facing `Figure` class

`Figure` is still the main object users interact with. It owns:

- the plot registry (`fig.plots`),
- the layout manager,
- the parameter manager,
- the info panel manager,
- the legend panel manager,
- the view manager,
- the per-view widget backends,
- active-view convenience properties such as `figure_widget`, `pane`, `x_range`, `y_range`.

### 2.2 It defines `FigureViews`

`FigureViews` is a small mapping-like facade over `ViewManager`. It exists because `ViewManager` is intentionally a pure model, while view switching has UI side effects that only `Figure` can perform.

Use `fig.views.current_id`, `fig.views.current`, `fig.views.add(...)`, and `fig.views.select(...)` instead of the deprecated `fig.active_view_id` property.

### 2.3 It defines `_ViewBackend`

`_ViewBackend` is an internal runtime bundle for one view:

- `FigureWidget`
- `PlotlyPane`
- relayout `QueuedDebouncer`

This separation is important: `View` is the **model**, `_ViewBackend` is the **runtime widget bundle**.

### 2.4 It re-exports module-level helper functions

At the bottom of `Figure.py`, the file imports `figure_api` and re-exports helpers such as `plot`, `parameter`, `parameters`, `render`, `info`, `set_title`, `set_x_range`, `set_y_range`, and `plot_style_options`.

That means `Figure.py` is not just a class definition file; it is part of the public package routing layer.

## What `Figure.py` does not do 

It does not contain the main implementation of layout construction, view model lifecycle, parameter model logic, info sidebar logic, legend logic, or per-curve render internals. Those live in dedicated modules.

## Why `Figure.py` still matters

Even though the code is split, `Figure.py` still documents the runtime orchestration order:

1. create layout,
2. create managers,
3. create per-view backends,
4. create the initial view,
5. wire widget events,
6. expose active-view convenience properties,
7. render, snapshot, and codegen.

For architecture work, `Figure.py` is the package's composition diagram in executable form.

---

# 3. Public surface layering

The public surface is now layered. Understanding that layering makes the package much easier to extend safely.

## 3.1 Package-level surface: `__init__.py`

`__init__.py` re-exports the notebook-facing API so users can import from `gu_toolkit` directly.

It also contains an important compatibility fix: because `Notebook.py` wildcard-imports SymPy conveniences, package-level `plot` is explicitly rebound to the toolkit's own plotting helper afterward so `gu_toolkit.plot` does not accidentally resolve to SymPy's plotting helper.

## 3.2 Object-oriented surface: `Figure.py`

This is the main surface for explicit, maintainable code:

- `Figure`
- `FigureViews`
- `Plot`
- `FigureLayout`
- snapshot types

## 3.3 Module-level convenience surface: `figure_api.py`

`figure_api.py` implements the free-function helpers used in notebook workflows.

Important behavior difference:

- `plot(...)` will **auto-create and display** a new `Figure` if no current figure exists.
- `parameter(...)`, `info(...)`, `render(...)`, and the range and title setters require an active figure and raise if none exists.

This is intentional. Plotting has an obvious default side effect; parameter registration and layout mutation do not.

## 3.4 Current-figure routing: `figure_context.py`

This module owns the thread-local current-figure stack.

Key points:

- `with fig:` pushes the figure onto the stack,
- module-level helpers resolve through that stack,
- nested usage is supported by stack semantics,
- `current_figure(required=False)` gives a nullable lookup for advanced code.

## 3.5 Notebook convenience namespace: `Notebook.py`

`Notebook.py` is a batteries-included namespace for interactive sessions. It exports:

- `sympy as sp`
- `numpy as np`
- optional `pandas as pd`
- `SymbolFamily` and `FunctionFamily`
- predefined symbolic families for common letters and Greek names
- `NIntegrate`, `NReal_Fourier_Series`, `play`
- display helpers like `display`, `HTML`, `Latex`, `pprint`

This is useful for notebook ergonomics, but it is not the main runtime architecture layer.

---

# 4. Layout and display architecture

## 4.1 `FigureLayout` owns the widget tree

`figure_layout.py` builds the notebook widget hierarchy.

### Main layout regions

- title bar (`title_html` plus `full_width_checkbox`)
- plot area (`plot_container`)
- optional tab selector (`view_tabs`)
- sidebar sections:
  - legend
  - parameters
  - info
- print and output area below the main figure content

### Important layout facts

- the plot container is given a real height (`60vh`) and min sizes; this is essential for Plotly sizing,
- the sidebar is hidden until at least one of legend, parameters, or info is present,
- the layout is responsive via flex wrapping, so the sidebar can drop below the plot on narrow widths,
- the full-width checkbox changes flex flow between side-by-side and stacked layouts.

## 4.2 `PlotlyPane` solves Plotly sizing problems

`PlotlyPane.py` is the toolkit's answer to unreliable Plotly resizing in notebook layouts.

### What it adds

- an `anywidget` frontend driver (`PlotlyResizeDriver`),
- `ResizeObserver` and `MutationObserver` based resize detection,
- explicit width and height application to Plotly DOM nodes,
- optional autorange-on-resize modes,
- deferred reveal to avoid wrong-size flash during layout transitions.

### Practical maintainer takeaway

Any feature that changes layout geometry should respect the pane and reflow contract instead of trying to manipulate Plotly DOM sizing directly from Python.

If you add new layout modes, make sure they eventually call the pane's `reflow()` path.

## 4.3 Display lifecycle and `OneShotOutput`

`FigureLayout.output_widget` returns a fresh `OneShotOutput` wrapper around the root widget.

`OneShotOutput` exists to protect against accidental repeated display of the same wrapper instance. It is not the main architecture feature, but it is part of the display lifecycle contract.

## 4.4 Output capture in `with fig:` blocks

A subtle but important behavior lives in `Figure.__enter__()`:

- entering `with fig:` not only pushes the current figure,
- it also enters the `FigureLayout.print_output` context.

That means `print(...)` and display output produced inside `with fig:` are captured into the figure's output panel rather than going to the surrounding notebook cell output.

This behavior is important for notebook UX and should be preserved unless the package intentionally redesigns its output model.

---

# 5. View system

Multi-view support is one of the biggest real architecture upgrades in the current code.

## 5.1 The split between `View` and `_ViewBackend`

This split is essential.

### `View` (`figure_view.py`)

`View` is a pure dataclass model. It stores:

- `id`
- `title`
- `x_label`
- `y_label`
- `default_x_range`
- `default_y_range`
- `viewport_x_range`
- `viewport_y_range`
- `is_active`
- `is_stale`

### `_ViewBackend` (`Figure.py`)

`_ViewBackend` stores runtime UI resources for a view:

- `FigureWidget`
- `PlotlyPane`
- relayout debouncer

Do not merge these concepts mentally. `ViewManager` should remain free of widget dependencies.

## 5.2 `ViewManager` policy

`ViewManager` owns:

- view registration,
- active-view identity,
- stale-state tracking,
- preservation of previous viewports when switching views.

### Important behavior

- the first view added becomes active automatically,
- the default view id is `main`,
- the active or default view cannot be removed,
- switching views persists the previous view's current viewport back into the model,
- inactive views can be marked stale and lazily rerendered later.

## 5.3 `FigureViews` is the public facade

`FigureViews` gives the user-facing API:

- `fig.views[id]`
- `fig.views.current_id`
- `fig.views.current`
- `fig.views.add(...)`
- `fig.views.remove(...)`
- `fig.views.select(...)`

This is preferable to reaching into `_view_manager` directly.

## 5.4 Each view has its own Plotly widget

This is a critical current implementation detail.

A view switch is **not** just a change of axis ranges on one global widget. Each view has its own:

- Plotly figure widget,
- pane wrapper,
- relayout debouncer,
- per-plot trace handles.

One `Plot` can therefore own multiple trace handles, one per view membership.

## 5.5 Active-view convenience properties are just shorthands

Several `Figure` properties are easy to misread as figure-global, but they are actually active-view shorthands:

- `figure_widget`
- `pane`
- `x_range`
- `y_range`
- `current_x_range`
- `current_y_range`

If you need a specific view's widget or pane, use `figure_widget_for(view_id)` and `pane_for(view_id)`.

> Important: `Figure.x_range` and `Figure.y_range` are convenience accessors for the **current view's default ranges**, not truly figure-global ranges.

## 5.6 Current metadata gaps

The current code stores richer view metadata than it renders.

### Stored and serialized

- `View.title`
- `View.x_label`
- `View.y_label`

### Currently rendered

- tab labels use the **view id**, not `View.title`,
- Plotly axis titles are not set from `x_label` and `y_label`.

Treat those fields as real model and serialization state, but not yet full UI state.

---

# 6. Plot system

`figure_plot.py` contains the curve-level render model.

## 6.1 What one `Plot` owns

A `Plot` is one conceptual plotted curve. It owns:

- the independent variable,
- the symbolic expression or symbolic placeholder,
- the compiled numeric backend,
- the parameter ordering implied by that backend,
- style state,
- visibility state,
- optional x-domain override,
- optional sampling override,
- view memberships,
- one `PlotHandle` per view.

## 6.2 `PlotHandle` is a per-view runtime binding

A `PlotHandle` binds a plot id to a specific view id and specific Plotly trace handle.

Current fields:

- `plot_id`
- `view_id`
- `trace_handle`
- `cached_x`
- `cached_y`

Only `trace_handle` is actively used in the current render path; the cached arrays appear to be reserved for future or unfinished optimization work.

## 6.3 Plot creation flow

When `Figure.plot(...)` is called, the coordinator does the following:

1. choose or validate the plot id,
2. normalize inputs using `normalize_plot_inputs(...)`,
3. resolve style aliases (`width` to `thickness`, `alpha` to `opacity`),
4. infer or honor parameter symbols,
5. ensure parameter controls exist,
6. create a new `Plot` or update an existing one in place,
7. notify the legend manager.

## 6.4 `normalize_plot_inputs(...)` is the input grammar boundary

This helper is important because it keeps `Figure.plot(...)` from becoming a giant branching parser.

Supported first argument kinds:

- SymPy expression,
- `NumericFunction`,
- plain callable.

Supported variable declarations include:

- a symbol,
- a range tuple `(x, min, max)`,
- callable variable specs through `vars=` using the same grammar as `numpify`.

## 6.5 Rendering model

`Plot.render(view_id=None)` does the following for the target view:

1. resolve target view,
2. skip if hidden or suspended,
3. if target view is inactive, mark it stale and stop,
4. determine x range from current viewport or default view range,
5. widen range to include explicit `x_domain` if present,
6. determine sample count from plot override, figure default, or `500`,
7. generate `x_values` with `numpy.linspace`,
8. evaluate `y_values` through the live numeric expression,
9. push arrays into the target trace in a Plotly `batch_update()` block.

## 6.6 One plot, many views

A plot can belong to multiple views. The model-level membership lives in `Plot._view_ids`, and `add_to_view(...)` creates a new trace handle in the target view's widget.

This is one of the most important differences from earlier one-widget mental models.

## 6.7 Styling

Style state is split between:

- line style: `color`, `thickness`, `dash`, `line`
- trace style: `opacity`, `trace`

Public discoverability for supported shorthands is centralized in `figure_plot_style.PLOT_STYLE_OPTIONS` and surfaced through `Figure.plot_style_options()`.

If you add a new public style keyword, update the centralized style contract instead of documenting it ad hoc in one method.

## 6.8 Visibility semantics

Visibility is intentionally strict in the current code: `VisibleSpec` is just `bool`.

This means the toolkit-side legend and render logic assumes `True` or `False`, not richer Plotly states such as `legendonly`.

## 6.9 Limitations of the current render model

The current plot render path is intentionally simple and fast, but it has some real limits:

- it assumes direct vectorized evaluation to one y-array,
- it does not split discontinuities into segments,
- it does not do NaN or singularity sanitization in the main plotting path,
- it does not keep inactive views eagerly synchronized; they are marked stale and rerendered on activation.

That simplicity is a feature for maintainability, but developers extending the plotting model should understand the tradeoff.

## 6.10 No public plot removal API yet

`Figure.plots` is a public dictionary-like registry, but the package does not currently expose a dedicated `Figure.remove_plot(...)` method.

Today, the supported plot lifecycle is essentially:

- create,
- update in place by id,
- hide by setting `visible=False`.

If proper plot deletion is added later, it must remove traces from all views and keep legend state in sync.

---

# 7. Parameter system

The parameter layer is one of the cleanest parts of the current design.

## 7.1 `ParameterManager` owns parameter state, not `Figure`

`figure_parameters.py` stores the parameter registry and hook machinery.

Core responsibilities:

- symbol to `ParamRef` mapping,
- control creation and reuse,
- control-to-ref handshake,
- render callback dispatch on change,
- hook registration,
- immutable snapshot creation,
- live parameter context view for numeric evaluation.

## 7.2 Ref-first API

The modern API is ref-first.

- `fig.parameter(a)` returns a `ParamRef`, not a widget.
- `fig.parameters[a]` returns a `ParamRef`.
- for multiple symbols, `fig.parameter([a, b])` returns a mapping from symbol to ref.

The widget is still available through `ref.widget`, but the main public contract is now the reference object.

## 7.3 `ParamRef` and `ProxyParamRef`

`ParamRef.py` defines the protocol that parameter references must satisfy.

A param ref exposes:

- `parameter`
- `widget`
- `value`
- `observe(...)`
- `reset()`
- optional metadata capability access (`default_value`, `min`, `max`, `step`)
- `capabilities`

`ProxyParamRef` is the default implementation that wraps a widget or control with a `value` trait.

## 7.4 `ParamEvent` normalizes observation

Regardless of what the underlying widget emits, observers are normalized into an immutable `ParamEvent` with:

- `parameter`
- `old`
- `new`
- `ref`
- `raw`

That means hooks and downstream logic can depend on one event shape instead of traitlets-specific dictionaries.

## 7.5 Default control: `FloatSlider`

The default parameter control lives in `Slider.py`.

### What it includes

- a numeric slider,
- one editable numeric text field for the current value,
- inline min and max text controls,
- a reset button,
- a settings button,
- a settings modal containing at least step size and live-update controls,
- optional modal hosting so the settings overlay can be attached to a figure-level host.

### Important contract detail

`FloatSlider.make_refs([symbol])` returns a `{symbol: ProxyParamRef(...)}` mapping. That is the handshake used by `ParameterManager`.

`FloatSlider` supports only **one symbol per control** in the current implementation.

## 7.6 Parameter context for numeric evaluation

`ParameterManager.parameter_context` returns a live mapping from symbol to current value. `Plot.numeric_expression` binds this mapping into a `NumericFunction` using `DYNAMIC_PARAMETER` markers.

This is the bridge that makes plot reevaluation on slider movement clean and explicit.

## 7.7 Hook semantics

`Figure.add_param_change_hook(...)` registers callbacks that run **after** the figure rerenders on parameter change.

Current order in `Figure.render(reason="param_change", trigger=event)` is:

1. rerender active-view plots,
2. mark inactive view memberships stale,
3. run hooks,
4. schedule info card updates.

So hooks can rely on updated plot state and current parameter values.

## 7.8 Default parameter creation policy

If `Figure.plot(...)` infers parameters, it will automatically ensure they exist through `Figure.parameter(...)`.

Current default slider config in `ParameterManager` is:

- `value=0.0`
- `min=-1.0`
- `max=1.0`
- `step=0.01`

If different defaults are wanted package-wide later, this is the place to change them.

## 7.9 Snapshot behavior

`ParameterManager.snapshot(full=False)` returns an immutable value-only snapshot, and `full=True` returns a full `ParameterSnapshot` with metadata and capability fields.

This is an improvement over ad hoc detached dictionaries because snapshot objects support deterministic ordered iteration and unambiguous string-name lookups.

---

# 8. Info panel

The info panel architecture is smaller and more concrete than the old guide implied.

## 8.1 `InfoPanelManager` has two implemented lanes

### Lane 1: raw `Output` widgets

`get_output(id=...)` lazily creates and returns `ipywidgets.Output` instances in the info sidebar.

### Lane 2: simple cards

`set_simple_card(...)` builds cards from:

- static string segments,
- dynamic callable segments,
- or sequences mixing the two.

Dynamic segments are rendered into `HTMLMath` widgets and updated through a debounced scheduling path.

## 8.2 Dynamic info callable contract

Dynamic simple-card callables are invoked with:

- the owning `Figure`, and
- an `InfoChangeContext` with:
  - `reason`
  - `trigger`
  - `t`
  - `seq`

This is the real dynamic info update contract in the provided code.

## 8.3 View scoping

Simple cards can be view-scoped. The manager tracks an active view id and hides card outputs when their `view_id` does not match.

Important nuance: sidebar section visibility is still controlled globally by `has_info`, so the Info section may remain present even if no card for the active view is visible.

## 8.4 Debounce behavior

Each simple card gets its own `QueuedDebouncer`, currently configured at a short cadence suitable for interactive updates. That prevents a burst of parameter-change events from causing repeated full card rebuilds.

## 8.5 Error rendering

If a dynamic info callable raises, the exception is captured and rendered as escaped HTML inside a `<pre>` block rather than crashing the whole update path.

## 8.6 Snapshot limitations

`InfoPanelManager.snapshot()` only captures **simple cards**.

It stores:

- static text verbatim,
- dynamic segments as the placeholder string `"<dynamic>"`.

That means:

- raw output widgets are not round-tripped,
- arbitrary registered components are not round-tripped,
- dynamic callable implementations are not serialized.

This is important for reproducibility expectations.

## 8.7 Component registry caveat

`add_component(...)` and `get_component(...)` exist, but they are currently a registry only. If you want a richer component lifecycle, that will require new architecture work rather than just new documentation.

---

# 9. Legend sidebar

The legend sidebar is now a proper subsystem, not a cosmetic add-on.

## 9.1 `LegendPanelManager` owns legend rows

It keeps:

- a row model per plot id,
- deterministic plot ordering,
- the active view id,
- synchronization between plot visibility and UI toggle state.

## 9.2 Row structure

Each row contains:

- a `ToggleButton` styled as a colored marker control,
- an `HTMLMath` label widget,
- a hidden style widget used to inject CSS.

So the current legend is **not** a checkbox list. It is a toggle-button-based, toolkit-owned legend row system.

## 9.3 View filtering

Rows are only shown when the underlying plot belongs to the current active view.

This makes legend visibility truly view-aware, unlike parameters which are currently global and unlike info section visibility which is only partially view-aware.

## 9.4 Color inference behavior

If a plot has no explicit color, the legend manager tries to infer a meaningful marker color by looking at:

1. explicit plot color,
2. trace line or marker color,
3. parent figure colorway or Plotly default palette.

This is a small but important UX detail because otherwise legend markers would degrade to gray before explicit styling is applied.

## 9.5 Visibility contract

Legend toggles write back to `plot.visible` using strict boolean semantics.

Any future support for richer visibility states would require coordinated changes to:

- `VisibleSpec`
- `Plot.visible`
- legend row syncing
- possibly code generation and snapshots

---

# 10. Numeric and symbolic layer

The plotting layer is powered by a substantial symbolic and numeric support stack.
## 10.1 `numpify.py` is the numeric core

`numpify.py` compiles SymPy expressions into `NumericFunction` objects that support:

- explicit variable ordering,
- vectorized NumPy evaluation,
- custom function bindings,
- cached compilation,
- symbolic metadata,
- freezing and unfreezing of parameter bindings,
- dynamic parameter bindings through `DYNAMIC_PARAMETER`.

This is not just a utility used by plotting. It is a foundational abstraction used across the package.

## 10.2 `NumericFunction` is the reusable compiled callable abstraction

A `NumericFunction` owns:

- the underlying callable,
- symbolic metadata,
- call signature metadata,
- variable-spec metadata,
- optional keyed variables,
- optional frozen values,
- optional dynamic values coming from a live parameter context.

This is what makes callable-first plotting and live slider-bound evaluation fit into one model.

## 10.3 Shared variable grammar

`figure_plot_normalization.py` deliberately reuses the same variable grammar as `numpify._normalize_vars(...)`.

That means the same `vars=` style can be shared across:

- plotting,
- numeric compilation,
- freeze and unfreeze workflows.

This is a good design and should be preserved.

## 10.4 `NamedFunction.py`

`NamedFunction.py` lets developers define SymPy `Function` subclasses from either a callable or a small spec class.

Key features include:

- symbolic rewrite support,
- numeric implementation attachment through `f_numpy`,
- better signatures for interactive help,
- compatibility with the `numpify` compilation path.

If the toolkit adds more custom symbolic authoring features, they should integrate here rather than bypassing this contract.

## 10.5 Parsing and conversion helpers

### `InputConvert.py`

This is the shared conversion layer for numeric-like user input. It accepts numbers directly and also parses strings, including SymPy-parsable text like `pi/2`.

### `ParseLaTeX.py`

This wraps SymPy's LaTeX parser with a backend fallback strategy and raises a package-specific `LatexParseError` when both backends fail.

### `Symbolic.py`

This module provides notebook-friendly symbolic families and infix helpers. It is primarily a usability layer, not a runtime plotting core.

### `numeric_operations.py`

This module adds higher-level numeric helpers such as integration, Fourier series coefficients, and simple audio playback. They are useful, but they are not part of the main figure orchestration path.

---

# 11. Snapshot and code generation architecture

Snapshots and code generation are now part of the package's core story.

## 11.1 Snapshot objects

### `FigureSnapshot`

Captures:

- current figure title,
- effective figure sampling default,
- current-view default x and y range,
- full parameter snapshot,
- plot snapshots,
- simple info card snapshots,
- view snapshots,
- active view id.

### `PlotSnapshot`

Captures:

- plot id,
- variable,
- symbolic expression,
- parameters,
- label,
- visibility,
- domain and sampling overrides,
- style fields,
- view memberships.

### `ParameterSnapshot`

Captures ordered parameter metadata and can also emit a detached value map.

## 11.2 Code generation path

`Figure.to_code()` and `Figure.get_code()` delegate to `codegen.figure_to_code(...)`.

Current codegen can emit two interface styles:

- `context_manager`
- `figure_methods`

It also recreates:

- figure construction,
- added views,
- parameters,
- plots,
- simple static info cards.

## 11.3 Important serialization limits

There are two big current limits.

### Limit 1: dynamic info is not fully serializable

Dynamic info segments are emitted as commented guidance blocks, not live recreated code.

### Limit 2: pure callable-backed plots are not necessarily round-trippable

If a plot was created from a plain Python callable without meaningful symbolic metadata, the snapshot stores a symbolic placeholder rather than the original callable implementation.

That means code generation is fully trustworthy for symbolic plots and for `NumericFunction` instances carrying symbolic metadata, but not for arbitrary opaque Python callables.

This is an important reality to document honestly.

## 11.4 Effective state vs exact state

One subtle example: `Figure.snapshot()` stores `sampling_points=self.sampling_points or 500`. That means the snapshot captures the effective default sample count, not the distinction between an explicit `500` and an unset value that currently falls back to `500`.

That is acceptable behavior, but it is worth understanding when reasoning about round-trip fidelity.

---

# 12. End-to-end control flow

This section describes how the main pieces collaborate at runtime.

## 12.1 Construction

When `Figure(...)` is constructed, it:

1. handles a small set of deprecated backward-compatibility kwargs,
2. creates `FigureLayout`,
3. creates `ParameterManager`, `InfoPanelManager`, and `LegendPanelManager`,
4. creates `ViewManager` and `FigureViews`,
5. adds the initial default view,
6. synchronizes sidebar visibility,
7. optionally displays immediately if `show=True`.

## 12.2 Display

When the figure is displayed:

- `Figure._ipython_display_()` displays `self._layout.output_widget`,
- the layout tree becomes live in the notebook frontend,
- PlotlyPane's frontend logic can start reacting to real layout sizes.

## 12.3 Entering figure context

When code runs inside `with fig:`:

1. the figure is pushed onto the thread-local current-figure stack,
2. the figure's output panel starts capturing prints and display output,
3. module-level helpers like `plot(...)` and `parameter(...)` route to this figure.

## 12.4 Plot registration

When `fig.plot(...)` is called:

1. inputs are normalized,
2. parameters are inferred if not explicit,
3. parameter controls are ensured,
4. a new `Plot` is created or an existing one is updated,
5. the legend manager is notified,
6. sidebar visibility is refreshed.

## 12.5 Parameter change

When a slider changes:

1. the control emits a trait change,
2. `ProxyParamRef.observe(...)` normalizes it into a `ParamEvent`,
3. `ParameterManager._on_param_change(...)` invokes `Figure.render("param_change", event)`,
4. active-view plots rerender,
5. inactive view memberships are marked stale,
6. registered hooks run,
7. info cards schedule updates.

## 12.6 Relayout and pan and zoom

Each view backend registers a relayout watcher on that view's Plotly layout.

Relayout events are debounced per view through `QueuedDebouncer`. When the debounced call runs:

- if it targets the active view, `Figure.render(reason="relayout")` runs,
- if it targets an inactive view, that view is marked stale.

This is a sensible compromise between responsiveness and notebook performance.

## 12.7 View switch

When the active view changes:

1. `ViewManager.set_active_view(...)` stores the previous view's viewport,
2. the new view becomes active,
3. the info and legend managers update their active view,
4. the active view's Plotly widget gets its stored or default ranges,
5. all plots render for the new active view,
6. stale state for the activated view is cleared,
7. the layout tab selection and pane reflow are synchronized.

## 12.8 Snapshot and code generation

When `fig.snapshot()` is called, immutable state objects are built. When `fig.to_code()` is called, those snapshots are turned into a Python reconstruction script.

---

# 13. Extension patterns and maintainer checklists

The package is now large enough that extension work should follow explicit checklists.

## 13.1 Adding a new public plot option

If you add a new public plot keyword such as a style field, update all relevant layers:

1. `figure_plot_style.py` if it is a public style option,
2. `Figure.plot(...)` signature and docs,
3. `figure_api.plot(...)` signature,
4. `Plot.update(...)` and possibly `Plot.snapshot()`,
5. `PlotSnapshot` if it must round-trip,
6. `codegen._plot_call(...)` if it should be regenerated,
7. public docs and examples.

## 13.2 Adding a new per-view property

If you add new view state, update:

1. `View`,
2. `ViewManager.add_view(...)` and any switching logic,
3. `Figure.add_view(...)` and any active-view application logic,
4. `ViewSnapshot`,
5. `Figure.snapshot()`,
6. `codegen.figure_to_code(...)`,
7. any tab or axis UI wiring in `FigureLayout` and `Figure`.

## 13.3 Adding a new parameter metadata field

If a control should expose new metadata beyond `default_value`, `min`, `max`, or `step`, update:

1. the control class,
2. `ParamRef` documentation,
3. `ProxyParamRef.capabilities`,
4. `ParameterManager.snapshot(...)`,
5. code generation if the field must round-trip.

## 13.4 Adding a new custom parameter control

A custom control should usually provide:

- a `value` trait and `observe(..., names="value")` compatibility,
- `make_refs(symbols)` returning a `{Symbol: ParamRef}` mapping,
- optional `set_modal_host(host)` if it needs figure-level overlay behavior,
- optional metadata attributes exposed through ref capabilities.

Do not assume every control must look like `FloatSlider`, but do preserve the ref-first contract.

## 13.5 Adding a new plot type

The current system is line-trace oriented. If you add another plot type, keep the same separation of concerns:

- input normalization should stay outside `Figure`,
- per-plot render logic should stay outside `Figure`,
- snapshot and codegen behavior should be explicit,
- legend and view membership behavior should be defined, not accidental.

If the new plot type needs a different trace model, prefer a parallel plot class over bloating `Plot` with mode-specific branches everywhere.

## 13.6 Adding new module-level helpers

If you add a free function helper, update:

1. `figure_api.py`,
2. any current-figure routing needed in `figure_context.py`,
3. `Figure.py` re-exports,
4. `__init__.py` exports if the helper is package-public,
5. docs and discoverability examples.

---

# 14. Current limitations and gotchas

These are worth calling out explicitly because they affect both maintenance decisions and user expectations.

## 14.1 Figure-level range properties are really current-view properties

`Figure.x_range` and `Figure.y_range` are shorthands for the current view's default ranges. Do not document them as figure-global range state in future docs.

## 14.2 View metadata is only partially surfaced

`View.title`, `x_label`, and `y_label` are real model and serialization fields, but they are not fully reflected in the UI yet.

## 14.3 Inactive views are stale by design

Parameter changes and relayout events do not eagerly rerender every view. Inactive views are marked stale and rerender when activated.

This is a performance strategy, not a bug.

## 14.4 Raw info outputs and generic info components are not serialized

Only simple cards participate in snapshot and codegen.

## 14.5 Opaque callable-backed plots are not fully round-trippable

If reproducibility matters, prefer symbolic expressions or `NumericFunction` objects carrying symbolic metadata.

## 14.6 `plot()` auto-creates a figure; most other helpers do not

This asymmetry is intentional but easy to forget in tests and examples.

## 14.7 Auto-generated plot ids are capped at 100 tries

If `Figure.plot(...)` is called without an id, the current implementation searches for `f_0` through `f_99`. If you generate many plots programmatically, pass explicit ids.

## 14.8 Compatibility kwargs still exist in `Figure.__init__`

The constructor still accepts some deprecated compatibility arguments and warns:

- `display=`
- `debug=`
- `default_view_id=`
- `plotly_legend_mode=`

Do not build new features on top of those paths.

## 14.9 There is no public plot deletion API

If tests or user code need deletion, that is a missing feature, not just an undocumented one.

## 14.10 The package uses mixed naming conventions for compatibility

The archive contains both capitalized legacy-style modules (`Figure.py`, `Notebook.py`) and newer snake_case split modules. Preserve import compatibility if you reorganize.

---

# 15. Contributor discipline

The older guide's general documentation discipline is still good, but the current architecture suggests some more specific rules.

## 15.1 Keep `Figure` as a coordinator

New features should only live in `Figure.py` when they truly need coordinator-level orchestration.

Good reasons to touch `Figure.py`:

- wiring together managers,
- exposing a public convenience method,
- coordinating multiple subsystems,
- managing active-view shorthands,
- snapshot or codegen entry points.

Bad reasons to touch `Figure.py`:

- adding complex widget tree code,
- adding per-curve render branches,
- adding parameter metadata logic,
- adding pure normalization helpers.

## 15.2 Preserve pure-state versus widget-state boundaries

Try to keep these modules mostly pure and side-effect light:

- `figure_view.py`
- `figure_view_manager.py`
- `figure_plot_normalization.py`
- `figure_plot_style.py`
- snapshot modules
- `codegen.py`
- most of `numpify.py`

Try to keep UI-specific behavior in:

- `figure_layout.py`
- `PlotlyPane.py`
- `Slider.py`
- `figure_legend.py`
- the coordinator portions of `Figure.py`

## 15.3 Centralize public contracts

If the public API accepts friendly input shapes or discoverable options, centralize them.

The current code already does this well in two places:

- `figure_types.py` for public type aliases,
- `figure_plot_style.py` for plot-style keyword metadata.

Follow that pattern rather than scattering public contracts across docstrings.

## 15.4 Preserve discoverability

When adding a module or public type, document:

- what it owns,
- how it collaborates with neighboring modules,
- where developers should look next.

That is especially important now that the architecture is split across many files.

## 15.5 Keep `__slots__` and snapshots in sync

`Figure` uses `__slots__`. If you add coordinator state, update:

- `__slots__`,
- constructor initialization,
- snapshot and codegen if the new state should persist,
- any display or cleanup lifecycle needed in `__enter__` and `__exit__`.

## 15.6 Prefer explicit state capture over hidden magic

The package is strongest when behavior is explicit:

- view state is in `View`,
- parameter metadata is in refs and snapshots,
- generated code is derived from snapshots,
- dynamic parameter resolution goes through `NumericFunction` and `parameter_context`.

Keep following that style.

---

# 16. Testing strategy

Because the provided archive did not include the repository's test suite or tooling config, the safest updated testing guidance is architectural rather than command-specific.

## 16.1 Pure-Python unit tests should cover

- `InputConvert` conversion and failure paths,
- `figure_plot_normalization.normalize_plot_inputs(...)`,
- `figure_plot_style.resolve_style_aliases(...)`,
- `ViewManager` view lifecycle and stale-state policy,
- `ParameterSnapshot` and value-map lookup behavior,
- `numpify` variable grammar, freezing, and dynamic bindings,
- `codegen.figure_to_code(...)` output for representative snapshots.

## 16.2 Widget-level tests should cover

- parameter creation and control reuse,
- custom control `make_refs(...)` integration,
- legend row refresh and toggle synchronization,
- info card visibility by view,
- `Figure` view switching semantics,
- output capture behavior in `with fig:`.

## 16.3 Notebook or manual regression tests should cover

- PlotlyPane resizing under flex layout changes,
- tab switching and pane reflow,
- full-width toggle behavior,
- panning and zooming debounce behavior,
- live slider drags with plot rerendering,
- multi-view stale rerender behavior.

## 16.4 Reproducibility tests should cover

- `Figure.snapshot()` shape,
- `Figure.to_code()` round trips for symbolic plots,
- expected degradation behavior for dynamic info and opaque callable-backed plots.

## 16.5 When writing new tests, prefer subsystem-level tests

The current architecture is split enough that tests should generally target the module that owns the behavior. Do not only write broad coordinator tests when a small module test would be more stable and more precise.

---

# 17. Module index

## Entry points and routing

| Module | Role | Notes |
|---|---|---|
| `__init__.py` | Top-level package exports | Rebinds package `plot` after notebook wildcard imports |
| `Figure.py` | Main entry point and composition root | Defines `Figure`, `FigureViews`, `_ViewBackend`, and re-exports free helpers |
| `figure_api.py` | Module-level helper API | `plot()` auto-creates figures; other helpers require active figure |
| `figure_context.py` | Current-figure stack | Thread-local routing and figure-default sentinel logic |
| `Notebook.py` | Notebook convenience namespace | SymPy, NumPy, optional pandas, helper families, display utilities |
| `notebook_namespace.py` | Backward-compatible alias | Legacy import path to `Notebook.py` |

## Figure runtime core

| Module | Role | Notes |
|---|---|---|
| `figure_layout.py` | Widget tree and layout composition | Owns tabs, sidebar, output panel, full-width toggle |
| `PlotlyPane.py` | Responsive Plotly host | Frontend resize driver via `anywidget` |
| `figure_view.py` | Pure view model | Stores ranges, labels, stale flags |
| `figure_view_manager.py` | View lifecycle policy | Registration, selection, stale marking |
| `figure_plot.py` | Per-curve render model | One plot, many per-view trace handles |
| `figure_plot_normalization.py` | Plot input grammar | Normalizes expression, callable, and `NumericFunction` inputs |
| `figure_plot_style.py` | Public style-option contract | Central discoverability for plot style kwargs |
| `figure_types.py` | Shared public typing aliases | Friendly input contracts such as `RangeLike` |
| `figure_parameters.py` | Parameter registry and hooks | Owns refs, controls, snapshots, live parameter context |
| `ParamRef.py` | Ref protocol and default proxy | Normalized parameter abstraction |
| `ParamEvent.py` | Immutable parameter event | Stable observer payload |
| `Slider.py` | Default parameter control | Single-symbol float slider with settings modal |
| `figure_info.py` | Info sidebar manager | Raw outputs plus simple cards |
| `figure_legend.py` | Legend sidebar manager | View-filtered toggle rows |
| `debouncing.py` | Debounce utility | Used for relayout and info updates |

## Persistence and code generation

| Module | Role | Notes |
|---|---|---|
| `FigureSnapshot.py` | Immutable figure snapshot types | Includes `InfoCardSnapshot` and `ViewSnapshot` |
| `PlotSnapshot.py` | Immutable plot snapshot | Symbolic expression plus style and membership |
| `ParameterSnapshot.py` | Immutable parameter snapshot | Ordered metadata and value-map views |
| `codegen.py` | Snapshot to Python source | Emits context-manager or method-style reconstruction code |

## Numeric and symbolic helpers

| Module | Role | Notes |
|---|---|---|
| `numpify.py` | SymPy to NumPy compilation core | `NumericFunction`, caching, freeze and unfreeze, dynamic bindings |
| `numeric_callable.py` | Compatibility export layer | Re-exports from `numpify.py` |
| `NamedFunction.py` | Custom SymPy function authoring | Bridges symbolic definitions and numeric implementations |
| `InputConvert.py` | Friendly numeric input parsing | Supports numeric values and symbolic strings |
| `ParseLaTeX.py` | LaTeX parser wrapper | Backend fallback and package-specific error type |
| `Symbolic.py` | Notebook symbolic convenience layer | Families and infix relational helpers |
| `numeric_operations.py` | Higher-level numeric helpers | Integration, Fourier series, audio playback |

---

# 18. Bottom line for maintainers

The most important mindset change is this:

`Figure.py` is now the **entry point and coordinator**, not the place where every behavior should live.

When working on the toolkit:

- start from `Figure.py` to understand orchestration,
- move quickly into the dedicated `figure_*` owner module for the behavior you are changing,
- update snapshots and code generation whenever new state must round-trip,
- keep view state, parameter state, plot state, and widget state cleanly separated,
- document real current behavior, especially where metadata exists but UI wiring is incomplete.

That mental model matches the provided source much better than the older single-file narrative.
