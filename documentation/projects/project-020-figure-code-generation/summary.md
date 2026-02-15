# Project 020: Figure Code Generation

## Rationale

The toolkit already supports interactive figure authoring, but there was no stable way to export a figure as reproducible Python source.

This project adds a first-class snapshot + codegen pipeline so users can:
- Capture a complete, immutable representation of figure state.
- Generate a runnable script that rebuilds the same figure.
- Share and version-control figure setups outside notebook runtime state.

## Architecture

The merged branch introduces three layers:

1. Snapshot model (immutable dataclasses)
- `PlotSnapshot` (`PlotSnapshot.py`) captures expression, variable, parameters, and style/domain metadata for each plot.
- `FigureSnapshot` and `InfoCardSnapshot` (`FigureSnapshot.py`) capture figure-level defaults, full parameter metadata, plot snapshots, and serializable info-card content.

2. Snapshot producers (runtime -> model)
- `Figure.snapshot()` in `Figure.py` aggregates global settings, parameter snapshot, all plot snapshots, and info-card snapshots.
- `Plot.snapshot()` in `figure_plot.py` serializes per-plot render and style state.
- `FigureInfo.snapshot()` in `figure_info.py` serializes static info-card segments and marks dynamic segments as `"<dynamic>"`.

3. Code generation (model -> Python source)
- `figure_to_code()` in `codegen.py` emits a complete script (`import sympy as sp`, symbol declarations, `Figure(...)`, parameter setup, `fig.plot(...)`, `fig.info(...)`, final `fig`).
- `sympy_to_code()` in `codegen.py` uses a custom SymPy printer that prefixes functions/constants with `sp.` and preserves symbol names.
- `Figure.to_code()` in `Figure.py` is the end-user API that calls `figure_to_code(self.snapshot())`.

Public API exports were extended in `__init__.py` to expose snapshot/codegen objects and helpers.

## Current Status

Completed in this merge:
- Added immutable snapshot dataclasses for figure, plot, and info cards.
- Added snapshot creation methods across figure/plot/info subsystems.
- Added script generation engine for figure reconstruction.
- Added top-level API exports for snapshots and codegen helpers.
- Preserved `main` behavior that removes deprecated `get_info_output` / `add_info_component` APIs.

## Remaining TODOs

- Add dedicated tests for `Figure.snapshot()` and `Figure.to_code()` output stability.
- Add round-trip tests: build figure -> snapshot -> generated code -> rebuilt figure equivalence checks.
- Define policy for dynamic info segments beyond current placeholder behavior (`"<dynamic>"`).
- Add user-facing docs/notebook examples demonstrating export/import workflow.
