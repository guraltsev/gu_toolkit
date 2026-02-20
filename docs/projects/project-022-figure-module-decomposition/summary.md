# Project 022: Figure Module Decomposition

**Status:** In Progress
**Priority:** High

## Goal/Scope

Reduce `Figure.py` from its current 67 KB / ~1,987 lines to a manageable
coordinator by extracting self-contained subsystems into dedicated modules.
The public API (`from gu_toolkit import Figure, plot, parameter, ...`) must
remain unchanged.

## Context

`Figure.py` is the largest module by a wide margin. It contains 49 methods
across 4 classes plus 17 module-level helper functions. The delegation
pattern to managers (`ParameterManager`, `InfoPanelManager`,
`LegendPanelManager`, `FigureLayout`) is sound, but the coordinator itself
has accumulated too many orchestration responsibilities.

Key complexity hotspots identified in the code review:

- **`plot()` method (214 lines):** Mixes input normalization, parameter
  auto-detection, style resolution, create-vs-update branching, and numeric
  function setup.
- **`_normalize_plot_inputs()` (110 lines):** Handles 5+ input formats
  with deep if-elif chains.
- **Module-level helpers (17 functions, lines 1753–1987):** Procedural
  wrappers that route through `_require_current_figure()`.
- **View management methods:** `add_view()`, `set_active_view()`,
  `remove_view()`, `view()` and associated stale-marking logic.
- **Backward-compatibility aliases:** `self._figure` and `self._pane`
  mirror active view runtime and can go stale.

## Proposed extraction targets

1. **`figure_api.py`** — Move the 17 module-level helper functions (`plot`,
   `parameter`, `render`, `set_title`, `get_title`, `set_x_range`, etc.)
   to a dedicated module. These functions only delegate to
   `_require_current_figure()` and carry no state.

2. **`PlotInputNormalizer`** — Extract `_normalize_plot_inputs()`,
   `_coerce_symbol()`, `_rebind_numeric_function_vars()` into a stateless
   normalizer. This makes plot input contracts independently testable and
   isolates the most complex logic in `plot()`.

3. **`ViewManager`** — Extract `add_view()`, `set_active_view()`,
   `remove_view()`, `view()`, `_active_view()`, and view stale-marking
   into a dedicated manager following the established manager pattern.

4. **Deprecation of `self._figure` / `self._pane`** — Replace with
   explicit `figure_widget_for(view_id)` access.

## TODO checklist

- [x] Extract module-level helpers to `figure_api.py` with re-exports.
- [x] Extract plot input normalization to a testable unit.
- [x] Extract view management to a `ViewManager`.
- [x] Deprecate `self._figure` / `self._pane` aliases.
- [x] Add regression tests for all public import paths.
- [x] Verify `Figure.py` is reduced to coordinator-only responsibilities.

## Exit criteria

- [ ] `Figure.py` is materially smaller (target: under 800 lines).
- [x] Each extracted module has focused unit tests.
- [x] All existing user-facing imports remain valid via `__init__.py`
      re-exports.
- [x] Test suite passes with no regressions (project-phase decomposition suites).

## Challenges and mitigations

- **Challenge:** Extracting `PlotInputNormalizer` requires careful
  handling of closures that reference `self` (Figure instance).
  **Mitigation:** Pass required state as explicit parameters to the
  normalizer; avoid capturing `self`.

- **Challenge:** View stale-marking logic is scattered across `render()`,
  `_run_relayout()`, and parameter change hooks.
  **Mitigation:** Centralize stale-marking in `ViewManager` with a single
  `mark_stale()` entry point.

- **Challenge:** Module-level helpers are the most-imported API surface.
  **Mitigation:** Keep `from gu_toolkit import plot, parameter, render`
  working via `__init__.py` re-exports; never break the public path.

## Completion Assessment (2026-02-18)

- [ ] `Figure.py` is still monolithic (currently ~2,098 lines), above the under-800 target.
- [ ] Module-level helper API has not been extracted to `figure_api.py`; helper wrappers remain in `Figure.py`.
- [ ] Plot input normalization remains embedded in `Figure.py` (`_normalize_plot_inputs`).
- [ ] View management extraction to a dedicated `ViewManager` is not complete.
- [ ] Legacy aliases (`self._figure` / `self._pane`) are still present.

**Result:** Project remains **open**. Scope is largely unstarted in code, so no completion move is appropriate.


## Phase Implementation Update (2026-02-20)

- ✅ Completed **Phase 1**: module-level helper API extracted from `Figure.py` into `figure_api.py` and re-exported through `Figure.py`/package namespace without user-facing import changes.
- ✅ Completed **Phase 2**: callable/expr normalization extracted into `figure_plot_normalization.py`; `Figure.plot()` now delegates to `normalize_plot_inputs(...)`.
- ✅ Completed **Phase 3**: view lifecycle + stale-state policy centralized in `figure_view_manager.py`; `Figure` now delegates view add/switch/remove and stale tracking to `ViewManager`.
- ✅ Completed **Phase 4**: removed legacy mutable alias *state* (`self._figure` / `self._pane`) and replaced internal usage with explicit accessors (`figure_widget`, `figure_widget_for`, `pane`, `pane_for`), with no backward-compatibility shim properties retained.
- ✅ Added targeted regression tests for phase 1-4 behavior (`tests/test_project022_phase12_decomposition.py`, `tests/test_project022_phase34_decomposition.py`).
- ✅ Phase 5 is now complete; see the phase 5+6 update below for coordinator hardening details.


## Phase 5+6 Implementation Update (2026-02-20)

- ✅ Completed **Phase 5** coordinator hardening by extracting plot style alias/option contract into `figure_plot_style.py` and keeping `Figure.plot()` as orchestration-only for style normalization usage.
- ✅ Added decomposition conformance/regression tests for phase 5 architecture boundaries (`tests/test_project022_phase56_decomposition.py`), including guardrails against reintroducing legacy normalizer helpers into `Figure.py`.
- ✅ Recorded measurable decomposition metric: `Figure.py` is now **1,564 lines** (down from ~2,098 baseline; ~25.5% reduction).
- ✅ Completed **Phase 6 acceptance hardening pass** for decomposition milestones by running phase 1-5 regression suites together.
- ⏳ Project remains **open** pending external review and under-800 stretch target reassessment in follow-on work.

## Findings: Why `Figure.py` is still large after Project 022 phases

Project 022 delivered the planned extractions (API wrappers, normalization,
view manager, style normalization), but the file is still large because the
remaining surface area is broad and still centered in the coordinator class.

### 1) The remaining class still carries a wide public API by design

- `Figure` currently contains **51 methods/properties**. Even with helper
  extraction complete, the coordinator still owns many user-facing accessors
  (`title`, axis/viewport ranges, sampling points, view controls, hooks,
  snapshots/codegen, context manager protocol, notebook display protocol).
- This shape is functionally correct, but line count remains high because the
  API breadth itself is large.

### 2) The largest single method (`plot`) is still orchestration-heavy

- `Figure.plot()` is still the biggest method (~235 lines). It now delegates
  normalization and style aliases, but it still has to orchestrate:
  create-vs-update flow, plot registry mutation, legend wiring, parameter
  auto-registration, and render/stale interactions.
- This means complexity moved out of specific helper logic, but not all of the
  orchestration can be removed without introducing a higher-level plot service.

### 3) Constructor + runtime wiring remain substantial

- `__init__` and runtime construction helpers are still significant because
  they compose and connect layout, parameter manager, info manager, legend
  manager, view manager, debouncers, and per-view widget/pane runtime objects.
- This integration responsibility is central to `Figure`, so those lines are
  not eliminated by phase 1-6 extraction work.

### 4) Render and hook lifecycle are still coordinated in this file

- `render`, relayout throttling, hook registration (`add_hook`,
  `add_param_change_hook`), logging helpers, and notebook display/context
  protocol methods remain in `Figure.py`.
- These are cross-cutting lifecycle concerns that currently have no separate
  coordinator module, so they keep `Figure.py` above the under-800 target.

### 5) Documentation and explicit contracts increase line count (intentionally)

- The repository standards require comprehensive public/private docstrings and
  examples. `Figure.py` includes extensive module and method documentation.
- This is valuable and intentional, but it contributes non-trivial LOC that
  are not “dead weight” and should not be treated as decomposition failure.

## Recommended follow-on scope (if under-800 remains mandatory)

To move below the original stretch target, a follow-on project is needed with
new extraction seams beyond Project 022's completed scope:

1. Extract plot orchestration workflow from `Figure.plot()` into a dedicated
   plot service/coordinator (distinct from input normalization already done).
2. Extract render lifecycle + relayout throttling into a render pipeline
   component.
3. Extract notebook display/context protocol helpers to a thin mixin/module if
   acceptable for readability.
4. Reassess whether under-800 is still a useful target versus a more realistic
   “bounded complexity + clear ownership” target.
