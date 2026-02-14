# Issue 003: Cache-control test blocked by `numpify` module shadowing

## Summary
`tests/test_numpify_cache_behavior.py::test_numpify_cache_false_forces_recompile` fails with the same module-shadowing error as Issue 002.

## Analysis
- Error: `AttributeError: 'function' object has no attribute 'numpify_cached'`.
- Root cause matches Issue 002 (`gu_toolkit.numpify` import resolves to function object).
- The functional behavior under test (`cache=False` forcing recompilation) is not being exercised due to import failure.

## Proposed solution
- Fix package namespace collision described in Issue 002.
- Keep this test after fix; it validates important cache semantics.

## Disposition
**Duplicate root cause of Issue 002 (real bug).**
