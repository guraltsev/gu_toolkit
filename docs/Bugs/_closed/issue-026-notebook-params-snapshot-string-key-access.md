# Issue 026: `params.snapshot()` key-access ergonomics mismatch in notebook diagnostics example

## Status
Closed

## Summary
State-of-completion checklist:
- [x] Baseline snapshot immutability and ordering tests exist.
- [x] String-key lookup ergonomics are implemented for parameter snapshots.
- [x] Ambiguous/unknown string-key error messaging is implemented.
- [x] Iteration and `keys()` remain symbol-based only (current behavior matches requirement).
- [x] Targeted tests cover notebook-requested string access and ambiguity/unknown failure modes.
- [x] Notebook diagnostics example uses supported string-key access (`p['b']`) and aligns with runtime behavior.

## Evidence
- `ParameterSnapshot.__getitem__` supports symbol keys and unambiguous string-name keys.
- `params.snapshot()` now supports symbol keys and unambiguous string-name keys while preserving symbol-based iteration.
- `tests/test_parameter_snapshot_numeric_expression.py` covers unambiguous string success, unknown-name failure, ambiguous-name failure, and symbol-only key iteration guarantees.
- `docs/notebooks/Toolkit_overview.ipynb` diagnostics code uses `p['b']` and no longer documents missing string-key lookup as a bug.

## TODO
- [x] Specify mapping semantics for snapshot key lookup (symbol keys + optional unambiguous string lookup).
- [x] Implement ambiguity handling and actionable error text for invalid/ambiguous string names.
- [x] Ensure iterators/`keys()` return only symbol objects.
- [x] Add focused unit tests for unambiguous success, ambiguous failure, unknown failure, and iterator/key type guarantees.
- [x] Validate notebook parity and close issue.

## Exit criteria
- [x] Snapshot lookup behavior is well-defined, consistent, and tested.
- [x] Notebook examples align with implemented behavior.
- [x] Issue is ready for `_closed` archival.
