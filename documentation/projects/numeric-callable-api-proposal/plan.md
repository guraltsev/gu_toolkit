# Plan: Numeric Callable API Proposal

## Goal

Adopt `NumericFunction` as the canonical numeric callable abstraction while preserving migration safety for legacy `NumpifiedFunction` usage.

---

## Phase 1 — API contract finalization

1. Finalize constructor and factory contract:
   - `NumericFunction(f, vars=...)`
   - `numpify(...) -> NumericFunction(symbolic=<set>)`
   - compatibility `NumpifiedFunction(..., symbolic=None by default)`
2. Finalize accepted `vars` forms:
   - tuple positional,
   - tuple positional + trailing mapping,
   - pure mapping,
   - mapping with integer keys (`0..n-1`) for positional slots and non-integer keys for keyed slots.
3. Define normalization and validation rules:
   - integer key contiguity,
   - collision handling,
   - deterministic ordering.

**Deliverable:** locked API spec and behavior table.

---

## Phase 2 — Implementation and testing

1. Implement `NumericFunction` runtime behavior for binding, freeze/unfreeze, context, and `vars()` round-trip.
2. Implement compatibility constructor `NumpifiedFunction` with default `symbolic=None` delegating to the new core behavior.
3. Update `numpify(...)` to return `NumericFunction` with `symbolic` set.
4. Add tests covering:
   - all `vars` input modes,
   - constructor defaults,
   - `numpify` return type and symbolic payload,
   - freeze/unfreeze parity across direct and compatibility construction.

**Deliverable:** merged implementation and passing test suite.

---

## Phase 3 — Complete replacement of `NumpifiedFunction`

1. Migrate internal helper consumers and dependent modules to target `NumericFunction` directly.
2. Remove or hard-deprecate direct `NumpifiedFunction` usage paths once compatibility window closes.
3. Update documentation and examples so `NumericFunction` is the only primary public narrative.

**Deliverable:** full replacement completed, with migration notes.

---

## Phase 4 — Post-migration cleanup

1. Remove transitional shims that are no longer required.
2. Audit docs for legacy terminology drift.
3. Verify downstream integrations remain stable after cleanup.

**Deliverable:** stable post-migration baseline.
