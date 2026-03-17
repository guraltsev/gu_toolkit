# Issue 010: Unbound callable integration with `binding=Figure` fails

## Summary
`tests/test_prelude_nintegrate.py::test_nintegrate_unbound_callable_with_smartfigure_binding` fails with the same binding type error as Issue 009.

## Analysis
- Call path for unbound callables resolves parameter symbols then delegates to `_resolve_parameter_values`.
- Since figure bindings are rejected there, callable path fails as well.
- This is the same core issue, surfaced through a different expression type.

## Proposed solution
- Implement figure binding support in `_resolve_parameter_values` (Issue 009).
- Confirm this callable path works once binding normalization is fixed.

## Disposition
**Duplicate root cause of Issue 009 (real bug).**


## Closure note (2026-02-14)
Closed because unbound callable integration with Figure binding now passes (`tests/test_prelude_nintegrate.py::test_nintegrate_unbound_callable_with_smartfigure_binding` did not fail).
