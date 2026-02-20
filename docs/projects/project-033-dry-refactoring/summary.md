# Project 033: DRY Refactoring

**Status:** Backlog
**Priority:** Medium

## Goal/Scope

Eliminate identified code duplication across the codebase to reduce
maintenance burden and inconsistency risk. This project targets specific
DRY violations found during the code review; it is not a general
refactoring pass.

## Context

The code review identified several concrete duplication sites:

1. **`_resolve_symbol` is implemented three times.** Two nearly identical
   19-line methods exist in `ParameterSnapshot.py` (for
   `ParameterValueSnapshot` and `ParameterSnapshot`), and a third variant
   exists in `numpify.py` as `NumericFunction._resolve_key()`. All three
   convert a string-or-Symbol argument to a canonical Symbol key.

2. **Greek letter data is hardcoded in two locations.** `NamedFunction.py`
   contains a 40-line hardcoded set of Greek letters used in both
   `_get_smart_latex_symbol()` and `_latex_function_name()`. This should
   be a single shared constant.

3. **`_normalize_vars()` in numpify.py accepts 5 input forms.** While
   flexibility for the user-facing API is valuable, the internal
   implementation mixes sequence-of-symbols, dict-with-symbol-keys,
   dict-with-string-keys, dict-with-int-keys, and mixed forms in a single
   100-line function. This can be simplified to accept: (a) a sequence of
   symbols/strings, or (b) a dictionary with number/string/symbol keys —
   and normalize internally to a single canonical representation.

## TODO checklist

- [ ] Extract shared `resolve_symbol(key, symbol_table)` utility from the
      three existing implementations.
- [ ] Replace the three call sites with the shared utility.
- [ ] Extract Greek letter constant set from `NamedFunction.py` to a shared
      location.
- [ ] Simplify `_normalize_vars()` to accept sequence or dict forms, with
      clear canonical output.
- [ ] Add focused unit tests for the extracted utilities.

## Exit criteria

- [ ] Symbol resolution logic exists in exactly one location.
- [ ] Greek letter data is defined once and imported where needed.
- [ ] `_normalize_vars()` input contract is documented and simplified.
- [ ] All existing tests pass without modification (behavior-preserving).

## Dependencies

- Best executed during or after project-023 (Package Reorganization),
  since shared utilities will have a natural home in `core/`.
- Can proceed independently if needed; just place utilities in the
  current flat layout and move them during reorganization.

## Challenges and mitigations

- **Challenge:** The three `_resolve_symbol` variants have subtle
  differences (error messages, fallback behavior).
  **Mitigation:** Parameterize the shared utility (e.g., accept an
  optional error message template); verify behavioral equivalence with
  targeted tests.

- **Challenge:** Simplifying `_normalize_vars()` may break power-user
  call patterns.
  **Mitigation:** Keep the two accepted forms (sequence and dict)
  broad enough to cover real usage; add deprecation warnings for
  exotic forms if any exist.

## Completion Assessment (2026-02-18)

- [ ] `_resolve_symbol` logic still exists in multiple locations (`ParameterSnapshot.py` and `numpify.py`).
- [ ] Greek-letter constant data is still local to `NamedFunction.py` and not extracted to a shared utility module.
- [ ] `_normalize_vars()` remains a large multi-form normalizer in `numpify.py` and has not been simplified per project target.
- [x] Focused tests exist for some normalization behavior (`tests/test_numpify_refactor.py`), but the extraction/simplification scope is incomplete.

**Result:** Project remains **open**.

---

## Coordination update (2026-02-20)

Duplicate-functionality consolidation remains owned by project-033 scope, with execution sequencing and architecture-boundary alignment coordinated through project-037 (`docs/projects/project-037-ownership-boundaries-and-dedup/summary.md`).
