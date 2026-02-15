# Design: Smart Figure Code Generation System

**Status:** Mostly implemented

## Status Update (2026-02-15)
- [x] Snapshot dataclasses exist (`PlotSnapshot.py`, `FigureSnapshot.py`).
- [x] `Figure.to_code()` pipeline exists (`codegen.py`, `Figure.py`).
- [x] Regression tests for generated code flow exist (`tests/test_figure_snapshot_codegen.py`).
- [ ] Confirm current docs match exact serialization limits (dynamic info/hook behavior).
- [x] Numbered follow-up proposal created and clarified: `project-027-codegen.md`.

---

## Goal

Add a `fig.to_code()` method (and supporting snapshot infrastructure) that emits
a self-contained Python script which fully reproduces the current figure — plots,
parameters, styling, and info cards — without requiring the original notebook.

---

## Example Output

```python
import sympy as sp
from gu_toolkit import Figure

# Symbols
x = sp.Symbol("x")
a = sp.Symbol("a")
b = sp.Symbol("b")

# Figure
fig = Figure(x_range=(-6, 6), y_range=(-3, 3), sampling_points=500)
fig.title = "Sine and Cosine"

# Parameters
fig.parameter(a, min=-1.0, max=1.0, value=0.5, step=0.01)
fig.parameter(b, min=0.0, max=5.0, value=2.0, step=0.1)

# Plots
fig.plot(x, a*sp.sin(b*x), parameters=[a, b], id="f_0", label="a·sin(bx)",
         color="#1f77b4", thickness=2, dash="solid", opacity=1.0,
         x_domain=(-10, 10), sampling_points=800)
fig.plot(x, sp.cos(x), parameters=[], id="f_1", label="cos(x)")

# Info cards
fig.info("Static description here")

fig
```

---

## Components to Add

### 1. `PlotSnapshot` — immutable snapshot of one plot's reproducible state

**File:** `PlotSnapshot.py` (new)

Captures everything needed to reconstruct a single `fig.plot(...)` call:

| Field | Type | Source |
|---|---|---|
| `id` | `str` | plot dict key |
| `var` | `Symbol` | `plot._var` |
| `func` | `Expr` | `plot._func` (the symbolic expression) |
| `parameters` | `tuple[Symbol, ...]` | `plot.parameters` |
| `label` | `str` | `plot.label` |
| `visible` | `bool \| str` | `plot.visible` |
| `x_domain` | `tuple[float,float] \| None` | `plot.x_domain` |
| `sampling_points` | `int \| None` | `plot.sampling_points` |
| `color` | `str \| None` | `plot.color` |
| `thickness` | `float \| None` | `plot.thickness` |
| `dash` | `str \| None` | `plot.dash` |
| `opacity` | `float \| None` | `plot.opacity` |

**API:**
```python
@dataclass(frozen=True)
class PlotSnapshot:
    id: str
    var: Symbol
    func: Expr
    parameters: tuple[Symbol, ...]
    label: str
    visible: bool | str
    x_domain: tuple[float, float] | None
    sampling_points: int | None
    color: str | None
    thickness: float | None
    dash: str | None
    opacity: float | None
```

**Method on `Plot`:**
```python
def snapshot(self) -> PlotSnapshot:
    ...
```

### 2. `FigureSnapshot` — immutable snapshot of the entire figure

**File:** `FigureSnapshot.py` (new)

Aggregates all sub-snapshots into one object:

| Field | Type | Source |
|---|---|---|
| `x_range` | `tuple[float,float]` | `fig.x_range` |
| `y_range` | `tuple[float,float]` | `fig.y_range` |
| `sampling_points` | `int` | `fig.sampling_points` |
| `title` | `str` | `fig.title` |
| `parameters` | `ParameterSnapshot` | `fig.parameters.snapshot(full=True)` |
| `plots` | `dict[str, PlotSnapshot]` | `{id: plot.snapshot() for ...}` |
| `info_cards` | `tuple[InfoCardSnapshot, ...]` | captured static text (see below) |

**API:**
```python
@dataclass(frozen=True)
class FigureSnapshot:
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    sampling_points: int
    title: str
    parameters: ParameterSnapshot
    plots: dict[str, PlotSnapshot]
    info_cards: tuple[InfoCardSnapshot, ...]
```

**Method on `Figure`:**
```python
def snapshot(self) -> FigureSnapshot:
    ...
```

### 3. `InfoCardSnapshot` — immutable snapshot of a simple info card

**File:** `FigureSnapshot.py` (same file, small dataclass)

Only static text segments are captured. Dynamic (callable) segments are recorded
as a placeholder string `"<dynamic>"` so the user knows something was there.

```python
@dataclass(frozen=True)
class InfoCardSnapshot:
    id: Hashable
    segments: tuple[str, ...]  # static text or "<dynamic>" marker
```

**Method on `InfoPanelManager`:**
```python
def snapshot(self) -> tuple[InfoCardSnapshot, ...]:
    ...
```

### 4. Symbolic Expression Serialization: `sympy_to_code()`

**File:** `codegen.py` (new) — the code-generation engine

Core challenge: convert `Expr` → valid Python string that, when `eval`'d with
the right symbols in scope, reconstructs the expression.

**Strategy:** Use a lightly customized `SymPy` code printer that:
- Prefixes SymPy functions with `sp.` (e.g. `sp.sin`, `sp.exp`, `sp.Rational`)
- Leaves `Symbol` names bare (they'll be defined as variables in the preamble)
- Handles special atoms: `sp.pi`, `sp.E`, `sp.I`, `sp.oo`
- Handles `Rational`, `Integer`, `Float` correctly
- Handles `Piecewise`, `Abs`, etc.

```python
def sympy_to_code(expr: Expr) -> str:
    """Return a Python source fragment reproducing *expr*.

    Assumes all Symbol names are available as local variables and
    that ``import sympy as sp`` is in scope.
    """
```

This is a pure function with no side effects — easy to unit test.

### 5. `Figure.to_code()` — the top-level code generator

**File:** `codegen.py`

Orchestrates the full script generation from a `FigureSnapshot`:

```python
def figure_to_code(snapshot: FigureSnapshot) -> str:
    """Return a self-contained Python script that recreates the figure."""
```

**Also exposed as a method on `Figure`:**
```python
# In Figure.py
def to_code(self) -> str:
    from .codegen import figure_to_code
    return figure_to_code(self.snapshot())
```

**Generation order:**
1. Imports (`import sympy as sp`, `from gu_toolkit import Figure`)
2. Symbol definitions — collect all unique symbols from parameters + plot vars + plot parameter lists
3. `fig = Figure(x_range=..., y_range=..., sampling_points=...)`
4. `fig.title = ...` (if non-empty)
5. Parameter setup — one `fig.parameter(sym, ...)` per parameter, using full snapshot metadata (value, min, max, step)
6. Plot calls — one `fig.plot(...)` per plot, with expression via `sympy_to_code()`, all styling kwargs
7. Info cards — `fig.info(...)` for static-only cards; a comment for cards with dynamic segments
8. `fig` (final expression for notebook display)

---

## New methods summary

| Location | Method | Returns |
|---|---|---|
| `Plot` | `snapshot()` | `PlotSnapshot` |
| `Figure` | `snapshot()` | `FigureSnapshot` |
| `Figure` | `to_code()` | `str` |
| `InfoPanelManager` | `snapshot()` | `tuple[InfoCardSnapshot, ...]` |

## New files

| File | Contents |
|---|---|
| `PlotSnapshot.py` | `PlotSnapshot` frozen dataclass |
| `FigureSnapshot.py` | `FigureSnapshot`, `InfoCardSnapshot` frozen dataclasses |
| `codegen.py` | `sympy_to_code()`, `figure_to_code()` |

## Modified files

| File | Change |
|---|---|
| `figure_plot.py` | Add `Plot.snapshot()` method |
| `Figure.py` | Add `Figure.snapshot()` and `Figure.to_code()` methods |
| `figure_info.py` | Add `InfoPanelManager.snapshot()` method |
| `__init__.py` | Export `PlotSnapshot`, `FigureSnapshot`, `InfoCardSnapshot` |

---

## Design decisions

1. **`sympy_to_code` uses `sp.`-prefixed function names** — This avoids requiring
   `from sympy import *` in the generated code, keeping the output clean and
   explicit. Symbol variables are bare names because they're defined as locals.

2. **Dynamic info segments are NOT serialized** — Callables cannot be reliably
   serialized to source. We emit a comment placeholder. Users who need dynamic
   info cards must re-add them manually.

3. **Hooks are NOT serialized** — Same reason as dynamic info. The generated code
   reproduces the *visual* state, not the interactive behavior.

4. **`line` and `trace` advanced kwargs are NOT captured** — These are arbitrary
   Plotly dicts that may contain non-serializable objects. The four explicit
   style properties (color, thickness, dash, opacity) cover the common cases.

5. **Snapshot objects are frozen dataclasses** — Consistent with `ParameterSnapshot`'s
   immutability design. Users can inspect snapshots without worrying about mutation.

6. **`to_code()` goes through `snapshot()` first** — Clean separation: snapshot
   captures state, codegen turns state into text. Both are independently useful.