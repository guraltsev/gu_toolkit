# Issue 031: Variable/parameter convention convergence across `plot()`, `NumericFunction`, and numerical helpers

## Status
Open (implementation complete, documentation convergence still pending)

## Summary
State-of-completion checklist:
- [x] `plot(..., vars=...)` now accepts mapping-based forms required by callable-first notebook examples.
- [x] Plotting input normalization reuses shared `numpify._normalize_vars(...)` behavior.
- [x] Regression tests cover string-keyed mapping, mixed index+name mapping, and invalid non-contiguous index mappings.
- [x] Notebook callable example using mapping-based `vars` is now runnable.
- [ ] Public API docs still lack a single explicit grammar reference shared across plotting and numeric helpers.
- [ ] Cross-helper documentation for alias/symbol resolution rules (including `freeze(...)`) is still incomplete.

## Evidence
- `Figure._normalize_plot_inputs(...)` routes plotting `vars` through shared normalization logic.
- `tests/test_project029_plot_callable_first.py` includes mapping-form regression tests.
- `docs/notebooks/Toolkit_overview.ipynb` includes a runnable callable example with mapping-based `vars`.

## TODO
- [x] Reuse shared vars normalization path for callable-first plotting.
- [x] Expand `plot(..., vars=...)` typing to include mapping variants.
- [x] Add regression tests for success and validation-error mapping forms.
- [ ] Add targeted public API reference docs for accepted `vars` grammar.
- [ ] Align docs for `plot`, `numpify`, and `freeze` around one shared variable-resolution contract.

## Exit criteria
- [ ] A single documented variable-spec grammar is referenced by plotting + numeric APIs.
- [x] `plot(..., vars=...)` accepts mapping and tuple+mapping forms with deterministic validation.
- [ ] `freeze(...)` and plot parameter binding are documented with matching symbol/alias resolution rules.
- [x] Notebook callable examples run without bug placeholders or API-specific workarounds.
- [x] Regression suite covers callable-plot mapping behavior.
