# Simplified `fig.info(...)` System (Summary)

## User-facing API

Add a single high-level API for the Info sidebar:

- `fig.info(spec, id="text")`

where `spec` is one of:
- `str`
- `callable`
- `Sequence[Union[str, callable]]`

Semantics:
- `id="info0"`,`id="info1"` etc is the automatic auto-incrementing info card id. Implement a system that avoids collisions. 
- If the card **already exists**, calling `fig.info(..., id=<existing>)` **replaces** that card’s content.
- If the card **does not exist**, a **new card** is created in the Info sidebar under that id.

### Callable spec
Each callable must accept:

- `(fig, change_context)` and return `str`.

The returned string may include:
- LaTeX (e.g. `$...$`, `\(...\)`, `\[...\]`, `$$...$$`)
- HTML tags (e.g. `<code>2.70</code>`)

## Display behavior

Each card is rendered as an ordered list of **segments**:

- **Static segment**: created from a `str` in the spec. Rendered once and never re-rendered during updates.
- **Dynamic segment**: created from a callable in the spec. Evaluated on updates; its displayed string is replaced if changed.

Rendering requirements:
- HTML tags are interpreted as HTML (not escaped).
- LaTeX in strings is typeset (MathJax).

## Update triggers and throttling

Dynamic segments update on all three reasons:
- `reason="param_change"`
- `reason="relayout"`
- `reason="manual"`

Updates are debounced using the same queuing semantics as render debouncing (“last call wins, last call guaranteed to execute”), and must not run more often than once 30ms.

Practical implication given current source:
- relayout renders are already debounced at 500ms upstream, so relayout-driven info updates will effectively occur ≤ 2Hz unless you also schedule directly from relayout events.

## Error handling

If a dynamic callable raises, that segment displays an **in-place error** instead of its normal output:
- constrained height/width (avoid giant tracebacks)
- scrollable
- escaped text inside `<pre>...</pre>` (do not allow traceback HTML injection)

## Best course of action (architecture)

1. Implement the feature as a small extension to `InfoPanelManager` (it already owns info outputs and sidebar ordering).
2. Expose `Figure.info(...)` as a thin wrapper delegating into the info manager and updating sidebar visibility.
3. Trigger updates from `Figure.render(...)` (covers manual/param_change/relayout in one place) using a new per-card 30Hz `QueuedDebouncer`.
4. Reuse the *existing* “HTML/LaTeX supported” rendering approach already used for `Figure.title` via `FigureLayout.set_title`. Do not invent a new typesetting mechanism; mirror the one that already works in this codebase.
5. Expose `info` as a global module level function that references the current active figure. 

