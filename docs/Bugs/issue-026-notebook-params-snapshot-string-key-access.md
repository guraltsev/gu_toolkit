# Issue 026: `params.snapshot()` key-access ergonomics mismatch in notebook diagnostics example

## Status
Open

## Summary
State-of-completion checklist:
- [x] Baseline snapshot immutability and ordering tests exist.
- [ ] String-key lookup ergonomics are not implemented for `ParameterSnapshot`.
- [ ] Ambiguous/unknown string-key error messaging is not implemented.
- [x] Iteration and `keys()` remain symbol-based only (current behavior matches requirement).
- [ ] No targeted tests yet cover notebook-requested string access and ambiguity failure modes.

## Evidence
- `ParameterSnapshot.__getitem__` currently accepts only symbol keys.
- Existing tests in `tests/test_parameter_snapshot_numeric_expression.py` cover order/immutability but not string lookups.
- Notebook diagnostics section still carries BUG guidance requesting string-key behavior.

## TODO
- [ ] Specify mapping semantics for snapshot key lookup (symbol keys + optional unambiguous string lookup).
- [ ] Implement ambiguity handling and actionable error text for invalid/ambiguous string names.
- [x] Ensure iterators/`keys()` return only symbol objects.
- [ ] Add focused unit tests for unambiguous success, ambiguous failure, unknown failure, and iterator/key type guarantees.
- [ ] Add notebook regression coverage for diagnostics card workflows.

## Exit criteria
- [ ] Snapshot lookup behavior is well-defined, consistent, and tested.
- [ ] Notebook diagnostics examples can rely on documented key semantics without BUG notes.
