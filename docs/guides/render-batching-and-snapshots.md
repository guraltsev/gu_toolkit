# Render batching and parameter snapshots

This guide describes the figure render pipeline introduced for the 60 Hz render
batching work.

## Goals

The render path now separates **requesting** a render from **executing** one:

- `Figure.render(..., force=False)` queues a render request.
- queued requests are coalesced so bursts of updates collapse into one actual
  render that observes one consistent parameter state,
- `Figure.render(..., force=True)` flushes the newest pending request
  synchronously,
- every actual render still recomputes all plots.

This keeps the public API simple while removing the old “render immediately on
 every trigger” behavior that caused repeated sampling and repeated widget
 updates during slider drags or other bursty interactions.

## Request coalescing model

`gu_toolkit.figure_render_scheduler.FigureRenderScheduler` owns the render
 request queue. The scheduler tracks:

- the latest request `reason`,
- the latest request `trigger`,
- whether any merged request represented a parameter change,
- the latest parameter-change trigger payload,
- how many requests were coalesced.

This preserves useful observability while ensuring only one actual render runs
for a burst of queued requests.

## Why snapshots are used during rendering

The plot layer now keeps two stable numeric bindings per plot:

- a **live** binding used for direct inspection through
  `plot.numeric_expression`, and
- a **render** binding that reads from the figure’s reusable render snapshot
  provider.

Before a real render starts, the figure refreshes the snapshot provider once.
All plots rendered in that pass then evaluate against that same frozen view of
parameter values. This prevents mid-render drift and avoids recreating bound
`NumericFunction` wrappers on every frame.

## Name-authoritative parameter keys

Parameter snapshots and render contexts are now **name-authoritative**:

- iteration yields parameter names such as `"a"`,
- lookup still accepts either `"a"` or `sp.Symbol("a")`, and
- same-name symbols collapse to one logical parameter entry.

This matters for render batching because the reusable render snapshot provider
now stores one value per parameter name. A render pass therefore sees one
consistent value for every logical parameter even when multiple SymPy symbols
with different assumptions share the same name.

When plots bind `NumericFunction` instances dynamically, those bindings also
resolve parameter state through the canonical name first.

## Compilation and numeric-function reuse

The symbolic-to-numeric compilation path is unchanged:

- plot functions are still compiled through `numpify_cached`,
- the compiled base `NumericFunction` stays cached,
- render-time work reuses pre-bound numeric expressions instead of rebuilding
  them.

That means the hot render loop performs sampling and trace updates, but it does
not repeatedly recompile symbolic expressions and it does not repeatedly create
new bound numeric-function wrappers.

## JupyterLab and JupyterLite considerations

The batching work deliberately reuses the existing debouncer abstraction rather
than introducing new threading-only behavior. `QueuedDebouncer` already prefers
`asyncio.get_running_loop()` / `loop.call_later(...)` when an event loop is
available, and only falls back to `threading.Timer` otherwise. Because the new
render scheduler is layered on top of that abstraction, it keeps the same
runtime portability characteristics as the rest of the toolkit.

## Testing strategy

The repository now includes dedicated coverage for:

- scheduler-level request coalescing,
- forced synchronous flushes,
- coalesced parameter-change bursts,
- stable `plot.numeric_expression` identity,
- render-snapshot consistency,
- “no recompilation during render” behavior.

Use these tests as the contract for future render-pipeline changes.
