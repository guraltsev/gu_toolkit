# Issue 009: `NIntegrate(..., binding=Figure)` rejected despite documented support

## Summary
`tests/test_prelude_nintegrate.py::test_nintegrate_symbolic_expr_with_smartfigure_binding` fails with `TypeError: binding must be a dict keyed by Symbol or symbol name`.

## Analysis
- `NIntegrate` docstring explicitly lists `Figure` as a supported binding source.
- `_resolve_parameter_values(...)` currently accepts only `None` or `dict`, then raises `TypeError` otherwise.
- This is a direct implementation-doc mismatch.

## Proposed solution
- Extend `_resolve_parameter_values` to accept figure-like bindings by reading `binding.parameters.parameter_context`.
- Optionally accept any mapping-like object and normalize Symbol/name lookup.
- Add/keep tests for both explicit dict and Figure binding paths.

## Disposition
**Real bug (implementation contradicts public API docs).**
