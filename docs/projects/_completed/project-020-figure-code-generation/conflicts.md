# Merge Conflicts: `smart-figure-code-generation-0bZri` into `main`

## Merge Inputs

- Target branch: `main` (`c90378d70bbd8a125b011c773cdbf83eb1174238`)
- Source branch: `remotes/github/claude/smart-figure-code-generation-0bZri`
- Source commit: `781f3fc9659be6cee8713cee8421efcb17d11c9e`

## Conflicts Encountered

1. `Figure.py`
- Conflict area: methods near `add_param(...)` / info API region.
- `main` side carried `get_info_output(...)` (and alias `new_info_output`).
- source side introduced new `snapshot()` and `to_code()` methods and also included `get_info_output(...)`.

Resolution:
- Kept `snapshot()` and `to_code()` from source branch.
- Dropped `get_info_output(...)` / `new_info_output` to preserve `main`'s deprecation/removal.
- Removed duplicate/conflict-marker blocks.

2. `__init__.py`
- Conflict area: public API exports after `ParameterSnapshot` import.
- `main` side added explicit module export: `from . import numpify as numpify_module`.
- source side added new exports for snapshot/codegen APIs.

Resolution:
- Preserved both sets of exports:
  - `numpify_module` explicit module handle from `main`.
  - `PlotSnapshot`, `FigureSnapshot`, `InfoCardSnapshot`, `sympy_to_code`, `figure_to_code` from source branch.

## Post-Resolution Notes

- No conflict markers remain.
- Merge now contains the full figure snapshot/code-generation feature set while preserving `main`'s removal of legacy info-output helpers.
