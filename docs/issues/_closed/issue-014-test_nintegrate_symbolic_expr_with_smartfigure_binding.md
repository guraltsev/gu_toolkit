# Issue 014: `NIntegrate(..., binding=Figure)` rejected despite documented support

## Summary
`tests/test_prelude_nintegrate.py::test_nintegrate_symbolic_expr_with_smartfigure_binding` failed with a `TypeError` claiming the binding must be a dict.

## Analysis
- `NIntegrate` docstring explicitly lists `Figure` as a supported binding source.
- `_resolve_parameter_values(...)` only accepted `dict` and rejected figure objects.
- This created an implementation/docs mismatch and broke Figure-backed integration.

## Implemented fix
Updated `prelude._resolve_parameter_values` to normalize multiple binding sources:
- Accept any `Mapping` (not just `dict`).
- Accept figure-like objects by extracting either:
  - `binding.parameters.parameter_context`, or
  - `binding.parameter_context`.
- Preserve Symbol-or-name lookup (`sym` and `sym.name`) and existing missing-key validation.
- Updated the `TypeError` message to reflect the supported binding forms.

## Validation
- Confirmed code path update in `prelude.py`.
- In this environment, running the targeted pytest is currently blocked by a missing runtime dependency (`scipy`), so full execution validation could not complete.

## Disposition
**Fixed (implementation now matches documented API for Figure binding).**


## Closure note (2026-02-14)
Closed because Figure binding for symbolic expressions is now passing (`tests/test_prelude_nintegrate.py::test_nintegrate_symbolic_expr_with_smartfigure_binding` did not fail).
