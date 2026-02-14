# Project 03: Reorganize Into Subpackages

**Priority:** Low
**Effort:** High
**Impact:** Better navigability at scale, clearer ownership boundaries

---

## Problem

All 18 source files are at the same level in a flat package. File naming is inconsistent (mix of PascalCase and snake_case). As the toolkit grows (e.g., the planned `SmartPad2D` widget), the flat structure will become harder to navigate.

Additionally, `prelude.py` bundles at least four distinct concerns:
1. Classroom wildcard imports and Greek letter symbols
2. `SymbolFamily` and `FunctionFamily` classes
3. `Infix` operator support
4. Numerical helpers (`NIntegrate`, `NReal_Fourier_Series`, `play`)

And `figure_context.py` bundles:
1. The figure context stack
2. Shared type aliases (`NumberLike`, `RangeLike`, etc.)
3. Plot style options dict

## Proposed Structure

```
gu_toolkit/
  __init__.py                  # Public API re-exports (unchanged surface)
  _types.py                    # Shared type aliases (NumberLike, RangeLike, etc.)

  figure/
    __init__.py
    _figure.py                 # Figure class
    _api.py                    # Module-level helpers (plot, parameter, render, etc.)
    _context.py                # Figure context stack
    _layout.py                 # FigureLayout, OneShotOutput
    _parameters.py             # ParameterManager
    _info.py                   # InfoPanelManager
    _plot.py                   # Plot class

  widgets/
    __init__.py
    _slider.py                 # FloatSlider
    _plotly_pane.py            # PlotlyPane, PlotlyResizeDriver

  math/
    __init__.py
    _numpify.py                # SymPy → NumPy compilation
    _prelude.py                # Classroom imports, SymbolFamily, FunctionFamily
    _named_function.py         # NamedFunction decorator
    _parse_latex.py            # LaTeX parsing
    _numeric.py                # NIntegrate, NReal_Fourier_Series, play

  core/
    __init__.py
    _param_ref.py              # ParamRef protocol
    _param_event.py            # ParamEvent dataclass
    _parameter_snapshot.py     # ParameterSnapshot
    _input_convert.py          # InputConvert
    _debouncing.py             # QueuedDebouncer
```

## Migration Strategy

This is a breaking internal change (all internal imports change) but should preserve the public API surface exactly. The approach:

1. **Create subpackage directories** with `__init__.py` files.
2. **Move files one at a time**, updating internal imports.
3. **Keep the top-level `__init__.py`** re-exporting everything from the same public names.
4. **Run tests after each move** to catch broken imports immediately.
5. **Rename files to snake_case** during the move (e.g., `Figure.py` -> `figure/_figure.py`).

## Risks

- High effort with many files to touch.
- Any external code importing internal modules directly (not through `__init__.py`) will break.
- Notebook imports like `from gu_toolkit.Figure import Figure` would need a compatibility shim or deprecation period.

## When to Do This

This project should be done **after** Project 01 (packaging) and Project 04 (testing infrastructure) are in place, so that:
- The package is properly installable.
- Tests can catch import breakage automatically.
- CI validates every step.

## Acceptance Criteria

- [ ] All source files use snake_case naming
- [ ] Files are organized into logical subpackages
- [ ] Public API (`from gu_toolkit import ...`) is unchanged
- [ ] All tests pass
- [ ] `prelude.py` numeric helpers are in a separate module
- [ ] Type aliases are in `_types.py`
