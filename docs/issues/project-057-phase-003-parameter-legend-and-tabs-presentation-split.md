# Project 057 / Phase 003: filter-driven legends, parameter presentations, and mount management

## Status
Unknown

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Why the earlier Phase 003 draft was inadequate
The earlier draft centered the redesign on a **peer-section model**. That was too abstract and it started at the wrong layer.

The real problem in the original code is not that the shell lacks a registry of peer items. The real problem is that the code still uses **`view` as the hidden organizing primitive** for all of the following at once:

- which Plotly widget a plot lives on
- which legend rows are shown
- which info cards are shown
- which plots render now versus later
- which shell page is treated as current

As long as that remains true, a shell-first redesign cannot solve the problem. It can only rearrange one global legend box, one global info box, and one global parameter box.

This replacement Phase 003 therefore changes the architectural center.

The center is **not** “peer sections”.
The center is **not** “soft associations”.
The center is **not** a generalized tabs/presenter framework.

The center is:

- a global plot store
- a global parameter store
- explicit **filters** over those stores
- legend and parameter **presentations** built from those filters
- a small mount manager that places already-built presentation roots

A “stage” in this plan is only the user’s name for a **Plotly plot widget/container**. It is **not** a new architecture object.

## Design corrections carried into this blueprint
This replacement blueprint incorporates the corrections from design review and from the follow-up discussion:

1. **Do not introduce a new stage architecture object.** A stage is just a Plotly plot widget/container.
2. **Filters are the primary abstraction.** Legends and parameter panels are filtered presentations over global stores.
3. **Remove `view` from the new core contracts.** `view` may survive briefly only in compatibility adapters while the core moves to explicit plot-widget queries.
4. **Split management from presentation for parameters.** The global parameter store must exist without widget/layout ownership.
5. **Split legend membership/state from legend widgets.** The default legend filter is “plots shown on this Plotly widget”.
6. **Do the mounting work after the filtered presentations exist.** Mounting is a small placement layer, not the architectural center.

## Detailed analysis of the original code

### 1. The shell still models singleton sidebar categories, not independently mountable presentations
`src/gu_toolkit/figure_shell.py:15-16` defines `_VALID_SECTION_IDS = ("legend", "parameters", "info")`.

`src/gu_toolkit/figure_shell.py:78-104` then validates that:

- only those singleton ids may appear in a shell preset,
- no section id may be mounted more than once, and
- every preset must define exactly one stage page.

That means the current shell model cannot represent two legends, two parameter panels, or two info groups even before legend or parameter logic runs.

This is a symptom, but it is not the root source. It matters because it shows how strongly the rest of the layout was shaped around one global panel per category.

### 2. `FigureLayout` still builds one legend panel, one parameter panel, and one info panel
`src/gu_toolkit/figure_layout.py:294-298` stores visibility only for three categories: `legend`, `parameters`, and `info`.

`src/gu_toolkit/figure_layout.py:326-381` builds one `view_selector`, one `view_stage`, one `legend_panel`, one `params_panel`, and one `info_panel`.

`src/gu_toolkit/figure_layout.py:479-504` then hard-wires those singleton surfaces into `_section_widgets` and `_shell_slots`.

`src/gu_toolkit/figure_layout.py:943-1005` reduces sidebar visibility to three booleans: `has_params`, `has_info`, and `has_legend`.

`src/gu_toolkit/figure_layout.py:2070-2148` and `2194-2249` rebuild and show shell pages by mounting those singleton panel widgets and toggling them according to the active shell page.

That means layout already assumes that there is one legend surface and one parameter surface. Even if legend and parameter logic were improved later, the layout layer would still force them back into single global boxes.

### 3. `Figure` wires one global legend manager and one global info manager and then synchronizes them through active view
`src/gu_toolkit/Figure.py:423-437` constructs one `ParameterManager`, one `InfoPanelManager`, and one `LegendPanelManager`.

`src/gu_toolkit/Figure.py:470-482` creates the initial view and immediately calls `self._legend.set_active_view(self.views.current_id)`.

`src/gu_toolkit/Figure.py:1032-1050` adds each new view to layout and, if active, pushes that `view_id` into both `InfoPanelManager` and `LegendPanelManager`.

`src/gu_toolkit/Figure.py:1058-1139` changes the active view by synchronizing:

- `FigureLayout`
- `InfoPanelManager`
- `LegendPanelManager`
- reflow
- render scheduling

`src/gu_toolkit/Figure.py:1256-1263` collapses shell state back down to three visibility booleans.

This shows that `Figure` is still treating the active view as the coordinator for shell content, not just for plotting.

### 4. Legend membership is still “plots in the active view”, not “plots selected by a filter”
`src/gu_toolkit/figure_legend.py:772-790` shows that `LegendPanelManager` requires a concrete `layout_manager` or `layout_box`. The legend manager is therefore coupled directly to a specific notebook widget surface.

`src/gu_toolkit/figure_legend.py:794-798` stores `_plots`, `_ordered_plot_ids`, and `_active_view_id` on the same object.

`src/gu_toolkit/figure_legend.py:1529-1575` provides `set_active_view(...)`.

`src/gu_toolkit/figure_legend.py:1577-1645` builds the visible row list by iterating global plots and keeping only those for which `_plot_in_active_view(plot)` is true.

`src/gu_toolkit/figure_legend.py:1647-1652` defines `_plot_in_active_view(plot)` as membership in `plot.views`.

This is the clearest evidence that legend behavior is not yet based on an explicit filter. It is still based on a hidden convention: “show plots that belong to whatever view is active now.”

### 5. Info content is still one global box with per-card view gating
`src/gu_toolkit/figure_info.py:167-177` stores `view_id` on each simple info card.

`src/gu_toolkit/figure_info.py:179-207` stores exactly one `_layout_box` and one `_active_view_id` in `InfoPanelManager`.

`src/gu_toolkit/figure_info.py:332-342` appends every new output directly into `_layout_box.children`.

`src/gu_toolkit/figure_info.py:641-647` stores `card.view_id = view`.

`src/gu_toolkit/figure_info.py:646-697` makes visibility equal to `card.view_id is None or card.view_id == self._active_view_id`.

That means info content is not yet represented as independently mountable presentations. It is one global box whose children are shown or hidden according to active view.

### 6. Parameter management still mixes storage, render hooks, control widgets, and concrete mounting
`src/gu_toolkit/figure_parameters.py:198-221` shows that `ParameterManager` requires a `layout_manager` or `layout_box`.

`src/gu_toolkit/figure_parameters.py:227-236` mounts controls directly into that layout host.

`src/gu_toolkit/figure_parameters.py:364-419` creates widgets, mounts them immediately, makes refs, binds change callbacks, and stores all of that in the same object.

`src/gu_toolkit/figure_parameters.py:1363-1454` exposes concrete widgets directly through `widget()` and `widgets()`.

This means the current parameter manager is not a pure parameter store. It is a fused state-and-presentation object.

### 7. Plot and field objects already contain the dependency data the new design needs
`src/gu_toolkit/figure_plot.py:689-734` exposes `plot.parameters`.

`src/gu_toolkit/figure_plot.py:737-760` exposes `plot.views`.

`src/gu_toolkit/figure_plot.py:344-365` stores `_handles` and `_view_ids` and creates one trace handle per view membership.

`src/gu_toolkit/figure_field.py:1558-1559` exposes `ScalarFieldPlot.views`.

`src/gu_toolkit/figure_field.py:3404-3409` and `3739-3754` use the same view-based runtime pattern as cartesian plots.

This is important because it shows that the repo already has the raw information needed for the new design:

- a global plot store (`Figure.plots`)
- per-plot parameter dependencies (`plot.parameters`)
- a mapping from plot memberships to concrete Plotly runtimes/handles (`plot._handles`, `plot.views`)

The missing piece is not information. The missing piece is **how that information is organized and queried**.

### 8. Rendering is still keyed to active view, but it already has the right stale/deferred pattern
`src/gu_toolkit/figure_diagnostics.py:411-456` renders only the current view and marks non-current memberships stale after parameter changes.

`src/gu_toolkit/figure_plot.py:2433-2449` and `src/gu_toolkit/figure_field.py:3739-3754` follow the same rule: render the active view now, mark others stale.

This matters because hidden plot widgets later need the same pattern. The stale/deferred idea is already present. The problem is that it is keyed to `view_id` instead of to visible plot-widget targets.

### 9. The browser-side visibility boundary is already correct in `PlotlyPane`
`src/gu_toolkit/PlotlyPane.py:643-655` computes host visibility from DOM connection, CSS display/visibility, and client rects.

`src/gu_toolkit/PlotlyPane.py:942-952` waits for a real plot element, host visibility, and measurable geometry before resizing.

This is strong evidence that the redesign should not invent a Python-owned sizing architecture. Plotly sizing should continue to follow actual DOM visibility and measurement.

## Runtime probes on the original repo
The code-level evidence above is structural. I also checked behavior by instantiating the original repo.

A short appendix with the observed runtime results is included in `project-057-phase-003-runtime-probes.md`.

### Probe A: two views, two plots, one legend surface
When creating two views and assigning one plot to each, the figure still exposes exactly one legend/info/parameters surface in `FigureLayout`, and the legend flips its visible rows only by changing the active view.

Observed behavior from the original repo:

- plots were registered globally as `p1 -> ('main',)` and `p2 -> ('second',)`
- the layout exposed one `legend` slot, one `parameters` slot, and one `info` slot
- legend rows showed `['p1']` in the main view and `['p2']` after switching to the second view

That confirms that the legend is one global panel filtered by active view, not an independently mountable filtered presentation.

### Probe B: two info cards, one shared box
When creating two info cards with different `view=` values:

- both cards were appended into the same `_layout_box.children`
- switching views only changed each card’s `layout.display`

That confirms the same pattern on the info side: one global surface plus active-view gating.

## Core source of the problem
The core source is **not** merely that the shell uses singleton section ids.
The core source is **not** merely that legends are on the wrong side of the figure.
The core source is **not** merely that tabs/pages are too rigid.

The real source is that **`view` is overloaded and leaks across too many responsibilities**.

Today, `view` simultaneously means:

1. the concrete Plotly runtime/widget a plot renders into
2. the grouping rule for legend membership
3. the grouping rule for info visibility
4. the unit of stale/render scheduling
5. the shell control unit that the layout toggles

Because those concerns are fused, the rest of the system collapses into the wrong shape:

- one legend manager that filters rows by active view
- one info box that filters children by active view
- one parameter manager that owns one global control surface
- one layout that toggles one legend/info/params set according to one active shell page

This is why the earlier peer-section draft was inadequate. It attacked shell shape before removing the overloaded organizing primitive.

## Evidence that this is the core source and not just a symptom
A useful check is to ask whether a proposed “fix” would still leave the same problem in place.

### Why “more shell sections” is not enough
Even if `figure_shell.py` allowed multiple legend ids, `LegendPanelManager.refresh()` would still define membership as `_plot_in_active_view(plot)` using `plot.views`.

That would give the project more places to mount a legend widget, but each legend would still be organized around the same active-view rule.

### Why a generic section registry is not enough
Even if the shell used a registry of section records, `ParameterManager` would still require a concrete layout box and `InfoPanelManager` would still append outputs into one `_layout_box.children` container.

That would reorganize mounting metadata without separating storage from presentation.

### Why a new tabs/page hierarchy is not enough
Pages and tabs only control **where** content is shown. They do not define **what content belongs in a legend** or **which parameters belong in a parameter panel**.

The real missing abstraction is the **filter**.

### Why “stage” should not become a new central object
A “stage” here is simply the user’s name for a Plotly plot widget/container.

Creating a new stage architecture object would risk rebuilding the same over-generalized system under a different name. The real unit that matters is:

- a concrete Plotly widget as an anchor object
- a filter that projects plots or parameters relative to that widget

That is the direct, concrete requirement.

## Revised implementation blueprint

### Design principle
Keep the global stores global. Build filtered presentations over them. Mount those presentations wherever needed.

That means:

- plots remain global objects in `Figure.plots`
- parameters remain global objects in a parameter store
- a legend is a **filtered presentation of plots**
- a parameter panel is a **filtered presentation of parameters**
- one common filter input is a concrete Plotly plot widget/container
- a small mount manager places those already-built presentation roots into layout slots

## 1. Remove `view` from the new core contracts
The new core contracts introduced in this phase must not use `view_id` as the organizing primitive for legend membership, parameter presentation membership, or info visibility.

That means:

- no legend API should require `set_active_view(...)`
- no parameter presentation API should require a layout box at construction time
- no info presentation API should rely on `card.view_id`
- no mount/layout API should require `view_id` to decide which legend or parameter panel belongs where

A temporary compatibility adapter may translate old public `view=` calls into the new internals during migration, but the **core contracts themselves** must be `view`-free.

## 2. Introduce explicit membership queries instead of hidden view conventions
Before legend and parameter presentation can be rewritten, the repo needs explicit query points for the relationships that are currently buried in `view` memberships.

At minimum, the codebase must be able to answer two questions directly:

### A. Which global plots are shown on this Plotly widget?
The answer should come from a dedicated query API, not from scattered `plot.views` checks.

Suggested query surface:

```python
fig.plots_for_plot_widget(plot_widget) -> tuple[PlotLike, ...]
```

Initial implementation may derive this from existing per-view handles, but callers outside the compatibility layer should not need to reason about `view_id`.

### B. Which global parameters are used by the plots shown on this Plotly widget?
Suggested query surface:

```python
fig.parameters_for_plot_widget(plot_widget) -> tuple[str, ...]
```

This should compute the union of `plot.parameters` across plots returned by `plots_for_plot_widget(plot_widget)`.

This step is crucial. Without these two queries, legends and parameter panels will continue to reinvent view-based selection logic in different places.

## 3. Split `ParameterManager` into a store layer and a presentation layer
The current `ParameterManager` should be decomposed into two concrete parts.

### A. `ParameterStore`
Owns:

- parameter registry
- parameter symbols / specs
- current values
- refs and change propagation
- render-trigger semantics
- subscription hooks
- render parameter context snapshots

Does **not** own:

- layout boxes
- mounting
- widget ordering/grouping in the shell

### B. `ParameterPanel` (or `ParameterPresentation`)
Owns:

- widget creation/binding
- control ordering/grouping
- the stable widget root used for mounting
- any modal/dialog host wiring
- a parameter filter

Does **not** own:

- authoritative parameter state
- figure render scheduling policy beyond calling the store protocol

### Required store/presentation protocol
Keep the protocol small and concrete. The presentation layer should only need something like:

```python
class ParameterStoreProtocol(Protocol):
    def list_parameters(self) -> tuple[str, ...]: ...
    def get_parameter_spec(self, name: str) -> Any: ...
    def get_value(self, name: str) -> Any: ...
    def set_value(self, name: str, value: Any) -> None: ...
    def subscribe(self, callback: Callable[[set[str]], None]) -> Callable[[], None]: ...
```

That is enough for multiple independent parameter presentations.

### Default parameter filter
The default filter should be:

> given a Plotly plot widget, include only parameters that intervene in plots shown on that widget

This should be implemented from the explicit query API above, not by inspecting active view.

## 4. Split legend logic into a filtered model and a presentation layer
The legend should also be decomposed into two concrete parts.

### A. `LegendModel` or `LegendController`
Owns:

- global plot source
- plot filter
- ordering
- row state
- visibility/toggle/style intent
- subscription hooks to plot changes if needed

Does **not** own:

- layout box
- header toolbar host
- notebook-only widget mounting
- active-view state

### B. `LegendPanel` or `LegendPresentation`
Owns:

- row widgets
- toolbar widgets
- dialogs
- anywidget/ipywidgets glue
- stable root widget for mounting

Does **not** decide membership by itself. It renders whatever plot subset the model exposes.

### Default legend filter
The default filter should be:

> given a Plotly plot widget, include only plots shown on that widget

This is the direct replacement for `_plot_in_active_view(plot)`.

### Suggested filter shape
Do not overengineer this.

A plain callable is enough:

```python
PlotFilter = Callable[[Figure], tuple[Any, ...]]
ParameterFilter = Callable[[Figure, ParameterStoreProtocol], tuple[str, ...]]
```

The important part is not the class hierarchy. The important part is that membership is **explicit and testable**.

## 5. Keep info/output work minimal in this phase
Info should not become a new abstraction stack.

This phase only needs enough change to stop forcing all info content into one global view-filtered box.

That means:

- support multiple independent info roots or info groups
- make them mountable separately
- remove active-view-based visibility from the new core path
- keep optional filtering simple if needed later

The old pattern of “append everything into one `_layout_box.children` and toggle display by view” should not survive into the new core.

## 6. Introduce a small mount manager
Only after filtered presentations exist should the shell/layout layer be revised.

The mount layer should stay deliberately small.

It needs to do only this:

- register mountable widget roots
- map them to slots/containers/pages
- apply default placement rules
- allow user overrides
- notify mountables when they become visible/hidden

It does **not** need to be a full presenter framework.

Suggested mountable shape:

```python
@dataclass
class MountItem:
    id: str
    kind: str
    root_widget: Any
    on_show: Callable[[], None] | None = None
    on_hide: Callable[[], None] | None = None
```

Suggested manager surface:

```python
class MountManager:
    def register(self, item: MountItem) -> None: ...
    def mount(self, item_id: str, slot: str) -> None: ...
    def set_visible(self, item_id: str, visible: bool) -> None: ...
```

The current notebook shell can then become one concrete consumer of this mount layer, and later HTML can become another.

## 7. Preserve PlotlyPane as the browser-owned visibility and sizing boundary
Do not rewrite `PlotlyPane` sizing. Keep the current browser-owned visibility/measurement behavior.

The only change needed at this phase boundary is:

- hidden plot widgets may defer expensive refresh work
- visible transitions should request refresh/reflow
- the actual “is it visible and measurable?” logic remains in `PlotlyPane`

That aligns the redesign with the strongest existing runtime code instead of fighting it.

## Implementation sequence for the third-party developer
The sequence matters. Filters and store/presentation splits must land before the mount-layer migration, otherwise the refactor will just rebuild the old coupling behind new shell objects.

### Step 1. Remove `view` from the new core contracts and add explicit plot-widget membership queries
Implement figure-level queries that answer:

- `plots_for_plot_widget(plot_widget)`
- `parameters_for_plot_widget(plot_widget)`

At first, these may be derived from existing view/handle state internally, but new callers must not need to query `view` directly.

This step is where `view` stops being the normal architectural boundary for legend membership, parameter membership, info visibility, or mount placement.

### Step 2. Extract `ParameterStore` from `ParameterManager`
Move parameter registry/state/hook logic into a widget-free store.

Leave the existing public API working through a compatibility facade if needed, but remove layout-box ownership from the store.

### Step 3. Implement filtered `ParameterPanel`
Create a presentation object that subscribes to the store and renders only the parameters selected by its filter.

Default filter: parameters used by plots shown on a given Plotly widget.

### Step 4. Extract `LegendModel` from `LegendPanelManager`
Move plot selection, row state, and actions into a model/controller object that receives a plot filter.

Delete the active-view-centric row-selection rule from the new code path.

### Step 5. Implement filtered `LegendPanel`
Create a presentation object that renders the model and owns widget/dialog details only.

### Step 6. Decouple info from one global box
Introduce independently mountable info roots or grouped output panels.

### Step 7. Replace layout-owned singleton panels with mountables
Refactor `FigureLayout` so it mounts already-built legend panels, parameter panels, info groups, and plot widgets into slots rather than owning one singleton surface for each.

### Step 8. Rephrase render scheduling around visible plot widgets
Migrate the existing stale/deferred pattern away from active view and toward visible plot-widget targets.

### Step 9. Keep legacy APIs behind adapters only
If public `view=` or `fig.views[...]` behavior must survive temporarily, confine it to compatibility adapters. The new legend, parameter presentation, info, and mount paths must not depend on it.

## Why this is the best correct approach

### It attacks the actual coupling point
The problem is the overload of `view`, not a lack of metadata objects. This design removes `view` from the new core contracts and replaces it with explicit, testable filters.

### It uses information the repo already has
The repo already knows:

- all plots (`Figure.plots`)
- per-plot parameter dependencies (`plot.parameters`)
- concrete trace/runtime memberships (`plot._handles`, `plot.views`)

So the redesign does not invent speculative data. It makes existing data queryable in the right way.

### It keeps the refactor on the relevant modules
The necessary work is concentrated in:

- `Figure.py`
- `figure_plot.py`
- `figure_field.py`
- `figure_parameters.py`
- `figure_legend.py`
- `figure_info.py`
- `figure_layout.py`
- `figure_shell.py`

It does not require rewriting:

- sampling/numeric compilation
- code generation
- unrelated notebook helpers
- `PlotlyPane` sizing internals

### It is not a stopgap
This is not “add more shell presets.”
This is not “rename views to stages.”
This is not “add a generic section registry and hope layout becomes flexible.”

It changes the real organizing primitive from:

- active-view-derived membership

to:

- explicit filters over global stores

That is the core structural correction.

### It stays concrete instead of overengineered
This plan deliberately avoids:

- a generalized section-association model
- a large tabs/presenter hierarchy
- a new “stage runtime” framework
- a custom HTML UI stack

The abstractions are kept to the minimum that removes real coupling:

- store
- filter
- presentation
- mount manager

## Non-goals for this phase
This phase should not:

- rewrite `PlotlyPane`
- rewrite sampling or symbolic compilation
- build the standalone HTML bootstrap yet
- finalize every deprecation on the public `view` API in the same patch
- invent a parallel custom DOM UI

## Exit criteria
- [ ] No new legend or parameter presentation contract depends on `view_id`.
- [ ] The codebase exposes an explicit query for plots shown on a given Plotly plot widget.
- [ ] The codebase exposes an explicit query for parameters used by plots shown on a given Plotly plot widget.
- [ ] Parameter state/storage exists independently from widget presentation.
- [ ] Legend membership/state exists independently from widget presentation.
- [ ] Multiple legends can be created by applying different filters.
- [ ] Multiple parameter presentations can be created by applying different filters.
- [ ] Info content is no longer forced through one global view-filtered box in the new path.
- [ ] Layout mounts already-built presentation roots instead of owning one singleton legend/info/params surface.
- [ ] Hidden plot widgets may defer work and visible transitions trigger refresh/reflow without replacing PlotlyPane’s browser-owned measurement logic.

## Recommended tests
- add a figure with two Plotly plot widgets and verify that two legends filtered by widget show different plot subsets
- add a figure with two Plotly plot widgets and verify that two parameter panels filtered by widget show different parameter subsets
- verify that `ParameterStore` can be tested without constructing `FigureLayout`
- verify that `LegendModel` can be tested without constructing `FigureLayout`
- verify that info outputs can be mounted into more than one independent root
- verify that hidden plot widgets mark stale and refresh when shown
- keep an integration test that confirms the default notebook layout still looks close to today’s behavior while being assembled from mountables
