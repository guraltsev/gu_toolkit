# Issue 026: `params.snapshot()` key-access ergonomics mismatch in notebook diagnostics example

## Status
ready to close (external review passed)

## Summary
State-of-completion checklist:
- [x] Baseline snapshot immutability and ordering tests exist.
- [x] String-key lookup ergonomics are implemented for parameter snapshots.
- [x] Ambiguous/unknown string-key error messaging is implemented.
- [x] Iteration and `keys()` remain symbol-based only (current behavior matches requirement).
- [x] Targeted tests cover notebook-requested string access and ambiguity/unknown failure modes.

## Evidence
- `ParameterSnapshot.__getitem__` now supports symbol keys and unambiguous string-name keys.
- `params.snapshot()` (value-only snapshot) now supports symbol keys and unambiguous string-name keys while preserving symbol-based iteration.
- Added regression tests for:
  - unambiguous string success,
  - unknown-name failure,
  - ambiguous-name failure,
  - symbol-only key iteration guarantees.
- ⚠️ **WARNING:** `docs/notebooks/Toolkit_overview.ipynb` still contains `#BUG` guidance claiming string-name access is missing. This notebook statement is now stale relative to runtime behavior and should be updated in a separate notebook-maintenance pass (per policy, notebook files were not modified in this fix).

## TODO
- [x] Specify mapping semantics for snapshot key lookup (symbol keys + optional unambiguous string lookup).
- [x] Implement ambiguity handling and actionable error text for invalid/ambiguous string names.
- [x] Ensure iterators/`keys()` return only symbol objects.
- [x] Add focused unit tests for unambiguous success, ambiguous failure, unknown failure, and iterator/key type guarantees.
- [x] Document implementation + verification progress in this issue.

## Exit criteria
- [x] Snapshot lookup behavior is well-defined, consistent, and tested.
- [x] External review completed before moving to `_closed`.
