# Issue 026: `params.snapshot()` key-access ergonomics mismatch in notebook diagnostics example

## Status
Open

## Summary
The notebook diagnostics section requests improved `params.snapshot()` ergonomics:
- allow lookup by symbol name string when unambiguous,
- raise helpful errors when string lookup is ambiguous or invalid,
- keep iteration and `keys()` symbol-based (do not mix in strings).

Current behavior does not satisfy this contract, making notebook diagnostics code less ergonomic and potentially confusing.

## Evidence
- In the diagnostics info-card section of `docs/notebooks/Toolkit_overview.ipynb`, a BUG comment specifies required snapshot key semantics and error behavior.

## TODO
- [ ] Specify mapping semantics for snapshot key lookup (symbol keys + optional unambiguous string lookup).
- [ ] Implement robust ambiguity handling and actionable error text.
- [ ] Ensure iterators/`keys()` return only symbol objects.
- [ ] Add focused unit tests for:
  - unambiguous string key success,
  - ambiguous string key failure,
  - unknown string key failure,
  - iterator/key type guarantees.
- [ ] Add regression coverage for notebook diagnostics card workflows.

## Exit criteria
- Snapshot lookup behavior is well-defined, consistent, and tested.
- Notebook diagnostics examples can rely on documented key semantics without BUG notes.
