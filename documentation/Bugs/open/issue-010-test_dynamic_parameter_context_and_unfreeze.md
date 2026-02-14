# Issue 005: Dynamic parameter context test blocked by module shadowing

## Summary
`tests/test_numpify_refactor.py::test_dynamic_parameter_context_and_unfreeze` fails before execution with `AttributeError: 'function' object has no attribute 'numpify'`.

## Analysis
- Same namespace/import collision as Issue 002.
- Test scenario itself appears valid for `NumpifiedFunction` dynamic binding and unfreeze workflow.

## Proposed solution
- Apply Issue 002 fix.
- Re-run this and related refactor tests to verify runtime behavior.

## Disposition
**Duplicate root cause of Issue 002 (real bug).**
