# Issue 031: Variable/parameter convention convergence across `plot()`, `NumericFunction`, and numerical helpers

## Status
Open (partially remediated; implementation merged pending external review)

## Summary
`plot(..., vars=...)` was too restrictive for callable-first notebook examples because it only accepted symbols/sequences. The notebook demonstrates mapping-based `vars` usage (`{'x': x, 'A': A, 'k': k[1]}`), so this issue tracks convergence between plotting and numeric-callable variable conventions.

## Evidence
### Notebook source of truth check
- `docs/notebooks/Toolkit_overview.ipynb` still includes a `#BUG` note stating `plot` should accept string-keyed dictionaries and mixed index+name mapping for callable vars.
- The same notebook cell includes a callable plot example with `vars={'x':x, 'A':A,'k':k[1]}`.

⚠️ **WARNING (notebook contradiction):** current code now implements mapping-based `vars` in `plot(...)`, but the notebook still documents this as a bug placeholder. Per workflow, notebook files were not edited automatically and need explicit follow-up review/update.

### Code-state assessment before fix
- `Figure._normalize_plot_inputs(...)` previously typed `vars` as `Optional[Union[Symbol, Sequence[Symbol]]]` and rejected mapping forms.
- `numpify._normalize_vars(...)` already supported mapping and tuple+tail-mapping grammar, creating divergence between `plot` and `numpify` workflows.

### Remediation implemented
- `Figure._normalize_plot_inputs(...)` now routes `vars` through shared `numpify._normalize_vars(...)` logic, enabling accepted mapping forms and consistent validation semantics.
- `Figure.plot(...)` and module-level `plot(...)` now type `vars` using a shared `PlotVarsSpec` alias that includes mapping forms.
- Callable-first `plot` now preserves and reuses normalized vars specification when constructing/rebinding `NumericFunction`.

### Regression tests added
- string-keyed mapping form for callable-first `plot` (`{"x": x, "A": A, "k": k}`)
- mixed index+string mapping form (`{0: x, "a": a}`)
- validation failure for non-contiguous integer mapping keys (`{0: x, 2: a}`)

## TODO
- [x] Assess issue completion status against notebook examples.
- [x] Emit contradiction warning where notebook bug marker no longer matches implementation.
- [x] Reuse shared vars normalization path for callable-first plotting.
- [x] Expand `plot(..., vars=...)` typing to include mapping variants.
- [x] Add regression tests for success and validation-error mapping forms.
- [ ] Update notebook bug marker and narrative after external review approval.
- [ ] Add targeted docs text in public API reference for `plot(..., vars=...)` accepted grammar.

## Exit criteria
- [ ] A single documented `VariableSpec` grammar is referenced by plotting + numeric APIs.
- [x] `plot(..., vars=...)` accepts mapping and tuple+mapping forms with deterministic validation.
- [ ] `freeze(...)` and plot parameter binding use the same symbol/alias resolution rules across all helper APIs.
- [ ] Notebook callable examples run with no bug placeholders and no API-specific workarounds.
- [x] Regression suite covers callable-plot mapping behavior.

## Implementation checklist (this change set)
- [x] Implement `plot` vars mapping support using shared vars normalization.
- [x] Preserve callable rebinding behavior when explicit plotting variable differs from callable arg names.
- [x] Add tests for mapping happy paths and key-validation failure.
- [x] Keep issue open pending external review.
