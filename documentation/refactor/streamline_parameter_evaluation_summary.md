# Streamline Parameter Evaluation — Summary Plan

## Motivation

Today, `numpify` returns a bare callable with no metadata attached beyond a
docstring and `_generated_source`.  The sympy expression, argument names, and
argument ordering are lost once compilation finishes.  Any code that wants to
bind parameter values (sliders, snapshots, dicts) must independently track that
information — and does so inside `SmartPlot` and `NumericExpression` wrappers.

The goal is to make the **output of `numpify` self-describing and
self-sufficient** so that parameter binding, introspection, and figure-aware
evaluation can happen at the function level, without requiring a `SmartPlot`
intermediary.

## High-Level Changes

### 1. Introduce `NumpifiedFunction` — a rich callable wrapper

`numpify` (and `numpify_cached`) will return a `NumpifiedFunction` instance
instead of a bare `def _generated(...)`.  This object:

| Attribute / Method | Purpose |
|-|-|
| `__call__(*args)` | Same positional-arg evaluation as today |
| `.expr` | Original sympy expression (post-expansion) |
| `.args` | Ordered tuple of `sympy.Symbol` — the argument names/order |
| `.source` | Generated Python source (currently `_generated_source`) |
| `.bind(values)` | Partial-apply a `dict[Symbol, scalar]`, `ParameterSnapshot`, or `SmartFigure` / `None` (current figure) — returns a `BoundNumpifiedFunction` |

### 2. `BoundNumpifiedFunction` — a callable with frozen or live values

Returned by `.bind(...)`.  Two binding modes:

| Mode | Input to `.bind()` | Behaviour |
|-|-|-|
| **Dead (snapshot)** | `dict[Symbol, value]` or `ParameterSnapshot` | Captures scalar values; fully evaluable with remaining free args only |
| **Live (figure)** | `SmartFigure` instance or `None` (current figure from context stack) | On each call, reads live parameter values from the figure's `ParameterManager` |

`BoundNumpifiedFunction` is itself callable and supports `.unbind()` to recover
the parent `NumpifiedFunction`.

### 3. Minor SmartFigure context-manager adaptation

Expose a **public helper** to obtain the current figure from the context stack:

```python
from gu_toolkit.SmartFigure import current_figure   # returns SmartFigure | None
```

This avoids users (and `NumpifiedFunction.bind(None)`) reaching into the
private `_current_figure()` / `_require_current_figure()` helpers.

### 4. Simplify `NumericExpression` wrappers

Once `NumpifiedFunction` carries its own metadata and binding logic, the
existing `DeadUnboundNumericExpression`, `DeadBoundNumericExpression`, and
`LiveNumericExpression` dataclasses in `NumericExpression.py` can delegate to
(or be replaced by) thin facades over `NumpifiedFunction` and
`BoundNumpifiedFunction`.

`SmartPlot` can store a `NumpifiedFunction` directly instead of the separate
`_core` + `_parameters` + `_func` triple.

## What Does NOT Change

- The code-generation internals of `numpify` (printer, `exec`, bindings).
- `ParameterSnapshot`, `ParamRef`, `ParameterManager` — untouched.
- The public plotting API (`fig.plot(...)`, slider creation, render loop).

## Critique / Risks

1. **Cache identity** — `numpify_cached` currently returns the raw callable;
   wrapping it in `NumpifiedFunction` must preserve caching semantics (same
   expression + args = same object, not a new wrapper each time).

2. **Live binding couples `numpify` to SmartFigure** — introducing a
   `.bind(smart_figure)` path creates a dependency from a low-level compilation
   module to the high-level figure system.  This should be managed via
   late/lazy imports or by accepting a generic protocol rather than a concrete
   `SmartFigure` type.

3. **`bind(None)` implicit context** — relying on global stack state is
   convenient but fragile in async/multi-figure scenarios.  Must document
   clearly and raise eagerly if no figure is active.

4. **Back-compat** — existing code that indexes into `numpify(...)` return
   value or passes it where a plain callable is expected must keep working.
   `NumpifiedFunction.__call__` satisfies this, but type checkers and
   `isinstance(..., types.FunctionType)` checks may break.

5. **Redundancy with `NumericExpression`** — there will be a transitional
   period where both systems coexist.  A clear deprecation / migration path is
   needed to avoid two parallel binding hierarchies.
