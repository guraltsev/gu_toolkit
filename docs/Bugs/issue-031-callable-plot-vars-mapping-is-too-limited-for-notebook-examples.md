# Issue 031: Variable/parameter convention convergence across `plot()`, `NumericFunction`, and numerical helpers

## Status
Open (reframed as convergence work)

## Why this issue is being reframed
The original bug statement focused only on `plot(..., vars=...)` not accepting mapping-based binding used in notebook examples. That is real, but too narrow.

Code inspection shows we currently have **multiple partially-overlapping conventions** for variables/parameters:
- `plot()` callable-first normalization in `Figure.py` accepts only `Symbol` or `Sequence[Symbol]` for `vars`, then treats ordering as positional-only.
- `NumericFunction`/`numpify` already support richer variable specifications (`Symbol`, tuple/list, mapping with integer and string keys, and tuple+tail-mapping hybrid), with keyed aliases that also participate in `freeze(...)`.
- Numerical helpers (`NIntegrate`, Fourier helpers) rely on `NumericFunction` and `freeze` semantics, so divergence in variable conventions creates inconsistent user expectations between plotting and non-plotting workflows.

Therefore this should be tracked as a **convergence issue**: one variable/parameter model used consistently across plotting, compiled numeric callables, and helper APIs.

## Current behavior analysis
### 1) `plot(..., vars=...)` (callable-first path)
- `Figure._normalize_plot_inputs(...)` currently types `vars` as `Optional[Union[Symbol, Sequence[Symbol]]]`.
- Mapping forms (e.g. `{"x": x, "A": A, 0: x}` or tuple+tail-mapping) are rejected by construction.
- For plain callables, argument symbols are inferred from Python signature names and immediately converted to positional symbols; keyed argument intent is lost.

### 2) `NumericFunction` and `numpify`
- `_normalize_vars(...)` in `numpify.py` supports:
  - single symbol,
  - iterable positional symbols,
  - mapping with contiguous integer keys for positional arguments,
  - mapping with string keys for keyed aliases,
  - tuple/list positional symbols with optional tail mapping for aliases.
- `NumericFunction.freeze(...)` accepts bindings by symbol, symbol name, or keyed alias.
- `NumericFunction.unfreeze(...)` and dynamic bindings (`DYNAMIC_PARAMETER`) depend on stable symbol identity and alias lookup.

### 3) Cross-feature mismatch symptoms
- Notebook callable examples that need explicit name/index mapping cannot be represented directly in `plot(...)` even though `NumericFunction` can represent them.
- Users switching between `numpify(..., vars=...)` and `plot(..., vars=...)` face incompatible mental models.
- `freeze(...)` looks like a general parameter-binding convention elsewhere, but plot-side variable binding is still narrower and mostly positional.

## Proposed common convention (normative target)
Adopt a single **VariableSpec** contract and use it everywhere we accept `vars=`:

```python
VariableSpec :=
    Symbol
  | Sequence[Symbol]
  | Mapping[int | str, Symbol]
  | Sequence[Symbol | Mapping[str, Symbol]]   # tuple/list + optional tail mapping
```

### Semantics
1. **Symbol identity is canonical**
   - Runtime parameter binding is always by symbol identity internally.
   - Names/aliases are ergonomics only.

2. **Two binding channels**
   - **Positional channel**: ordered symbols (explicit sequence or integer mapping keys `0..n-1`).
   - **Keyed channel**: string keys that alias symbols.

3. **Deterministic precedence and validation**
   - Positional order is deterministic from explicit sequence or integer keys.
   - Keyed aliases must be unique.
   - Duplicate symbol appearance across channels is invalid.
   - Integer mapping keys must be contiguous starting at 0.

4. **`freeze(...)` alignment rule**
   - Any symbol that can be referenced via `vars=` must be bindable in `freeze(...)` by:
     - symbol object,
     - symbol name,
     - keyed alias (if declared).

5. **Plot-variable selection rule**
   - `plot_var` must resolve to one symbol in the normalized positional channel.
   - remaining normalized symbols become parameter candidates.
   - keyed aliases do not create new symbols; they only name existing symbols.

## Scope of convergence work
This issue now coordinates the following tracks:

1. **API surface alignment**
   - Expand `plot(..., vars=...)` typing/normalization to accept full `VariableSpec`.
   - Ensure callable-first and expression-first paths share the same normalized variable model.

2. **`NumericFunction` as reference model**
   - Treat `numpify._normalize_vars(...)` + `NumericFunction.freeze/unfreeze` behavior as the baseline.
   - Reuse/adapt normalization utilities rather than re-inventing separate plot-only logic.

3. **Error-model consistency**
   - Harmonize error messages across `plot`, `numpify`, and helper APIs for:
     - unknown keyed names,
     - non-contiguous integer mapping,
     - duplicate symbol bindings,
     - ambiguous/missing plotting variable.

4. **Notebook and docs convergence**
   - Update notebook examples to demonstrate one endorsed convention.
   - Remove bug placeholders that suggest unsupported forms once convergence lands.

## Implementation plan (convergence-oriented)
- [ ] Introduce shared variable normalization helper (or expose existing one) consumable by plotting code.
- [ ] Update `Figure._normalize_plot_inputs(...)` to parse full `VariableSpec` and preserve keyed alias metadata where needed.
- [ ] Add plot tests for mapping/index/name success/failure paths and parity with `NumericFunction` behavior.
- [ ] Add cross-feature tests proving that the same `vars` declaration behaves consistently in:
  - `numpify(...)`,
  - `plot(...)`,
  - numerical helpers using `freeze(...)`.
- [ ] Update notebook examples and developer docs with canonical patterns.

## Exit criteria
- [ ] A single documented `VariableSpec` grammar is referenced by plotting + numeric APIs.
- [ ] `plot(..., vars=...)` accepts mapping and tuple+mapping forms with deterministic validation.
- [ ] `freeze(...)` and plot parameter binding use the same symbol/alias resolution rules.
- [ ] Notebook callable examples run with no bug placeholders and no API-specific workarounds.
- [ ] Regression suite covers convergence behavior (not only isolated plot behavior).
