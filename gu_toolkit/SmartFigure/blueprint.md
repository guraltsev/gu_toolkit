## OUTPUT PART 1 — Technical blueprint (implementation-ready)

### Purpose

Implement **two-way synchronization** between a Plotly viewport (pan/zoom/reset) and `SmartFigure`’s viewport state, with a **debounced** (0.5s idle) recompute/resampling trigger that runs in **Pyodide/JupyterLite** (so: `asyncio`, no threads).

This blueprint follows your “single-file but extractable sections” preference via explicit section markers. 

---

## 1) State model and invariants

### 1.1 Canonical state (in `SmartFigure`)

Maintain four ranges:

* **Live** (changes from UI *and* code):

  * `SmartFigure._x_range`, `SmartFigure._y_range`
* **Home / Default** (baseline for reset; changes from code, not from UI):

  * `SmartFigure._x_range_default`, `SmartFigure._y_range_default`

#### Semantics

* On first creation: `live == default`.
* Programmatic update (`fig.x_range = ...`, `fig.y_range = ...`):

  * update **live** and **default** (new home).
* User pan/zoom via Plotly:

  * update **live only**; default stays unchanged.

### 1.2 Range type + validation

Use a narrow internal type alias:

```python
Range2 = tuple[float, float]  # always (lo, hi), finite, lo < hi
```

Provide an internal helper:

* `_normalize_range(obj) -> Range2`:

  * coerce to floats
  * reject NaN/inf
  * enforce lo < hi
  * raise `TypeError` / `ValueError` with actionable messages

This keeps “Plotly delta parsing” (messy, `Any`) isolated from the core invariants (per your style guide). 

---

## 2) Plotly integration layer (adapter)

### 2.1 Underlying Plotly object

Assume `SmartFigure` uses a Plotly `FigureWidget` (or equivalent widget-backed figure). The integration must support:

* **Push**: `SmartFigure` state → Plotly layout ranges
* **Pull**: Plotly relayout events → `SmartFigure` live ranges

### 2.2 Preserve UI zoom while updating data

Use a stable `layout.uirevision` strategy:

* Set `layout.uirevision` to a stable constant (e.g., `"smartfigure-uirev-1"`).
* Do **not** change it on normal data updates, so UI pan/zoom stays put when traces update.
* For explicit reset to home, directly set axis ranges (don’t rely on Plotly’s internal initial-state reset).

### 2.3 Modebar buttons

Remove autoscale from the modebar:

* Prefer Plotly config: remove `"autoScale2d"` (and optionally `"zoomIn2d"/"zoomOut2d"` only if you later decide; currently only autoscale is requested).
* Keep “reset axes” but override its effect (see §4.3).

Implementation note: where config lives depends on how you display the widget. The blueprint assumes `SmartFigure.show(..., config=...)` or a stored `_plotly_config` passed at render time.

---

## 3) Relayout listener and delta parsing

### 3.1 Relayout event source

Attach a relayout listener once when the widget is constructed:

* `fig.on_relayout(handler)` if available (preferred)
* otherwise an equivalent “layout delta” observation channel

### 3.2 Delta parsing

Relayout deltas commonly include keys like:

* `"xaxis.range[0]"`, `"xaxis.range[1]"`
* `"yaxis.range[0]"`, `"yaxis.range[1]"`
* `"xaxis.autorange"`, `"yaxis.autorange"` (often emitted by “reset axes”)

Implement:

* `_parse_relayout_delta(delta: Mapping[str, object]) -> ViewportDelta`

  * Extract any axis range endpoints present
  * Detect reset intent: `autorange is True` (either axis)
  * Return a structured delta object

Keep this parsing in the Plotly adapter boundary; accept `object/Any` internally, but do not leak into public signatures. 

---

## 4) Two-way sync mechanics (with loop prevention)

### 4.1 The key problem

If you update Plotly programmatically (to reflect a new `SmartFigure` range), Plotly may emit a relayout event, which could recursively update `SmartFigure`, etc.

### 4.2 Guard strategy

Add an internal reentrancy guard:

* `self._viewport_sync_guard_depth: int`
* context manager `with self._viewport_sync_guard(): ...`
* If guard depth > 0, relayout handler should **ignore** (or record stats and ignore).

This guard must be used around any “push to plotly” operation.

### 4.3 Reset axes override (home restore)

When a relayout delta indicates reset intent (typically `autorange=True`):

1. Compute home ranges = `(_x_range_default, _y_range_default)`
2. Set live ranges to home (state update)
3. Push home ranges to Plotly layout (`autorange=False`, explicit ranges)

This ensures “reset axes” goes to **home**, not to Plotly’s idea of “initial.” (And you can remove autoscale so users don’t accidentally use it.)

---

## 5) Debounced recompute/resample policy

### 5.1 Trigger rule

Viewport changes from Plotly UI should:

* Update live ranges immediately
* Schedule recompute/resample **after 0.5s idle** (debounce)

Treat y-range the same way as x-range for sync + debounce scheduling.

### 5.2 Debouncer design (Pyodide-safe)

Use `asyncio` tasks, no threads.

Provide an internal debouncer object with:

* `request(reason: str, viewport: ViewportSnapshot) -> None`
* `flush() -> None`  *(for deterministic tests and for “apply now”)*
* cancels previous pending task on new request
* stores latest requested viewport snapshot

### 5.3 “Recompute only when necessary to increase precision”

Interpret this in a correctness+precision way:

Recompute/resample for a trace if **either**:

1. **Coverage insufficient**: current sampled x-domain does not cover the new live `x_range` (pan/zoom outside sampled domain).
2. **Resolution insufficient**: current sampling density is too coarse for the current live `x_range` (zoom in).

Do **not** recompute when:

* zooming out/panning inside fully covered domain *and* resolution remains sufficient.

Implementation specifics depend on your existing sampling model, but the adapter contract should be:

* Each plotted object (trace/function) can expose:

  * `sample_domain: Range2`
  * `sample_dx` or `sample_n`
  * `supports_resample: bool`
* And a method:

  * `ensure_samples_for(viewport: ViewportSnapshot) -> bool` returning whether it actually recomputed.

### 5.4 Skip work for invisible traces (optional but recommended)

If a trace is hidden (including “legend-only” style), skip recompute. (This matches your performance direction and aligns with Plotly’s `visible` semantics.)

---

## 6) Debug hooks and stats (for your workflow and for notebook tests)

Add internal-but-stable debug hooks to support deterministic notebook validation (and to help you inspect behavior quickly):

* `SmartFigure._debug_apply_plotly_relayout(delta: dict[str, object]) -> None`

  * calls the real relayout handler
* `SmartFigure._debug_flush_viewport_debounce() -> None`

  * calls debouncer.flush()
* `SmartFigure._debug_viewport_sync_stats() -> dict[str, object]`

  * returns counters and last-seen values:

    * `relayout_events_seen`
    * `relayout_events_ignored_guard`
    * `recompute_requests`
    * `recompute_runs`
    * `last_recompute_reason`
    * `last_recompute_viewport`

This matches your testing-notebook expectations: short cells, assert-heavy, informative success prints. 

---

## 7) Interaction with `SmartParameters` (important constraint)

If you reuse your reactive-callback machinery anywhere in this pipeline:

* Callbacks must accept `**kwargs` (forward compatible). 
* Notifications already pass `owner_token` and `what_changed` through `_notify`, so you can use tokens to avoid feedback loops in parameter-driven updates. 
* **Do not** construct `CallbackToken()` without a token string; use the existing token-creation path (`register_callback` or `_new_token()`). 

(You don’t need `SmartParameters` for viewport ranges unless you want “viewport changes are parameters”; the above is here to keep the integration safe if you do.)

---

## 8) Code placement and file layout

To avoid file proliferation, implement the sync logic inside the existing `SmartFigure.py` with extractable section markers. 

Suggested sections:

* `# === SECTION: Viewport types & invariants [id: viewport-types] ===`
* `# === SECTION: Plotly viewport adapter [id: plotly-viewport-adapter] ===`
* `# === SECTION: Debouncer (asyncio) [id: viewport-debouncer] ===`
* `# === SECTION: Recompute policy glue [id: viewport-recompute-policy] ===`
* `# === SECTION: Debug hooks & stats [id: viewport-debug] ===`

---

# OUTPUT PART 2 — Staged implementation plan

Below, each stage yields a working, usable `SmartFigure` (with increasing feature completeness).

---

## Stage 1 — Implement viewport state model (live vs home)

### Description and instructions

Add internal state + normalization helpers and ensure programmatic updates follow the “live+home” rule.

Key tasks:

* Add `_x_range`, `_y_range`, `_x_range_default`, `_y_range_default` initialization (`live==home` on construction).
* Modify `x_range` / `y_range` setters to:

  * normalize
  * update live
  * update default (home)
  * call `_push_viewport_to_plotly(...)` if the plotly figure exists.

Snippet (conceptual):

```python
def _set_x_range(self, r: Range2, *, update_home: bool) -> None:
    self._x_range = r
    if update_home:
        self._x_range_default = r
```

### Functional requirements

* `fig.x_range` and `fig.x_range_default` exist and match initially.
* Setting `fig.x_range = ...` updates both `x_range` and `x_range_default`.
* Same for y.

### Regression requirements

* Existing plotting, sliders, and callbacks still work.
* No new dependencies.

### Completeness criteria

* Unit-level checks (or notebook cells) show correct semantics for initial + programmatic updates.

---

## Stage 2 — Push viewport state to Plotly without clobbering UI state

### Description and instructions

Implement `_push_viewport_to_plotly(live_ranges)` plus `uirevision` setup.

Key tasks:

* Set Plotly axis ranges from `SmartFigure._x_range/_y_range`.
* Set `layout.uirevision` to stable value.
* Store a config that removes autoscale from modebar.

Snippet (conceptual):

```python
self._plotly_layout.uirevision = "smartfigure-uirev-1"
# on display: config={"modeBarButtonsToRemove": ["autoScale2d"]}
```

### Functional requirements

* Programmatic `x_range/y_range` updates are reflected in Plotly.
* Data updates do not reset user zoom/pan.

### Regression requirements

* Updating data/traces doesn’t revert the viewport.
* Existing modebar buttons remain, except autoscale.

### Completeness criteria

* In Jupyter, changing `fig.x_range` updates axes immediately.
* Pan/zoom stays after trace data refresh.

---

## Stage 3 — Relayout listener: Plotly → SmartFigure live ranges (+ reset override)

### Description and instructions

Attach relayout handler and implement robust delta parsing + loop prevention.

Key tasks:

* Install a relayout handler on the widget.
* Parse x/y range changes and update **live only**.
* Detect reset intent (`autorange=True`) and snap back to **home**.
* Add guard around push-to-plotly.

Add debug hook:

* `_debug_apply_plotly_relayout(delta)` calling the handler directly.

### Functional requirements

* User pan/zoom updates `fig.x_range/fig.y_range` but not defaults.
* “Reset axes” restores home ranges.

### Regression requirements

* No infinite recursion (guard works).
* Plotly doesn’t end up in autorange state after reset override.

### Completeness criteria

* Notebook tests can simulate relayout deltas and observe state updates.
* Manual pan/zoom works and `SmartFigure` state follows.

---

## Stage 4 — Debounced recompute trigger (0.5s idle) + flush hook

### Description and instructions

Add `asyncio`-based debouncer and connect it to the relayout handler.

Key tasks:

* Implement debouncer with `request()` and `flush()`.
* On UI relayout, schedule recompute via debouncer (0.5s).
* Add debug hooks + stats:

  * `_debug_flush_viewport_debounce()`
  * `_debug_viewport_sync_stats()`

Recompute entrypoint should be a single internal method:

* `_on_viewport_idle_recompute(viewport_snapshot, reason)`

### Functional requirements

* Relayout causes recompute requests, but recompute runs only after idle.
* `flush()` forces immediate recompute for testing.

### Regression requirements

* No threads; works in Pyodide/JupyterLite.
* Recompute still works when called from non-async contexts.

### Completeness criteria

* Stats counters show: requests increment immediately, runs increment on flush/idle.

---

## Stage 5 — “Recompute only when necessary” decision logic

### Description and instructions

Implement the resample decision so recompute runs only when needed.

Key tasks:

* For each visible trace/function:

  * check coverage and resolution against viewport
  * recompute only if needed
* Skip recompute for invisible traces (recommended).

### Functional requirements

* Zooming in triggers recompute (after debounce).
* Panning within covered domain does not.
* Panning outside sampled domain triggers recompute.

### Regression requirements

* No extra recompute storms during normal interaction.
* Visibility doesn’t get clobbered by recompute (retain Plotly trace visibility states).

### Completeness criteria

* Notebook tests show recompute runs only in “needs” cases (using simple synthetic functions with known sampling metadata).

