# Project 036: CSS and Plot Layout Logging

## Status
Proposed

## Goal/Scope
Add a dedicated, opt-in logging and geometry-introspection layer that makes layout and responsive-design failures debuggable across the current notebook stack:

- `Figure` orchestration and reflow requests
- `FigureLayout` widget-tree mutations
- per-view host visibility and sizing state
- `PlotlyPane` / `PlotlyResizeDriver` frontend measurements and resize attempts
- sidebar and slider-modal geometry changes that affect available plot area
- debounce/queue behavior that can hide or collapse resize traffic

This project is **diagnostic only**. It must not attempt to fix the sizing bug itself, redesign the layout, or change the current layout policy.

## Summary of design
The current codebase already has most of the architectural pieces needed for responsive Plotly panes, but it lacks end-to-end observability.

Today, geometry changes originate in Python (`Figure`, `FigureLayout`, sidebar visibility, view activation, full-width toggles), while actual size measurement only exists in the browser (`PlotlyResizeDriver._esm`). The missing layer is a correlated log trail that answers all of the following in one place:

1. What geometry-affecting event happened?
2. Which view and pane were targeted?
3. Was a reflow request emitted from Python?
4. Did the frontend driver receive that request?
5. What size did the frontend actually measure for the host, clip ancestor, and Plotly DOM?
6. Was resize applied, skipped, or rate-limited?
7. Did a later Plotly relayout/render follow?

The recommended design is a structured logging stack with stable correlation ids, small geometry snapshots, and a JS-to-Python forwarding path for browser-side events. The log stream should be low-overhead when disabled, detailed when enabled, and explicit about whether a zero-size or hidden-view condition is expected versus erroneous.

The design should build on the existing standard-library `logging` approach already used by `Figure.py`; it should **not** reintroduce `Figure(debug=...)`-style configuration as the main entry point.

## Evidence
Current source analysis shows a clear observability gap around layout and responsive sizing:

- `Figure._request_active_view_reflow()` discards its `reason` and only calls `self.views.current.pane.reflow()`; no request id, target pane id, or before/after state is logged.
- `PlotlyResizeDriver.reflow()` currently sends only `{"type": "reflow"}` to the frontend, so the browser receives no structured context about *why* the request occurred.
- `Figure._log_render()` only logs coarse render/range information and does not cover layout mutations, host sizing, clip sizing, or Plotly resize outcomes.
- `FigureLayout` mutates `display`, `flex`, `width`, `max_width`, and page visibility state without any logging of the resulting layout intent.
- `PlotlyResizeDriver._esm` has a `debug_js` flag, but it only writes to the browser console via `safeLog(...)`; nothing is forwarded back into Python logs or a per-figure debug buffer.
- Hidden inactive view pages use `display="none"`, which means their DOM geometry is intentionally unavailable. The current code does not distinguish that expected zero-size state from a failure to size the active pane.
- `tests/test-responsive_plotly.ipynb` still contains unchecked manual verification items for responsive resize behavior, and open issue `bug-022-responsive-plotly-side-pane.md` explicitly calls out the end-to-end verification gap.
- The historical `view_tabs` / `plot_container` model still appears in stale tests and closed docs, which increases the risk of debugging the wrong architecture.

## Current-state architecture relevant to logging
These are the important ownership boundaries in the current codebase.

### 1. `FigureLayout` owns widget composition and geometry intent
`src/gu_toolkit/figure_layout.py` defines the active notebook widget tree:

- `root_widget`
- `content_wrapper`
- `left_panel`
- `view_selector`
- `view_stage`
- one persistent `_ViewPage.host_box` per view
- `sidebar_container`
- `print_area`

It decides which page is visible and whether the sidebar is shown, but it does **not** measure real DOM pixels.

### 2. `Figure` owns orchestration and reflow triggers
`src/gu_toolkit/Figure.py` wires the layout and managers together. It triggers explicit reflows after geometry-affecting events such as:

- adding a view
- activating a different view
- removing a view
- toggling full-width mode
- changing sidebar visibility after params/info/legend state changes

It also owns the Plotly relayout callback routing and the figure-level `QueuedDebouncer` for relayout events.

### 3. `View` owns stable per-view runtime
`src/gu_toolkit/figure_view.py` gives each view its own stable:

- `FigureWidget`
- `PlotlyPane`
- selector title
- default axis ranges
- remembered viewport ranges
- axis labels

This is important because logging must correlate events with the *view* and the *pane*, not only the figure.

### 4. `PlotlyPane` and `PlotlyResizeDriver` own browser-side sizing
`src/gu_toolkit/PlotlyPane.py` is the only place that actually knows measured browser geometry.

- `PlotlyPane._wrap` and `_host` form the widget-side host chain.
- `PlotlyResizeDriver._esm` resolves a host element, finds `.js-plotly-plot`, optionally finds a clip ancestor, measures size, writes width/height hints into the Plotly DOM, and calls Plotly resize.

This layer is the only place that can explain why the inner plot height under-fills, overflows, or ignores a container resize.

### 5. Sidebar and modal controls also affect plot geometry
The right-hand plot width is not only a Plotly concern. The available area is also shaped by:

- `FigureLayout.sidebar_container`
- `ParameterManager` adding/removing controls
- `InfoPanelManager` adding/removing info outputs
- `LegendPanelManager` visibility state
- `Slider.set_modal_host(...)`, which re-parents modal overlays into `FigureLayout.root_widget`

These are secondary, but they still create geometry-affecting state transitions worth logging.

## Non-goals
This logging project must **not** do the following:

- fix the height under-fill / overflow bug
- change `view_stage.height`, `host_box.height`, or Plotly sizing policy
- redesign the view system or replace `PlotlyPane`
- rewrite the frontend resize algorithm
- declare responsive behavior “verified” without tests or notebook validation
- use logging as a hidden fix by quietly mutating additional layout state

## Questions the logs must answer
A good logging design should make the following failure classes distinguishable.

### A. Python never requested a resize
Example symptom: sidebar visibility changed, but no explicit reflow was requested for the active pane.

### B. Python requested a resize for the wrong target
Example symptom: the active view changed, but the reflow request was sent before the visible page changed, or it referenced stale active-view state.

### C. The JS driver did not receive or process the request
Example symptom: `pane.reflow()` ran, but the frontend did not schedule a resize or the message was dropped/never correlated.

### D. The driver measured an unexpected size
Example symptom: host height was `0`, clip width was smaller than expected, or a hidden page was measured instead of the active one.

### E. The driver applied DOM size hints, but Plotly still did not resize correctly
Example symptom: `applyWidthClamp()` and `setPlotHeights()` ran, but the resulting Plotly DOM size or `_fullLayout._size` still did not match the effective host size.

### F. A debounce layer collapsed the event stream
Example symptom: many resize triggers were emitted, but only the last one executed, masking the event that actually mattered.

### G. The issue is a rendering/range problem, not a geometry problem
Example symptom: the pane sized correctly, but trace rendering or stored view ranges made it look broken.

## Recommended logging architecture

### 1. Add one small internal helper module for layout logging
Create a focused internal helper module, for example `src/gu_toolkit/layout_logging.py`, that provides three things:

1. a structured event emitter helper
2. lightweight geometry snapshot dataclasses / dict builders
3. correlation id helpers for figure/view/pane/reflow requests

The rest of the code should call that helper rather than assembling ad-hoc dictionaries in every module.

### 2. Use logger namespaces, not print statements
Recommended logger hierarchy:

| Logger name | Owner | Purpose |
|---|---|---|
| `gu_toolkit.layout` | shared | umbrella logger for all layout/responsive debugging |
| `gu_toolkit.layout.figure` | `Figure.py` | view activation, reflow requests, relayout dispatch, render correlation |
| `gu_toolkit.layout.figure_layout` | `figure_layout.py` | widget-tree and geometry-intent mutations |
| `gu_toolkit.layout.plotly_pane` | `PlotlyPane.py` | Python-side pane/driver lifecycle |
| `gu_toolkit.layout.plotly_driver` | JS frontend + Python bridge | host resolution, measurements, resize attempts, skip reasons |
| `gu_toolkit.layout.debounce` | `debouncing.py` and JS debouncer | queue length, drop-overflow, callback execution |
| `gu_toolkit.layout.slider_modal` | `Slider.py` | hosted/global modal placement and visibility |

The codebase already uses `logging` and `NullHandler` patterns. Reusing that convention keeps debugging aligned with the rest of the repository.

### 3. Emit structured events with stable field names
Every layout event should carry a flat, predictable envelope.

Suggested required fields:

| Field | Meaning |
|---|---|
| `event` | Stable event name such as `reflow_requested`, `resize_skipped`, `view_page_visibility_changed` |
| `source` | Module or layer, for example `Figure`, `FigureLayout`, `PlotlyResizeDriver` |
| `phase` | `requested`, `scheduled`, `measured`, `applied`, `skipped`, `completed`, `failed` |
| `figure_id` | Stable id for one `Figure` instance |
| `view_id` | Target view id when relevant |
| `pane_id` | Stable id for one `PlotlyPane` / resize driver pair |
| `request_id` | Correlation id for one explicit reflow request chain |
| `reason` | High-level cause such as `view_activated`, `sidebar_visibility`, `full_width_change`, `ResizeObserver:host` |
| `active_view_id` | Active view at emission time |
| `seq` | Local monotonic counter within a figure or pane |
| `outcome` | `success`, `skipped`, `no_host`, `zero_size`, `min_delta`, `error`, etc. |
| `display_state` | `flex`, `none`, `block`, etc. when helpful |
| `sizes` or flattened size fields | Rounded integer geometry values |

Recommended size fields when flattening is more log-friendly:

- `host_w`, `host_h`
- `clip_w`, `clip_h`
- `effective_w`, `effective_h`
- `plot_w`, `plot_h`
- `plot_container_w`, `plot_container_h`
- `wrapper_padding_px` where relevant

### 4. Give each figure and pane stable ids
The current architecture has stable views and stable panes, but no stable debug ids.

Add lightweight ids such as:

- `Figure._layout_debug_figure_id`
- `View.pane.debug_pane_id` or equivalent
- optional per-driver `driver_id`

The ids do not need to be public API. They only need to be stable for the lifetime of the object so that log lines can be correlated after view switches and rerenders.

### 5. Add a per-figure in-memory debug buffer
Standard logging is necessary, but it is not always sufficient for notebook debugging.

Recommended addition:

- one bounded `deque` per figure (for example last 200 or 500 layout events)
- events mirrored into both the normal logger and the in-memory buffer
- no public API commitment required yet; an internal helper or a future debugging accessor is enough

Why this matters:

- browser-forwarded events may be easier to inspect in-order from Python memory than from notebook console output
- unit tests can assert on buffered event contents without depending entirely on logging-capture formatting
- manual debugging can dump the last event window after a bad resize without reproducing from scratch

## Python-side instrumentation plan

### `Figure.py`
Instrument the following events.

| Area | Event examples | Why it matters |
|---|---|---|
| constructor | `figure_created`, `relayout_debouncer_created`, `default_view_added` | establishes figure id and baseline wiring |
| `_create_view()` | `view_runtime_created` | captures pane id, default ranges, labels, per-view widget creation |
| `add_view()` | `view_registered`, `view_page_attached`, `reflow_requested` | correlates layout page creation with later resize work |
| `set_active_view()` | `view_switch_requested`, `viewport_captured`, `active_view_changed`, `viewport_restored`, `reflow_requested` | this is one of the highest-value geometry transitions |
| `remove_view()` | `view_removed`, `active_view_after_remove`, `reflow_requested` | explains why pages disappear or orders change |
| `_sync_sidebar_visibility()` / callers | `sidebar_visibility_sync` | sidebars directly change width allocation |
| `_request_active_view_reflow()` | `reflow_requested`, `reflow_send_failed` | the primary correlation root for layout debugging |
| `_queue_relayout()` | `plotly_relayout_queued` | connects Plotly viewport changes to render decisions |
| `_dispatch_relayout()` | `plotly_relayout_dispatched`, `inactive_view_marked_stale` | explains whether relayout led to render or stale marking |
| `render()` / `_log_render()` | `render_started`, `render_completed` | useful for distinguishing geometry problems from render problems |
| `_ipython_display_()` / `show()` | `figure_displayed` | frontend geometry only exists after notebook display |

Critical requirement: `Figure._request_active_view_reflow()` must stop discarding the `reason` in the diagnostic path. Even if behavior stays the same, the logging layer needs to preserve that reason and attach a `request_id`.

### `figure_layout.py`
Instrument geometry-intent mutations rather than only value changes.

| Method | Event examples |
|---|---|
| `__init__` | `layout_initialized` |
| `update_sidebar_visibility()` | `sidebar_visibility_changed`, `sidebar_visibility_unchanged` |
| `ensure_view_page()` | `view_page_created`, `view_page_reused` |
| `attach_view_widget()` | `view_widget_attached` |
| `remove_view_page()` | `view_page_removed` |
| `set_view_order()` | `view_order_changed` |
| `set_active_view()` | `active_page_set` |
| `_apply_active_page_visibility()` | `view_page_visibility_changed` |
| `_refresh_view_selector()` | `view_selector_refreshed` |
| `_on_full_width_change()` | `full_width_layout_changed` |

The event payload should include the relevant layout traits before and after the mutation when the change is geometry-affecting.

### Secondary owners worth instrumenting lightly
These modules are not the primary layout engine, but they still create layout-affecting state:

- `figure_parameters.py`
  - first control added, control reused, modal host attachment
- `figure_info.py`
  - output/card added, view-scoped card visibility changes
- `figure_legend.py`
  - legend visible/non-visible transitions for the active view
- `Slider.py`
  - modal reparenting, hosted/global mode, modal open/close

These can stay lower priority than `Figure`, `FigureLayout`, and `PlotlyPane`, but they are worth covering because each can change the sidebar or overlay geometry.

## Frontend and JS-bridge instrumentation plan

### Why the bridge is necessary
The current frontend debug path writes only to the browser console. That is not enough for notebook-centric debugging because:

- Python-side events and JS-side events cannot be correlated in one stream
- automated tests cannot easily assert on browser console output
- notebook users often need a single place to inspect the most recent layout chain

### Required addition
Extend the `PlotlyResizeDriver` communication path so the frontend can forward structured events back to Python.

Recommended approach:

1. Keep `debug_js` as the gate for verbose browser-side instrumentation.
2. Add a second, explicit forwarding path for structured payloads.
3. Use widget custom messages to send small JSON-safe payloads back to Python.
4. Log the forwarded payload through `gu_toolkit.layout.plotly_driver` and mirror it into the per-figure debug buffer.

### Events to forward from `_esm`
Instrument the following JS-side moments:

| JS area | Event examples | Notes |
|---|---|---|
| `render()` mount | `driver_mounted`, `host_resolved`, `clip_resolved` | first chance to know DOM attachment exists |
| `setHostHidden()` | `host_hidden`, `host_revealed` | useful because deferred reveal affects visual interpretation |
| `schedule(reason)` | `resize_scheduled` | include debounce and follow-up timings |
| debouncer queue | `debounce_enqueued`, `debounce_drop_overflow`, `debounce_tick` | queue collapse is important for resize bugs |
| `doResize(reason)` start | `resize_attempt_started` | include reason, request id if any, and current visible state |
| no plot element | `resize_skipped` with `outcome=no_plot_el` | common during initial mount |
| zero or invalid size | `resize_skipped` with `outcome=zero_size` | must distinguish hidden-view zero height from unexpected zero height |
| min-delta suppression | `resize_skipped` with `outcome=min_delta` | explains “nothing happened” cases |
| before DOM mutation | `geometry_measured` | host/clip/effective/plot/container sizes |
| after width/height hints | `resize_applied_dom_hints` | confirms current code path ran |
| after Plotly resize | `plotly_resize_completed` or `plotly_resize_failed` | distinguishes DOM hinting from Plotly reaction |
| autorange path | `autorange_requested`, `autorange_completed`, `autorange_failed` | only when relevant |
| cleanup | `driver_disposed` | helps explain disappearing observers |

### Required payload discipline
The bridge should send only small, serializable values:

- integers for sizes
- booleans
- short strings
- stable ids
- optional short arrays for ranges if needed later

It should **not** forward:

- raw DOM nodes
- full computed-style dumps by default
- large HTML/className strings from every element on every event
- unbounded event spam from every observer tick

### Request correlation across Python and JS
This is the most important part of the bridge.

When Python asks for a reflow, the message sent to the driver should include at least:

- `request_id`
- `reason`
- `view_id`
- `pane_id`
- maybe `figure_id`

Then the JS driver should include that same `request_id` in:

- `resize_scheduled`
- `resize_attempt_started`
- `resize_skipped`
- `plotly_resize_completed` / `failed`

That makes it possible to trace one explicit geometry change through the full stack.

## Geometry snapshot design
Logging is much more useful if a few standard snapshot builders exist.

### Python layout snapshot
Add a helper that captures the widget-layout intent for the active figure without touching the browser DOM.

Recommended fields:

- `root_widget.layout.width`, `position`
- `content_wrapper.layout.display`, `flex_flow`, `gap`
- `left_panel.layout.flex`
- `view_selector.layout.display`
- `view_stage.layout.width`, `height`, `min_height`, `display`, `overflow`
- active `host_box.layout.width`, `height`, `display`, `overflow`
- `sidebar_container.layout.display`, `flex`, `min_width`, `max_width`, `width`, `padding`
- `pane.widget.layout.width`, `height`, `padding`, `border`, `overflow`
- `pane._host.layout.width`, `height`, `display`, `overflow`

This snapshot does **not** tell us real pixels. It tells us what Python believes the geometry contract should be.

### JS geometry snapshot
Add a frontend helper that captures measured DOM state for the active pane.

Recommended fields:

- host rect width/height
- clip rect width/height and whether clip equals host
- effective width/height
- plot rect width/height
- `.plot-container` rect width/height
- current `style.width`, `style.maxWidth`, `style.height` on plot and container
- host `display`, `overflow`, `opacity`
- optional Plotly `_fullLayout._size` if available

This snapshot should be logged on:

- first successful resize
- explicit reflow requests
- skips / failures
- maybe at `DEBUG` level after meaningful size changes

## Debounce logging plan
Two separate debouncers matter here.

### 1. Python `QueuedDebouncer`
`Figure` uses `QueuedDebouncer` for relayout, and `InfoPanelManager` also uses it for simple card updates.

Recommended additions:

- optional `name` or `owner` field for diagnostics
- queue depth at enqueue time
- whether `drop_overflow` collapsed multiple calls
- callback execution start/end events
- callback failure already logs exceptions and should keep doing so

High-value events:

- `debounce_enqueued`
- `debounce_drop_overflow`
- `debounce_tick_started`
- `debounce_tick_completed`

### 2. Frontend `createQueuedDebouncer(...)`
The JS driver currently collapses overflow silently. That silence is a problem for resize debugging.

Recommended events:

- `debounce_enqueued`
- `debounce_drop_overflow`
- `debounce_tick`
- `followup_scheduled`
- `followup_cleared`

Without these, an important resize signal can disappear with no record.

## Recommended implementation phases

### Phase 1 — Logging primitives and ids
- Add the internal layout-logging helper module.
- Add figure and pane debug ids.
- Define stable event names and payload schema.
- Add a per-figure ring buffer.

**Exit condition:** events can be emitted consistently from Python without changing behavior.

### Phase 2 — Python instrumentation
- Instrument `Figure.py` reflow, relayout, display, and view-switch paths.
- Instrument `figure_layout.py` geometry-intent mutations.
- Add light instrumentation to sidebar-affecting managers and `Slider.py` where useful.

**Exit condition:** Python-only geometry changes produce a useful causal trail.

### Phase 3 — JS forwarding and correlation
- Extend `PlotlyResizeDriver` messages to include `request_id` and `reason`.
- Forward structured frontend events back to Python.
- Log and buffer forwarded events under `gu_toolkit.layout.plotly_driver`.

**Exit condition:** one explicit `pane.reflow()` can be traced from Python request to frontend measurement/result.

### Phase 4 — Snapshot helpers and notebook workflow
- Add Python layout snapshots and JS geometry snapshots.
- Document how to enable and read layout logs during notebook debugging.
- Update the responsive manual notebook to use the new diagnostics.

**Exit condition:** a maintainer can reproduce a resize failure and inspect a coherent event window.

### Phase 5 — Tests and hardening
- Add unit tests for event emission helpers and id correlation.
- Add Python tests for reflow/logging calls and layout mutations.
- Add a minimal integration path for JS event forwarding if practical.
- Update docs and the manual notebook checklist.

**Exit condition:** logging behavior is regression-tested and documented.

## Detailed blueprint for implementation

### Logging helper responsibilities
The shared helper should provide:

- `emit_layout_event(logger, event, **fields)`
- `new_request_id()` or equivalent
- `buffer_layout_event(figure, payload)`
- optional snapshot flatteners

The helper should centralize:

- standard timestamp fields
- id normalization to strings
- consistent field naming
- optional level selection (`DEBUG` vs `INFO`)

### Preferred event naming style
Use short, stable verb-based names:

- `figure_created`
- `figure_displayed`
- `view_runtime_created`
- `view_page_created`
- `view_page_visibility_changed`
- `sidebar_visibility_changed`
- `full_width_layout_changed`
- `reflow_requested`
- `reflow_message_sent`
- `resize_scheduled`
- `resize_attempt_started`
- `geometry_measured`
- `resize_applied_dom_hints`
- `plotly_resize_completed`
- `resize_skipped`
- `render_started`
- `render_completed`

Avoid one-off names that encode the full context in the event string itself.

### Recommended log levels
- `INFO`
  - lifecycle markers that are useful in normal debugging sessions
  - view switches, explicit reflow requests, full-width toggles, sidebar visibility changes
- `DEBUG`
  - geometry snapshots, DOM measurements, debounce queue details, follow-up scheduling
- `WARNING`
  - unexpected missing active view, missing pane, unhandled driver state, suspicious zero-size conditions on visible active panes
- `ERROR`
  - failures in forwarding, resize exceptions, unexpected bridge deserialization problems

### Suspicious-versus-expected zero-size policy
Not every `0x0` measurement is a bug.

Treat as expected by default:

- inactive view pages with `display="none"`
- initial mount before Plotly DOM insertion
- transient no-host/no-plot-element cases during widget setup

Treat as suspicious and elevate to warning when all are true:

- target view is the active view
- page display state is visible (`flex`)
- the reflow was explicit rather than opportunistic
- repeated measurements continue to report zero size after follow-ups

This distinction is critical for readable logs.

## Manual debugging workflow after implementation
The intended maintainer workflow should look like this:

```python
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("gu_toolkit.layout").setLevel(logging.DEBUG)
```

Then:

1. display the figure in the notebook
2. trigger one known geometry change, for example:
   - activate another view
   - toggle full-width mode
   - add/remove sidebar content
   - resize the notebook side pane
3. find the emitted `reflow_requested` event and note its `request_id`
4. follow that `request_id` through:
   - `reflow_message_sent`
   - `resize_scheduled`
   - `geometry_measured`
   - `resize_applied_dom_hints` or `resize_skipped`
   - `plotly_resize_completed`
5. if needed, dump the last buffered layout events for the figure and compare Python intent versus JS measurements

This workflow is the main deliverable. The logging project is successful when a maintainer can answer “where did the resize chain stop?” in one debugging pass.

## Test suite for acceptance

### Unit tests
Add focused tests for:

- event helper formatting and stable field names
- request id generation and propagation
- per-figure buffer insertion and truncation behavior
- `Figure._request_active_view_reflow()` including reason/request id emission
- `FigureLayout.update_sidebar_visibility()` event emission on changed vs unchanged state
- `QueuedDebouncer` logging hooks when queue overflow is dropped
- `PlotlyPane.reflow()` payload enrichment

### Python-side integration tests
Add or update tests to verify:

- view activation emits reflow/logging in the correct order
- sidebar visibility changes log geometry-affecting state and request a reflow
- full-width toggle emits layout mutation logs and a reflow request
- removing a view updates active-view/page state and logs the resulting reflow reason

### Notebook/manual verification
Use the existing responsive notebook as the manual verification surface:

- turn on the layout logger
- perform window-width resize
- perform side-pane/container-width resize
- confirm that logs clearly distinguish host resize, clip resize, skipped attempts, and completed Plotly resize calls

### Optional future browser integration
This project does not need to solve browser automation fully, but it should prepare for it by making forwarded JS events observable from Python. That will make a future end-to-end responsive test much easier to add.

## Open questions
1. Should the per-figure event buffer remain internal, or should it become a supported debugging API later?
2. Should JS forwarding be enabled automatically when `gu_toolkit.layout.plotly_driver` is set to `DEBUG`, or should it require an explicit internal flag sync?
3. How much Plotly-specific detail should be forwarded, especially around `_fullLayout._size`, before payloads become too noisy?
4. Should layout snapshots be emitted automatically on every explicit reflow, or only on failure/suspicious conditions?
5. Is it worth giving `QueuedDebouncer` a diagnostic `name` argument globally, or should names be attached by the caller in wrapper events?

## Challenges and mitigations

### Challenge: log volume can explode under resize observers
**Mitigation:** keep geometry snapshots at `DEBUG`, round values to ints, sample only important edges, and log follow-up events only when they differ materially.

### Challenge: Python and JS clocks/orders are not identical
**Mitigation:** use stable `request_id`, `pane_id`, and local sequence counters; do not rely only on timestamps.

### Challenge: browser-only state is invisible to current unit tests
**Mitigation:** forward structured JS events into Python so tests can assert on the observable bridge rather than raw browser console output.

### Challenge: stale historical terms (`view_tabs`, `plot_container`) can send debugging down the wrong path
**Mitigation:** update the development guide and explicitly document the current page-host architecture as authoritative.

### Challenge: diagnostics can accidentally become behavior changes
**Mitigation:** keep logging paths side-effect free, avoid modifying layout during snapshot collection, and do not add “stabilizing” mutations under the guise of logging.

## TODO
- [ ] Add a small shared layout-logging helper module.
- [ ] Add stable `figure_id`, `pane_id`, and `request_id` correlation fields.
- [ ] Instrument `Figure.py` geometry-affecting flows.
- [ ] Instrument `figure_layout.py` geometry-intent mutations.
- [ ] Instrument `PlotlyPane.py` Python-side lifecycle and message sending.
- [ ] Add frontend event forwarding from `PlotlyResizeDriver._esm` back to Python.
- [ ] Add standard Python layout snapshots and JS geometry snapshots.
- [ ] Add debounce diagnostics for both Python and JS queueing layers.
- [ ] Add or update tests for event emission and request correlation.
- [ ] Update the responsive notebook and development guide to use the new diagnostics.

## Exit criteria
- [ ] A geometry-affecting action produces a correlated event trail from Python request to JS resize result.
- [ ] Logs make it obvious whether a failure is due to missing reflow, wrong target view, zero-size host, skipped resize, debounce collapse, or Plotly non-response.
- [ ] Logging remains opt-in and low overhead when disabled.
- [ ] The layout guide documents the current widget/geometry architecture and points maintainers at the right source files.
- [ ] The responsive notebook can be used as a practical manual debugging surface with the new logging enabled.
- [ ] This project improves observability without changing layout behavior or claiming the sizing bug is fixed.
