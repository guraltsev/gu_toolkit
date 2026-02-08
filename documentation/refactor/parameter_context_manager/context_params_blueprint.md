# Blueprint: Module-level, context-managed parameter modification (`params[...]`) for SmartFigure

## Goal

Provide a module-level API for parameter access/modification that mirrors the existing `plot(...)` helper and integrates with the existing `with fig:` context stack, enabling:

```python
with fig:
    params[a].value = 5
```

while preserving **strict dict semantics** for `__getitem__` (no implicit parameter creation).

## Non-goals

- No changes to how `fig.params[...]` behaves (it should remain a strict lookup).
- No new widget types or 2D controls (this blueprint is only about module-level context access).
- No batching/debouncing of renders (can be added later as a separate feature).

## Current architecture (relevant pieces)

- A global figure stack is used to define a “current figure” (`with fig:` pushes/pops).
- A module-level `plot(...)` helper targets the current figure, and creates/displays a new figure if there is no current figure.
- Parameters are managed by `ParameterManager` (`fig.params`), which is a mapping `Symbol -> ParamRef`.
- Parameter creation is explicit via `ParameterManager.parameter(...)`.
- Lookup via `ParameterManager.__getitem__` is strict (raises `KeyError` if missing).

## Proposed public API

### 1) Module-level `params`: mapping proxy to the current figure’s `fig.params`

A singleton object that behaves like a read/write mapping of symbol -> ParamRef:

- `params[a]` returns `ParamRef` for `a` on the **current** figure.
- `params[a].value = 5` sets the value via the ref (recommended idiom).
- `params[a] = 5` optionally supported as a convenience alias for `params[a].value = 5` (see “Semantics”).

Critically:

- `params[a]` MUST NOT create a parameter if it is missing.
- If no current figure is active, `params[...]` should either raise or create a new figure (see Decision 1).

### 2) Module-level `parameter(...)`: “ensure/create” on the current figure

A helper to ensure parameter(s) exist on the current figure, analogous to `plot(...)`:

```python
with fig:
    parameter(a, min=-10, max=10, step=0.1, value=3)   # returns ParamRef
    parameter([a, b])                                  # returns dict[Symbol, ParamRef]
```

This is the **explicit** creation path, consistent with strict `params[a]` lookup.


## Semantics (spec)

### Semantics 0: “Current figure” resolution

All module-level parameter operations resolve the target figure via:

- the global stack’s top element (same mechanism as `plot(...)` uses).

### Semantics 1: Strict lookup (no implicit creation)

- `params[a]` delegates to `current_fig.params[a]` and therefore raises `KeyError` if `a` is missing.
- `a in params` returns `False` if missing and does not create anything.

### Semantics 2: Creation is explicit via `parameter(...)`

- `parameter(symbols, **kwargs)` forwards to `current_fig.params.parameter(...)`.

### Semantics 3: Behavior when no current figure is active (Decision 1)

Two viable behaviors:

**Decision 1A (recommended): raise**  
- `params[a]` raises `RuntimeError("No current SmartFigure. Use `with fig:` first.")`.
- `parameter(...)` also raises the same error.

Rationale: parameter mutation without an active figure is usually accidental, and auto-creating a figure for silent state changes is surprising.

### Semantics 4: sugar `params[a] = value`

Implement `__setitem__` so `params[a] = 5` sets `params[a].value`.

This is purely ergonomic and does not change core semantics.

## Implementation plan

### Step 1: Add a small proxy class in `SmartFigure.py`

Place near existing module-level helpers (close to `plot(...)`), so it can access `_current_figure`, `SmartFigure`, and the `ParameterManager` instance.

```python
from collections.abc import Mapping
from typing import Any, Dict, Iterator, Optional

class _CurrentParamsProxy(Mapping):
    def _fig(self) -> "SmartFigure":
        fig = _current_figure()
        if fig is None:
            # Decision 1A: raise
            raise RuntimeError("No current SmartFigure. Use `with fig:` first.")

            # Decision 1B: auto-create (alternative)
            # fig = SmartFigure()
            # display(fig)
        return fig

    def _mgr(self) -> "ParameterManager":
        return self._fig().params

    def __getitem__(self, key):
        return self._mgr()[key]  # strict lookup (KeyError if missing)

    def __iter__(self):
        return iter(self._mgr())

    def __len__(self):
        return len(self._mgr())

    def __contains__(self, key):
        return key in self._mgr()

    # Optional sugar (Decision 2B)
    def __setitem__(self, key, value):
        self[key].value = value

    # Explicit creation path
    def parameter(self, symbols, *, control=None, **kwargs):
        return self._mgr().parameter(symbols, control=control, **kwargs)
```

Then export a singleton:

```python
params = _CurrentParamsProxy()
```

### Step 2: Add a module-level `parameter(...)` helper

This is the module-level analog of `plot(...)`, targeting the current figure:

```python
def parameter(symbols, *, control=None, **kwargs):
    fig = _current_figure()
    if fig is None:
        # Decision 1A: raise
        raise RuntimeError("No current SmartFigure. Use `with fig:` first.")

        # Decision 1B: auto-create (alternative)
        # fig = SmartFigure()
        # display(fig)
    return fig.params.parameter(symbols, control=control, **kwargs)
```

Notes:
- Keep the name `parameter` only if it does not conflict with other exports in your public API.
- If you already export `SmartFigure.parameter` heavily, the module-level name is still fine; it matches the style of `plot`.

### Step 3: Documentation + examples

Add a comprehensive docstring (similar to):

```python
x, a = sp.symbols("x a")
fig = SmartFigure()

with fig:
    fig.plot(x, a*sp.sin(x), parameters=[a])
    params[a].value = 5             # modify existing param
    parameter(a, min=-10, max=10)   # ensure/create (if not already present)
```

Clarify:
- `params[a]` is strict and requires that `a` exists (via `plot(..., parameters=[a])` or via `parameter(a)`).

### Step 4: Tests

Add tests at the module level (or in your existing test harness) that verify:

1) **Within context**:
- `with fig: params[a] is fig.params[a]` after ensuring `a`.

2) **Strict lookup**:
- `with fig: params[a]` raises `KeyError` if `a` was never created.

3) **Creation path**:
- `with fig: parameter(a)` returns a `ParamRef`, and then `params[a]` succeeds.

4) **No-context behavior**:
- Decision 1: `params[a]` and `parameter(a)` raise `RuntimeError`.

5) **Optional assignment sugar** (if Decision 2):
- `with fig: params[a] = 7` sets `params[a].value == 7`.

### Step 5: Export surface

If you use `__all__`, add:

- `params`
- `parameter`

## Compatibility and migration

- No changes required for existing `fig.params` usage.
- Users who prefer explicit figure access can continue using `fig.params[a].value = ...`.
- Users who prefer pyplot-like usage can use the module-level `params` under `with fig:`.
