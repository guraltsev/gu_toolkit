# Project 020: Numeric Callable API (Completed)

## Completion status

This project is **fully implemented and cleaned up**.

## Delivered outcomes

### Canonical API

- `NumericFunction` is the only supported numeric callable class.
- `numpify(...)` / `numpify_cached(...)` return `NumericFunction`.
- Legacy `NumpifiedFunction` compatibility paths were removed from runtime and public exports.

### Unified `vars` contract

`vars` supports all proposed forms:

1. `vars=(x, y)`
2. `vars=(x, {"y": y, "scale": s})`
3. `vars={"x": x, "scale": s}`
4. `vars={0: x, 1: y, "scale": s}`

Validation guarantees:

- integer keys are contiguous from `0`,
- non-integer mapping keys are strings,
- duplicate symbols are rejected,
- normalized argument naming is deterministic and collision-safe.

### Runtime behavior

- freeze/unfreeze behavior is implemented directly on `NumericFunction`.
- dynamic parameter-context evaluation is supported via `set_parameter_context(...)` and `DYNAMIC_PARAMETER`.
- `vars` remains backward-friendly as tuple-like iterable, while `vars()` returns the round-trip spec.
- signature introspection tracks currently free variables.

### Comprehensive tests

The numeric callable suite covers:

- constructor and return-type contract,
- all supported `vars` modes,
- keyed/positional calling validation,
- dynamic context and freeze/unfreeze workflows,
- free-variable/signature tracking,
- vectorized execution behavior.

## Implemented change log (since `2132b4463f4333bfb878c321872f1e098c08e9ae`)

- `607667b`: completed the migration baseline by updating runtime consumers and expanding NumericFunction-focused tests (`numpify.py`, `Figure.py`, `figure_plot.py`, `numeric_operations.py`, `tests/test_numeric_callable_api.py`).
- `17f293a`: removed the remaining `NumpifiedFunction` compatibility surface from public exports and aligned docs/tests with the new canonical API (`__init__.py`, `numpify.py`, `tests/test_numeric_callable_api.py`, `tests/test_numpify_refactor.py`, and related documentation updates).
- `081aaea`: finalized project-020 planning/summary documentation with completion status.

Project 020 is fully complete and has been moved under `documentation/projects/_completed/`.
