# Project 020: Numeric Callable API (Implemented)

## Implementation audit status

This project is **partially implemented**, but not yet fully complete against the full plan.

### Still TODO

1. **Complete internal migration to `NumericFunction` (Phase 3.1).**
   - Core modules still type/import against `NumpifiedFunction` in several places (for example: `Figure.py`, `figure_plot.py`, and `numeric_operations.py`).
2. **Complete public narrative replacement (Phase 3.3).**
   - Several docs and internal review notes still describe behavior primarily in `NumpifiedFunction` terms.
3. **Post-migration cleanup (Phase 4).**
   - Transitional compatibility surface has not been reduced yet (`NumpifiedFunction` remains part of runtime and dependent typing paths), and no cleanup pass has been documented.

## What shipped

This project is now implemented with `NumericFunction` as the canonical numeric callable API and a compatibility `NumpifiedFunction` constructor.

### Core behavior

1. `numpify(...)` now returns `NumericFunction`.
2. `NumpifiedFunction` remains available as a compatibility subclass/constructor.
3. Legacy construction defaults `symbolic=None` when omitted.
4. Freeze/unfreeze, dynamic parameter context, and call-signature behavior are shared through the same runtime class.

## Unified `vars` contract

`vars` now supports the proposal forms:

1. **Pure positional**
   - `vars=(x, y)`
2. **Positional + keyed tail mapping**
   - `vars=(x, {"y": y, "scale": s})`
3. **Pure keyed mapping**
   - `vars={"x": x, "scale": s}`
4. **Indexed positional mapping + keyed mapping**
   - `vars={0: x, 1: y, "scale": s}`

Validation rules implemented:

- Integer keys must be contiguous from `0` with no gaps.
- Non-integer mapping keys must be strings.
- Duplicate symbols in the normalized contract are rejected.

## Round-trip behavior

`NumericFunction.vars` is now a compatibility accessor with two modes:

- Iteration/indexing (`tuple(fn.vars)`) exposes positional symbols for legacy compatibility.
- Calling (`fn.vars()`) returns the original normalized vars specification for round-trip reconstruction.

## Test coverage added

`tests/test_numeric_callable_api.py` covers:

- `numpify` return type and `symbolic` payload.
- legacy compatibility construction defaults.
- mixed positional+keyed calling.
- integer-key mapping behavior and contiguity validation.
- freeze/unfreeze parity across canonical and compatibility construction.

## Audit notes

- Phase 1 and Phase 2 deliverables are implemented and covered by tests.
- Full completion is currently blocked on Phase 3/4 migration and cleanup work above.
