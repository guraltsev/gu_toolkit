# gu_toolkit Code Analysis Report

**Date:** 2026-02-14
**Scope:** Full codebase review — 18 Python source files, ~9,200 lines of code

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Strengths](#strengths)
3. [Architectural Concerns](#architectural-concerns)
4. [Stale & Dead Code](#stale--dead-code)
5. [Likely Bug Sources](#likely-bug-sources)
6. [Simplification Opportunities](#simplification-opportunities)
7. [Logical Organization Review](#logical-organization-review)
8. [Testing & Infrastructure Gaps](#testing--infrastructure-gaps)
9. [Recommended Projects](#recommended-projects)

---

## Executive Summary

`gu_toolkit` is a well-designed, composition-oriented interactive mathematics toolkit for Jupyter notebooks. It bridges SymPy symbolic math with Plotly interactive visualizations through a carefully layered architecture. The codebase demonstrates strong software engineering fundamentals — protocol-driven interfaces, immutable event payloads, context manager patterns, and clean separation of concerns.

However, the project has accumulated technical debt in several areas: it lacks standard Python packaging, has no CI/CD pipeline, carries stale code from earlier iterations, has inconsistent type annotation coverage, and contains a few architectural choices that increase maintenance cost without proportional benefit. This report identifies specific issues and recommends concrete improvement projects.

**Overall quality: Good.** The core architecture is sound. Most issues are in infrastructure and polish rather than fundamental design.

---

## Strengths

### 1. Composition-Based Architecture
The `Figure` class delegates to specialized managers rather than accumulating all logic in one monolith:

| Manager | Responsibility |
|---------|---------------|
| `ParameterManager` (`figure_parameters.py`) | Slider lifecycle, change hooks, dict-like parameter access |
| `InfoPanelManager` (`figure_info.py`) | Info sidebar, dynamic segments, error rendering |
| `FigureLayout` (`figure_layout.py`) | Widget hierarchy construction, CSS, one-shot output safety |
| `Plot` (`figure_plot.py`) | Single-curve compilation, sampling, trace updates |
| `PlotlyPane` (`PlotlyPane.py`) | Responsive Plotly sizing via ResizeObserver |

This decomposition makes each piece testable and replaceable independently.

### 2. Protocol-Driven Parameter System
`ParamRef` (`ParamRef.py:1-592`) is defined as a `runtime_checkable Protocol` rather than a base class. This means any widget that quacks like a parameter reference works — the system is not locked to a specific slider implementation. The `ProxyParamRef` wrapper further decouples the Figure from widget internals.

### 3. Immutable Event & Snapshot Types
- `ParamEvent` (`ParamEvent.py`) is a frozen dataclass — events cannot be accidentally mutated after dispatch.
- `ParameterSnapshot` (`ParameterSnapshot.py`) uses `deepcopy` + `MappingProxyType` for true immutability.

These choices prevent a class of subtle state-sharing bugs that are common in callback-driven interactive systems.

### 4. Smart Compilation Pipeline
`numpify.py` provides a thoughtful SymPy-to-NumPy compiler with a **compile-once, call-many** design:
- Expressions are compiled with both the independent variable AND parameters as positional arguments (`figure_plot.py:159` — `numpify_cached(func, vars=[var] + parameters)`). On slider drags, the same compiled function is called with updated parameter values — **no recompilation occurs**.
- `DYNAMIC_PARAMETER` sentinel and `NumpifiedFunction.set_parameter_context()` enable parameter values to be resolved from the figure's live `parameter_context` at call time (`figure_plot.py:178`), making the render path a pure function call with no compilation overhead.
- LRU caching (`numpify_cached`) avoids redundant compilation when the same symbolic expression is plotted again (e.g., re-executing a notebook cell). It is **not** needed for the slider-drag hot path — that path is already compilation-free by design.
- Custom function support via `f_numpy` attribute detection means users can extend the system without modifying core code.
- Identifier mangling handles edge cases (reserved words, symbols with special characters).

### 5. Defensive UI Patterns
- `OneShotOutput` (`figure_layout.py`) prevents accidental double-display of widgets — a common Jupyter footgun.
- `QueuedDebouncer` (`debouncing.py`) throttles render callbacks during rapid slider drags and pan/zoom events.
- Rate-limited logging in `Figure.py` prevents console spam during interactive sessions.
- The `FloatSlider` (`Slider.py`) accepts mathematical expressions (e.g., `pi/2`, `sqrt(3)`) in the text field, with graceful revert on parse failure.

### 6. Thorough Documentation
The developer guide (`documentation/develop_guide/smartfigure_developer_guide.md`) is unusually comprehensive for a project of this size — it covers architecture, render flow, parameter system design, compilation pipeline, and extensibility points. Bug reports in `documentation/Bugs/` follow a structured format with root cause analysis.

### 7. Context Manager Facade
The `with fig:` pattern (`figure_context.py`) enables module-level helpers (`plot()`, `parameter()`, `info()`) to operate on the "current" figure without explicit figure references. This produces clean, notebook-friendly code:
```python
with fig:
    plot(x, sin(a * x))
    parameter(a, min=-3, max=3)
```

---

## Architectural Concerns

### A1. No Python Packaging Configuration

**Files affected:** Project root (missing `pyproject.toml`, `setup.py`, `requirements.txt`)

The toolkit has zero packaging infrastructure. There is no `pyproject.toml`, no `setup.py`, no `requirements.txt`. This means:
- Users cannot `pip install` the toolkit.
- Dependencies are undeclared — there is no machine-readable list of required packages (sympy, numpy, plotly, ipywidgets, anywidget, traitlets, pandas, lark).
- Version constraints are unspecified, risking silent breakage on dependency updates.
- CI/CD cannot be automated without dependency declarations.

**Severity:** High. This is the single largest infrastructure gap.

See: [project-01-packaging.md](./project-01-packaging.md)

### A2. Figure.py Is Three Modules Concatenated Into One

**File:** `Figure.py` (1,486 lines)

Despite the good composition pattern, `Figure.py` still contains:
- The `Figure` class itself (coordinator)
- Module-level helper functions (`plot()`, `parameter()`, `render()`, etc.)
- Module-level proxy objects (`parameters`, `plots`, `params`)
- Duplicate module docstrings (lines 1-6 and lines 12-28 are two separate docstrings)
- Re-exports from sub-modules

The file also has a stale comment at line 10: `# NOTE: This file is Figure.py with the Info Components API implemented. It is intended as a drop-in replacement.` — this suggests the file was created by copying an earlier version and the note was never cleaned up.

**Impact:** Harder to navigate and maintain. The module-level helpers could live in their own file (e.g., `figure_helpers.py` or `api.py`).

See: [project-02-figure-decomposition.md](./project-02-figure-decomposition.md)

### A3. Global Mutable State in Figure Context Stack

**File:** `figure_context.py:8`

```python
_FIGURE_STACK: List["Figure"] = []
```

The context stack is a module-level mutable list with no thread-safety guarantees. In a multi-threaded Jupyter environment (e.g., async widgets, background tasks), concurrent push/pop operations could corrupt the stack.

The `_pop_current_figure` function (lines 96-116) does a linear scan to find and remove a figure — this is O(n) and handles out-of-order pops, which hints at past bugs with stack discipline.

**Impact:** Potential for subtle context corruption in async/threaded notebook workflows. The O(n) scan is not a performance concern at typical stack depths but signals architectural fragility.

### A4. `exec()` for Code Generation in numpify

**File:** `numpify.py`

The compilation pipeline uses `exec()` to turn generated source code into a callable. While this is a common pattern in SymPy's own codebase and is safe when the input is a SymPy expression (which is trusted structured data), it is worth noting:

- There is no explicit trust boundary documented.
- The generated code namespace includes NumPy and any user-provided `f_numpy` bindings.
- If the toolkit were ever used in a web-facing context, this would be a code injection vector.

**Impact:** Low risk for the current Jupyter-only use case, but should be documented as a known trust assumption.

### A5. Prelude Wildcard Imports

**File:** `prelude.py:15` and `__init__.py:13`

```python
from sympy import *          # prelude.py
from .prelude import *       # __init__.py
```

This is intentional for classroom convenience, but it:
- Pollutes the namespace with hundreds of SymPy symbols.
- Makes it impossible to trace where names come from without reading the import chain.
- Risks name collisions as SymPy evolves (e.g., if SymPy adds a new export that shadows a toolkit name).

The `__all__` list in `prelude.py` is dynamically constructed from `sympy.__all__`, which means the exported namespace changes with SymPy versions.

**Impact:** Acceptable trade-off for classroom use, but should be documented as a deliberate choice with known risks. Consider providing an alternative import path for power users who want explicit imports.

### A6. Mixed Naming Conventions for Source Files

Source files use three different naming conventions:
- **PascalCase:** `Figure.py`, `Slider.py`, `PlotlyPane.py`, `ParamRef.py`, `ParamEvent.py`, `ParameterSnapshot.py`, `NamedFunction.py`, `InputConvert.py`, `ParseLaTeX.py`
- **snake_case:** `figure_context.py`, `figure_layout.py`, `figure_parameters.py`, `figure_plot.py`, `figure_info.py`, `debouncing.py`
- **snake_case with prefix:** `numpify.py`, `prelude.py`

PEP 8 recommends snake_case for module names. The current mix suggests PascalCase files were created earlier and snake_case files were added during a composition refactor.

**Impact:** Minor, but inconsistent naming creates friction for new contributors.

---

## Stale & Dead Code

### S1. Duplicate Module Docstrings in Figure.py

**File:** `Figure.py:1-6` and `Figure.py:12-28`

Two separate module docstrings exist at the top of the file. The first (lines 1-6) is a brief description. The second (starting line 12) is a longer guide that was likely the original docstring. Only the first one is used by Python as the actual module docstring.

### S2. Drop-in Replacement Comment

**File:** `Figure.py:10`

```python
# NOTE: This file is Figure.py with the Info Components API implemented.
#       It is intended as a drop-in replacement.
```

This comment references a past refactoring step and is no longer meaningful. It should be removed.

### S3. Commented Debug Print in prelude.py

**File:** `prelude.py:26`

```python
# print("__all__ (from prelude):",__all__)
```

Commented-out debug statement.

### S4. Duplicate `import sympy as sp` in prelude.py

**File:** `prelude.py:13` and `prelude.py:27`

SymPy is imported twice — once before the wildcard import and once after. The second import is redundant.

### S5. Open Bug Not Addressed in Code

**File:** `ParseLaTeX.py` / `documentation/Bugs/open/bug-002-parse-latex-ambiguous-tree.md`

Bug 002 documents that `parse_latex()` can return a `Tree` object instead of a SymPy expression for certain inputs (unparenthesized products after fractions). The fix plan exists in documentation but has not been implemented. This is stale in the sense that the bug is documented but unfixed.

---

## Likely Bug Sources

### B1. Figure Context Stack Is Not Thread-Safe

**File:** `figure_context.py:8-116`

`_FIGURE_STACK` is a plain `list` with no locking. `_push_current_figure` and `_pop_current_figure` can race in async widget callbacks. The `_pop_current_figure` function's linear scan (lines 113-116) tries to handle out-of-order removal, which suggests this has been a source of issues.

**Likely symptom:** Under concurrent widget callbacks, `current_figure()` could return the wrong figure or `None` unexpectedly.

### B2. Mutable Default Argument in Plot.__init__

**File:** `figure_plot.py:40`

```python
parameters: Sequence[Symbol] = [],
```

Using a mutable default (`[]`) is a classic Python footgun. If the list were ever mutated in place, all callers sharing the default would be affected. In this case the parameter is likely never mutated (it is iterated, not appended to), but it violates the standard `None`-default pattern.

### B3. QueuedDebouncer Callback Runs Outside Lock

**File:** `debouncing.py:84`

```python
self._callback(*call.args, **call.kwargs)
```

The callback executes after releasing `self._lock`. If the callback raises an exception:
- In threading mode: the exception is silently swallowed by `threading.Timer`.
- In asyncio mode: the exception may propagate differently.

There is no error handling around callback execution. A failing callback will silently stop debounced updates.

### B4. ParseLaTeX Ambiguous Tree Bug (Open)

**File:** `ParseLaTeX.py`

As documented in bug-002, the `lark` backend can return a `Tree` object instead of a SymPy `Expr`. Downstream code that calls `.free_symbols` on the result will get an `AttributeError`. The fallback to `antlr` only triggers on exceptions, not on wrong return types.

### B5. Slider _syncing Guard May Suppress Legitimate Updates

**File:** `Slider.py`

The `_syncing` flag prevents circular updates between the slider widget and text field. However, if an exception occurs during a sync operation, the flag may remain set, permanently suppressing updates until the slider is recreated.

### B6. `sampling_points` Type Hint Is Malformed

**File:** `figure_plot.py:42`

```python
sampling_points: Optional[int,str] = None,
```

`Optional[int, str]` is not valid typing syntax. This should be `Optional[Union[int, str]]`. Python's runtime does not enforce type hints, so this doesn't cause a runtime error, but it will confuse type checkers and IDE tools.

---

## Simplification Opportunities

### P1. Consolidate Figure Module-Level Helpers

**Files:** `Figure.py`, `figure_context.py`

The module-level helpers (`plot()`, `parameter()`, `render()`, etc.) in `Figure.py` are thin wrappers around `_require_current_figure().method()`. These could be generated programmatically or consolidated. There are ~15 such wrappers.

### P2. Simplify ParameterSnapshot

**File:** `ParameterSnapshot.py`

The `ParameterSnapshot` class wraps a deep-copied dict with `MappingProxyType`. The class is only 71 lines but introduces its own `__getitem__`, `__iter__`, `__len__`, and `value_map()`. Since it already implements `Mapping`, consider whether a plain frozen dict (or `types.MappingProxyType` directly) would suffice.

### P3. Reduce CSS Inline in Slider.py

**File:** `Slider.py`

The slider embeds ~80 lines of CSS directly as Python string literals in `__init__`. This makes the CSS hard to maintain and impossible to override. Consider extracting to a `.css` file loaded at init or using a class-level constant.

### P4. Simplify _resolve_numeric_callable in prelude.py

**File:** `prelude.py`

The `_resolve_numeric_callable()` function is ~100 lines with deeply nested conditionals for resolving different expression types (SymPy expr, numpified function, plain callable, Lambda). This could be refactored into a dispatch table or chain-of-responsibility pattern.

### P5. Remove Redundant Type Aliases in figure_context.py

**File:** `figure_context.py:143-146`

Type aliases `NumberLike`, `NumberLikeOrStr`, `RangeLike`, and `VisibleSpec` are defined in `figure_context.py` but used across multiple files. They should be in a dedicated `_types.py` module to clarify they are shared types, not context-specific.

---

## Logical Organization Review

### Current Structure

```
gu_toolkit/
  __init__.py              # Public API re-exports
  Figure.py                # Coordinator + module helpers + proxies (1,486 lines)
  figure_context.py        # Context stack + type aliases + style options dict
  figure_layout.py         # OneShotOutput + FigureLayout
  figure_parameters.py     # ParameterManager
  figure_info.py           # InfoPanelManager
  figure_plot.py           # Plot
  numpify.py               # SymPy → NumPy compilation
  prelude.py               # Classroom imports + SymbolFamily + numeric helpers
  Slider.py                # FloatSlider widget
  PlotlyPane.py            # Responsive Plotly wrapper
  ParamRef.py              # Parameter reference protocol
  ParamEvent.py            # Parameter event dataclass
  ParameterSnapshot.py     # Immutable parameter snapshots
  InputConvert.py          # Input parsing
  NamedFunction.py         # Custom SymPy function decorator
  ParseLaTeX.py            # LaTeX parser wrapper
  debouncing.py            # QueuedDebouncer
```

### Assessment

**What works well:**
- The `figure_*.py` prefix groups related figure subsystems.
- Small utility modules (`debouncing.py`, `InputConvert.py`, `ParseLaTeX.py`) are properly separated.
- `numpify.py` is self-contained with clear boundaries.

**What could improve:**

1. **Flat structure at scale:** All 18 files are at the same level. As the toolkit grows, grouping into subpackages would help:
   - `figure/` — Figure coordinator, layout, parameters, info, plot, context
   - `widgets/` — FloatSlider, PlotlyPane
   - `math/` — numpify, prelude, NamedFunction, ParseLaTeX
   - `core/` — ParamRef, ParamEvent, ParameterSnapshot, InputConvert, debouncing

2. **`figure_context.py` is a grab bag:** It contains the context stack (core behavior), type aliases (shared types), and a style options dict (UI concern). These three responsibilities should be separated.

3. **`prelude.py` has too many responsibilities:** It handles:
   - Classroom wildcard imports
   - `SymbolFamily` and `FunctionFamily` classes
   - `Infix` operator support
   - `NIntegrate`, `NReal_Fourier_Series` numerical helpers
   - `play()` audio synthesis

   These are at least three distinct concerns. The numeric helpers and audio synthesis should be separate modules.

4. **Test files use non-standard patterns:** Tests use `importlib.util.spec_from_file_location` for dynamic module loading and hardcoded relative paths. This is fragile and unnecessary with proper packaging and pytest discovery.

See: [project-03-package-reorganization.md](./project-03-package-reorganization.md)

---

## Testing & Infrastructure Gaps

### T1. No CI/CD Pipeline

There are no GitHub Actions, no `tox.ini`, no `Makefile`. Tests are run manually. This means regressions can slip into merged PRs undetected.

### T2. Non-Standard Test Harness

Some test files (`test_Figure_module_params.py`) use custom `main()` functions and manual assertion helpers instead of pytest. Others assume pytest. This inconsistency makes it unclear how to run the full test suite.

### T3. Fragile Test Imports

Multiple test files (`test_NamedFunction.py`, `test_numpify_refactor.py`, `test_numpify_cache_behavior.py`) use `importlib.util.spec_from_file_location(Path("Module.py"))` with relative paths. These break if tests are run from any directory other than the project root.

### T4. No Coverage Reporting

There is no `.coveragerc`, no coverage configuration, and no visibility into which code paths are tested.

### T5. Minimal .gitignore

The `.gitignore` only excludes `__pycache__/` and `.ipynb_checkpoints/`. Missing: `*.pyc`, `.eggs/`, `dist/`, `build/`, `.venv/`, `.pytest_cache/`, `htmlcov/`, `.coverage`, `*.egg-info/`.

### T6. Gaps in Test Coverage

| Area | Coverage Status |
|------|----------------|
| Parameter lifecycle | Good (multiple test files) |
| numpify compilation | Good (3 test files) |
| Info cards | Good |
| NIntegrate / Fourier | Good (18 tests) |
| PlotlyPane resizing | None (notebook-only) |
| Slider widget behavior | None |
| ParseLaTeX (bug-002 case) | None |
| Figure render pipeline end-to-end | None |
| Concurrent context stack | None |

See: [project-04-testing-infrastructure.md](./project-04-testing-infrastructure.md)

---

## Recommended Projects

| # | Project | Priority | Effort | File |
|---|---------|----------|--------|------|
| 1 | Add `pyproject.toml` and packaging | High | Low | [project-01-packaging.md](./project-01-packaging.md) |
| 2 | Decompose Figure.py | Medium | Medium | [project-02-figure-decomposition.md](./project-02-figure-decomposition.md) |
| 3 | Reorganize into subpackages | Low | High | [project-03-package-reorganization.md](./project-03-package-reorganization.md) |
| 4 | Testing infrastructure & CI | High | Medium | [project-04-testing-infrastructure.md](./project-04-testing-infrastructure.md) |
| 5 | Fix known bugs & stale code | Medium | Low | [project-05-bug-fixes-cleanup.md](./project-05-bug-fixes-cleanup.md) |
| 6 | Type annotation completion | Low | Low | [project-06-type-annotations.md](./project-06-type-annotations.md) |
