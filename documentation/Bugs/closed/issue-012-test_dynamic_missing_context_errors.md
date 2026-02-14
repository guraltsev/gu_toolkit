# Issue 007: Missing-context error test blocked by module shadowing

## Summary
`tests/test_numpify_refactor.py::test_dynamic_missing_context_errors` fails with `AttributeError: 'function' object has no attribute 'numpify'`.

## Analysis
- Same import collision as Issue 002.
- Test intent (clear error when dynamic parameters are used without context) remains valuable.

## Proposed solution
- Fix package `numpify` namespace handling (Issue 002).
- Re-run to verify user-facing error message remains stable.

## Disposition
**Duplicate root cause of Issue 002 (real bug).**


## Closure note (2026-02-14)
Closed because `tests/test_numpify_refactor.py::test_dynamic_missing_context_errors` passed in the provided suite output.
