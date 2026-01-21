# SmartFigure.py — Weak Points Handoff (for follow-up work)

Date: 2026-01-19  
Scope: This document summarizes **weak points / risks** in the current `SmartFigure.py` implementation and recommends **high‑leverage fixes**. It is written as a handoff to a developer who will patch/refactor the file.

---

## Executive summary (what to fix first)

### P0 — Correctness / crashers (must fix)
1. **`SmartPlot.set_func(..., parameters=None)` can crash** due to `list(self._parameters)` when `_parameters` is `None`.
2. **`sampling_points="figure_default"` can crash on first plot creation** (works in `.update(...)` but not in `SmartPlot.__init__` / setter).

### P1 — API hazards / surprising behavior
3. **Hooks run immediately on registration**, with an empty change dict and possibly `fig=None`; failures are downgraded to warnings (easy to miss).
4. **Missing parameters silently evaluate to `0.0`**, masking user errors and producing plausible-but-wrong plots/results.
5. **Hook ordering is implicit**: on slider change, `render()` happens first, then hooks. This may or may not match expected “compute derived values before rendering”.

### P1/P2 — Performance, robustness, maintainability
6. **JS injection uses a global `MutationObserver` over `document.body`** + per-plot `ResizeObserver`. This can cause performance surprises in large notebooks and is difficult to tear down.
7. **Plot evaluation is not numerically defensive**: no handling for exceptions, NaN/inf, complex outputs, or discontinuities; one bad evaluation can break the display.
8. **Type/API inconsistencies** around `"figure_default"` and accepted `sampling_points` types.
9. **Error reporting relies on `warnings.warn`**, which often hides stack traces and makes debugging harder.

---

## Findings in detail

### P0.1 — `SmartPlot.set_func(parameters=None)` crash

**Where it happens**
- `SmartPlot.set_func` stores `self._parameters = None` when `parameters is None`, then computes:
  - `args = [self._var] + (list(self._parameters) or [])`

**Why this is a bug**
- `list(None)` raises `TypeError: 'NoneType' object is not iterable`.
- The `or []` does *not* help because Python must evaluate `list(self._parameters)` first.

**User-visible symptom**
- Any call path that ends up invoking `SmartPlot.set_func(..., None)` can crash immediately.
- This is especially likely because `parameters` is typed optional and defaults to `None`.

**Minimal reproduction**
```python
import sympy as sp
x = sp.Symbol("x")
# If SmartPlot is reachable directly:
p = SmartPlot(var=x, func=sp.sin(x), smart_figure=fig, parameters=None)  # can crash
# Or any code path that calls set_func(..., parameters=None).
```

**Recommended fix (minimal)**
- Normalize `parameters` to an empty tuple instead of `None`:
  - `self._parameters = tuple(parameters) if parameters is not None else ()`
- Then set:
  - `args = [self._var] + list(self._parameters)`

**Recommended test**
- Ensure `SmartPlot(..., parameters=None)` works and creates a callable with signature `(x,)`.

---

### P0.2 — `"figure_default"` sampling points works in updates but can crash at creation

**Where it happens**
- `SmartFigure.plot(..., sampling_points: Optional[Union[int, str]] = None)` advertises string values.
- `SmartPlot.__init__` does:
  - `self.sampling_points = sampling_points`
- `SmartPlot.sampling_points` setter does:
  - `self._sampling_points = int(InputConvert(value, int)) if value is not None else None`

**Why this is a bug**
- If `sampling_points` is `"figure_default"` (supported elsewhere), the setter tries to `int(InputConvert("figure_default", int))`, which is expected to fail.
- The `.update(...)` path special-cases `"figure_default"` (sets `None`), but construction does not.

**User-visible symptom**
- `fig.plot(..., sampling_points="figure_default")` fails on first creation but may work on later updates of an existing plot.

**Recommended fix (minimal)**
- Treat `"figure_default"` in the setter (or normalize in `__init__`), same as the `.update(...)` path:
  - if value is `"figure_default"`: store `None`

**Recommended test**
- Fresh plot creation works with `sampling_points="figure_default"`.
- Updating existing plot continues to work.

---

## API hazards / surprising behavior

### P1.1 — Hooks run immediately on registration (and errors are easy to miss)

**Current behavior**
- `ParameterManager.add_hook(...)` stores the callback and then *immediately* invokes:
  - `callback({}, fig)`
- Exceptions are caught and converted into `warnings.warn(...)`.

**Why this is risky**
- Surprising side effects: registration triggers execution.
- Hook authors may assume `change` contains keys (e.g. `'name'`, `'new'`)—but init uses `{}`.
- `fig` is optional, defaulting to `None`; a user can call `add_hook(cb)` and the first call will pass `fig=None`, likely breaking.
- `warnings.warn` typically does not include a full stack trace, so failures are “quiet”.

**Recommended fix options**
- **Option A (cleanest):** stop running hooks on registration.
  - Provide explicit initialization by user code: call the hook once manually if they want.
- **Option B (still auto-init):** only run immediately if `fig is not None`, and pass a sentinel change object:
  - e.g. `{"event": "init"}` instead of `{}`.
- Replace `warnings.warn` with `logger.exception(...)` (or re-raise when `debug=True`).

**Recommended tests**
- Hook registration does not crash when `fig` is omitted.
- Hook failures are visible in logs when debugging is enabled.

---

### P1.2 — Missing parameter values silently become `0.0`

**Current behavior**
- `ParameterManager.get_value(symbol)` returns `0.0` if the slider doesn't exist.

**Why this is risky**
- It masks mistakes:
  - A misspelled symbol or missing slider yields a “reasonable” output that is silently wrong.
- It makes debugging hard: user sees a curve, but it is not parameterized as expected.

**Recommended fix**
- Prefer failing loudly by default:
  - Raise `KeyError` if `symbol` is not present.
- If backwards-compatibility matters, consider:
  - `get_value(..., default=_MISSING)` where default must be explicit, or
  - return `0.0` only when `debug=False` but log a warning once.

---

### P1.3 — Hook ordering is implicit (render first, hooks second)

**Current behavior**
- On slider change: `ParameterManager` calls `render_callback("param_change", change)`.
- `SmartFigure.render(...)` renders plots first, then runs hooks when `reason == "param_change"`.

**Why this matters**
- Many hooks are “derived values” about the current plots. Some want:
  - render → hook (current behavior)
- Others want:
  - hook → render (e.g. a hook that changes parameters or plot definitions before rendering)
- This ordering should be explicit and documented, or configurable.

**Recommended fix**
- Document the contract clearly:
  - hook timing, change payload, guarantee that all plots are rendered before hooks, etc.
- If needed, split into phases:
  - `pre_render_hooks` and `post_render_hooks` (or a single hook registry with an enum/flag).

---

## Performance and robustness

### P1.4 — Global MutationObserver + ResizeObserver: potential notebook-wide overhead

**Current behavior**
- JS is injected once globally, installs:
  - `MutationObserver` on `document.body` watching subtree changes.
  - `ResizeObserver` for each `.js-plotly-plot`.

**Risks**
- In notebooks with many widgets and frequent DOM changes, `MutationObserver` callbacks can run often.
- Hard to deactivate / teardown in long kernel sessions.
- Can cause “mysterious sluggishness” that users blame on the plotting layer.

**Recommended fixes**
- Avoid observing the whole document; scope to the widget root if possible.
- Reduce scanning work in `attachAll()` (e.g., incremental attachment only).
- Provide a kill switch for advanced users (disable JS injection).

---

### P1.5 — Plot evaluation is not numerically defensive

**Current behavior**
- `y_values = np.asarray(self._f_numpy(*args))` is executed with no protection.

**Risks**
- Exceptions in evaluation crash render.
- NaN/inf produce ugly graphs; complex values may crash plotly or show nonsense.
- Discontinuities (e.g., `tan(x)`) look like vertical lines unless masked.

**Recommended fixes**
- Wrap evaluation in try/except; on failure:
  - keep previous trace data, and optionally log a warning / show info output.
- Mask non-finite values:
  - `y = np.where(np.isfinite(y), y, np.nan)`
- Consider handling complex:
  - either take `np.real` with a warning, or raise.

---

## Maintainability / consistency

### P2.1 — Type/API inconsistencies for `sampling_points`
- `SmartFigure.plot` allows `Optional[Union[int, str]]`.
- `SmartPlot.sampling_points` setter type is `Optional[int]` (but accepts `InputConvert` of arbitrary).
- There is a special string `"figure_default"` that is only handled in some paths.

**Recommended fix**
- Make the accepted type explicit everywhere:
  - e.g. `SamplingSpec = Optional[Union[int, Literal["figure_default"]]]`
- Centralize normalization: one helper or one place (e.g. in setters).

---

### P2.2 — Error reporting via `warnings.warn` loses stack traces
- Used for hook init failure and hook runtime failure.

**Recommended fix**
- Use `logging` (already present) with `logger.exception(...)` on errors.
- For teaching notebooks, consider:
  - `debug=True` → re-raise (fail fast)
  - default → log at WARNING/ERROR

---

## Suggested patch checklist (high leverage, low risk)

1. **Normalize `parameters` to empty tuple** in `SmartPlot.set_func`.
2. **Normalize `sampling_points`** to treat `"figure_default"` as `None` in *all* entry points (constructor + setter + update).
3. **Hook registration behavior**:
   - either remove auto-run, or require `fig`, or pass an explicit init event.
4. **Stop silently returning `0.0`** for missing parameter values (raise or warn+log).
5. Add minimal **render robustness** (try/except, non-finite masking).
6. Review **JS observers** for scope and teardown, or provide an opt-out.

---

## Quick regression notebook cells (recommended)

1) Parameters None:
```python
import sympy as sp
x = sp.Symbol("x")
fig = SmartFigure()
fig.plot(x, sp.sin(x), parameters=[])      # should work
fig.plot(x, sp.sin(x), parameters=None)    # should work and behave like autodetect or empty (choose contract)
```

2) figure_default sampling:
```python
fig = SmartFigure()
fig.plot(x, sp.sin(x), id="s", sampling_points="figure_default")  # should not crash
```

3) Hook behavior:
```python
out = fig.get_info_output("hook_test")
def cb(change, fig):
    with out:
        print("hook called", change.keys(), fig is not None)

fig.params.add_hook(cb)  # confirm behavior + no warning surprises
```

4) Non-finite:
```python
fig.plot(x, 1/(x-0.1), id="sing")  # should not crash; should handle inf/nan cleanly
```

---

End of handoff.
