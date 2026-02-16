# Plan: Numeric Callable API Proposal

## Goal

Adopt `NumericFunction` as the canonical numeric callable abstraction and retire legacy `NumpifiedFunction` compatibility code.

---

## Phase 1 — API contract finalization ✅

1. Finalized constructor/factory contract:
   - `NumericFunction(f, vars=...)`
   - `numpify(...) -> NumericFunction(symbolic=<expr>)`
2. Finalized accepted `vars` forms:
   - tuple positional,
   - tuple positional + trailing mapping,
   - pure mapping,
   - mapping with integer positional keys (`0..n-1`) plus keyed names.
3. Finalized normalization/validation rules:
   - integer key contiguity,
   - collision handling,
   - deterministic ordering.

---

## Phase 2 — Implementation and testing ✅

1. Implemented `NumericFunction` runtime behavior for binding, freeze/unfreeze, context, and `vars()` round-trip.
2. Updated `numpify(...)` to return `NumericFunction` with `symbolic` payload.
3. Added tests covering:
   - all `vars` input modes,
   - constructor defaults,
   - `numpify` return type and symbolic payload,
   - dynamic context behavior,
   - freeze/unfreeze workflows.

---

## Phase 3 — Replacement and cleanup ✅

1. Migrated internal helper consumers and dependent modules to target `NumericFunction` directly.
2. Removed direct `NumpifiedFunction` compatibility usage and exports.
3. Updated documentation and examples to use `NumericFunction` as the public narrative.

---

## Deliverable

Stable post-migration baseline with `NumericFunction` as the sole supported numeric callable API.
