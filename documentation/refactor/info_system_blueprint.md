# Blueprint: Simplified Info Cards via `Figure.info(spec, id=...)`

## 1. Current source constraints to respect

- The Info sidebar is a `VBox` of `ipywidgets.Output` widgets managed by `InfoPanelManager.get_output(...)`.
- `Figure.render(reason, trigger)` is the centralized render point; relayout events call `render(reason="relayout")` via a `QueuedDebouncer` configured at 500ms.
- Parameter-change hooks currently run after plots render, only for `reason == "param_change"`.

Implication: The safest integration point for “update on all three reasons” is at the end of `Figure.render(...)`.

---

## 2. Public API

### 2.1 Signature
Add:

- `Figure.info(spec, id="text") -> None`

### 2.2 Semantics
- `id` is the info-card identifier.
- If `id` already exists, **replace** that card’s configured segments and UI.
- If `id` does not exist, create a new output via `InfoPanelManager.get_output(id)` and add it to the sidebar (existing ordering behavior).

---

## 3. Internal model

### 3.1 Change context
Define a lightweight object passed to callables:

`InfoChangeContext`
- `reason: str`  (one of `"manual" | "param_change" | "relayout" | ..."`; keep open)
- `trigger: Any | None` (e.g., ParamEvent or None)
- `t: float`  (time.time() when queued; optional)
- `seq: int`  (monotone counter; optional, helpful for debugging)

This satisfies “something describing the reason for the change” while remaining extensible.

### 3.2 Segment types
Each card stores an ordered list of segments:

- `StaticSegment(text: str, widget)`
- `DynamicSegment(fn: callable, widget, last_text: str | None)`

Where `widget` is chosen to support HTML + LaTeX (see §6).

### 3.3 Card state
Store per-card state in `InfoPanelManager`, e.g.

`self._simple_cards: Dict[Hashable, SimpleInfoCard]`

`SimpleInfoCard` contains:
- `id: Hashable`
- `output: widgets.Output`
- `container: widgets.Box` (e.g. VBox) holding per-segment widgets
- `segments: list[Segment]`
- `debouncer: QueuedDebouncer` (30Hz)
- `pending_ctx: InfoChangeContext | None`

---

## 4. Parsing and configuration

### 4.1 Normalize spec
Normalize `spec` to a list:
- `str` → `[str]`
- `callable` → `[callable]`
- `Sequence[...]` → validate each element is `str` or callable

Reject anything else with a clear `TypeError`.

### 4.2 Replace vs create
On `fig.info(spec, id=...)`:

- if card exists:
  - clear its output/container content
  - rebuild segments & segment widgets
  - preserve the same `Output` widget instance (keeps sidebar placement stable)
- else:
  - `out = InfoPanelManager.get_output(id)`
  - create container + segments and display into `out`
  - register card state under that id

---

## 5. Update scheduling and throttling

### 5.1 Debouncer
For each card create:

`QueuedDebouncer(card._run_update, execute_every_ms=33, drop_overflow=True)`

Contract:
- “queued calls”
- “last call wins”
- last call is guaranteed to execute
- upper bound frequency ~30Hz

### 5.2 Trigger points (recommended)
At the **end of `Figure.render(reason, trigger)`**:
- build `ctx = InfoChangeContext(reason=reason, trigger=trigger, ...)`
- tell the info manager to `schedule_info_update(ctx)` which:
  - records `pending_ctx = ctx` (overwrite)
  - calls each card’s debouncer (or one shared manager-level debouncer)

This covers all three reasons using a single integration point.

### 5.3 Optional enhancement (only if needed later)
If you want smooth relayout-only info updates without paying for full re-render:
- also schedule from `_throttled_relayout(...)` directly (still 30Hz debounced),
- but be explicit that dynamic info callables must not assume plots were re-rendered for that relayout event.

Do not do this unless you observe a real need.

---

## 6. HTML + LaTeX rendering (decision procedure)

You must reuse whatever currently makes `Figure.title` support “HTML/LaTeX is allowed.”

Since `FigureLayout` is not in the provided files, the correct choice is determined by inspection:

### 6.1 Inspect existing title rendering
Open `figure_layout.py` and locate `FigureLayout.set_title(...)` and any helper it uses.

There are three common patterns:

**Pattern A: `widgets.HTMLMath`**
- Title uses `widgets.HTMLMath(value=...)`.
- Then for info segments use the same widget class for each segment.
- Set `.value = html_string` to update dynamic segments.

**Pattern B: `widgets.HTML` + explicit typeset hook**
- Title uses `widgets.HTML(value=...)` and then calls a JS/py typeset helper (e.g. `typeset_math(widget)`).
- For info segments, use `widgets.HTML` and call the same typeset helper after updating `.value`.
- Ensure typeset is only called when the segment text changes.

**Pattern C: custom DOM injection / template**
- Title is rendered via a custom widget/template that already handles MathJax.
- For info segments, implement a small wrapper in `FigureLayout` such as:
  - `FigureLayout.make_rich_text_widget(initial_value: str) -> widgets.DOMWidget`
  - `FigureLayout.set_rich_text(widget, value: str) -> None`
so that info rendering stays consistent with title rendering.

### 6.2 Required properties
Whatever widget you choose must satisfy:
- HTML tags are interpreted (so `<code>` renders)
- LaTeX is typeset
- updates are cheap (avoid re-typesetting static segments)

---

## 7. Caching and no-op optimization

### 7.1 Static segments
- Build once at configuration time.
- Never updated during `schedule_info_update`.

### 7.2 Dynamic segments
On update:
1. `new_text = fn(fig, ctx)`
2. if `new_text == last_text`: return (no DOM update, no typeset)
3. else:
   - set widget content
   - typeset if needed by the chosen mechanism
   - store `last_text = new_text`

---

## 8. Error handling (in-place, constrained)

When a callable raises:
- catch exception and create a short error payload:
  - exception type + message
  - optionally first N lines of traceback (recommend N=15–25)
- escape text (`&`, `<`, `>`) before embedding into HTML
- render as:

`<pre style="max-height: 12em; overflow:auto; white-space: pre-wrap; margin:0;">...</pre>`

This keeps the card bounded and avoids massive notebook layout shifts.

---

## 9. Compatibility considerations

- Keep `Figure.get_info_output(...)` and `Figure.add_info_component(...)` unchanged.
- New simplified cards coexist with legacy outputs.
- If desired, later you can provide a migration guide to replace legacy components with `fig.info(...)`.

---

## 10. Minimal manual test matrix

1. `fig.info("$x^2$")` renders LaTeX and never re-typesets on slider drags.
2. `fig.info(lambda fig, ctx: f"<code>{fig.x_range}</code>")` updates on:
   - manual render
   - slider drags (throttled to ≤30Hz)
   - relayout renders (subject to upstream 500ms relayout debounce)
3. Mixed: `fig.info(["Fixed $f$", fn, "Fixed $g$", fn2])` with only dynamic segments changing.
4. Exception: dynamic fn raises; verify bounded error display and no runaway growth.

