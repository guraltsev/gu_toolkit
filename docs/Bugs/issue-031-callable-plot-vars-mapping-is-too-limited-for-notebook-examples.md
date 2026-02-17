# Issue 031: Variable/parameter convention convergence across `plot()`, `NumericFunction`, and numerical helpers

## Status
Open (implementation and documentation convergence completed; pending external review)

## Summary
State-of-completion checklist:
- [x] `plot(..., vars=...)` now accepts mapping-based forms required by callable-first notebook examples.
- [x] Plotting input normalization reuses shared `numpify._normalize_vars(...)` behavior.
- [x] Regression tests cover string-keyed mapping, mixed index+name mapping, and invalid non-contiguous index mappings.
- [x] Notebook callable example using mapping-based `vars` is now runnable.
- [x] Public API docs now include a single explicit grammar reference shared across plotting and numeric helpers.
- [x] Cross-helper documentation for alias/symbol resolution rules (including `freeze(...)`) is now documented.

## Evidence
- `Figure._normalize_plot_inputs(...)` routes plotting `vars` through shared normalization logic.
- `tests/test_project029_plot_callable_first.py` includes mapping-form regression tests.
- `docs/notebooks/Toolkit_overview.ipynb` includes a runnable callable example with mapping-based `vars`.

## TODO
- [x] Reuse shared vars normalization path for callable-first plotting.
- [x] Expand `plot(..., vars=...)` typing to include mapping variants.
- [x] Add regression tests for success and validation-error mapping forms.
- [x] Add targeted public API reference docs for accepted `vars` grammar.
- [x] Align docs for `plot`, `numpify`, and `freeze` around one shared variable-resolution contract.

## Exit criteria
- [x] A single documented variable-spec grammar is referenced by plotting + numeric APIs.
- [x] `plot(..., vars=...)` accepts mapping and tuple+mapping forms with deterministic validation.
- [x] `freeze(...)` and plot parameter binding are documented with matching symbol/alias resolution rules.
- [x] Notebook callable examples run without bug placeholders or API-specific workarounds.
- [x] Regression suite covers callable-plot mapping behavior.

## Assessment
- Confirmed the notebook source-of-truth example uses mapping-based callable vars (`vars={'x': x, 'A': A, 'k': k[1]}`) and matches the implemented normalization behavior.
- Confirmed regression coverage exists for string-keyed mappings, mixed integer+string mappings, and invalid non-contiguous integer mapping keys.
- No contradiction was found between notebook behavior and code/tests, so no WARNING is required.

## Remediation plan
- [x] Keep callable `plot(..., vars=...)` on shared `numpify._normalize_vars(...)` path.
- [x] Add explicit `vars` grammar documentation to `Figure.plot(...)` public docs.
- [x] Expand `numpify._normalize_vars(...)` docs as the canonical grammar reference.
- [x] Document `NumericFunction.freeze(...)` / `unfreeze(...)` key resolution to align alias/symbol behavior with plotting.
- [x] Re-run callable-first regression tests.

## Implementation checklist
- [x] Updated docs in code for variable-spec grammar and alias resolution contract.
- [x] Verified issue-031 regression tests pass.
- [x] Updated issue tracking checklist and status (kept open for external review).
