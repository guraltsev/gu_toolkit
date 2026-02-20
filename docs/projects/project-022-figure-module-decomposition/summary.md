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
- [ ] Add regression tests for all public import paths.
- [ ] Verify `Figure.py` is reduced to coordinator-only responsibilities.

## Exit criteria

- [ ] `Figure.py` is materially smaller (target: under 800 lines).
- [ ] Each extracted module has focused unit tests.
- [ ] All existing user-facing imports remain valid via `__init__.py`
      re-exports.
- [ ] Test suite passes with no regressions.

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
- ✅ Completed **Phase 4**: removed legacy mutable aliases (`self._figure` / `self._pane`) and replaced usage with explicit accessors (`figure_widget`, `figure_widget_for`, `pane`, `pane_for`).
- ✅ Added targeted regression tests for phase 1-4 behavior (`tests/test_project022_phase12_decomposition.py`, `tests/test_project022_phase34_decomposition.py`).
- ⏳ Remaining phase (5) is still open and tracked in the project TODO/exit criteria.
