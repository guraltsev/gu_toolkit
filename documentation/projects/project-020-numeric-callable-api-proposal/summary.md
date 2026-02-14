# Proposal: Unified API for Numeric Callables

## Context

The current direction is to make `NumericFunction` the primary callable wrapper for numeric workflows, including freeze/unfreeze behavior and dynamic parameter-context lookup. A compatibility constructor `NumpifiedFunction` may remain temporarily, but it should delegate to the same core behavior.

## Requested direction (applied)

1. Replace `NumpifiedFunction` as the primary concept with `NumericFunction`.
2. Keep compatibility behavior where legacy `NumpifiedFunction` defaults to `symbolic=None`.
3. Ensure `numpify(...)` returns a `NumericFunction` instance with `symbolic` populated.
4. Define one `vars` contract for constructor input and `NumericFunction.vars()` output/round-trip behavior.
5. Avoid legacy label terminology in the API.

## Unified `vars` contract

`vars` supports positional identifiers, keyed identifiers, or mixed mode:

1. **Pure positional**
   - `vars=(symbol_a, symbol_b, ...)`
2. **Positional followed by keyed entries**
   - `vars=(symbol_a, symbol_b, {"key_z": symbol_z})`
3. **Pure keyed**
   - `vars=({"key_a": symbol_a, "key_b": symbol_b})`
   - `vars={"key_a": symbol_a, "key_b": symbol_b}`
4. **Indexed positional via mapping keys**
   - numeric keys starting at `0` define positional order,
   - non-numeric keys define keyed arguments.
   - Example: `vars={0: symbol_a, 1: symbol_b, "scale": symbol_s}`.

`NumericFunction.vars()` should emit the same structure class that was supplied at creation (tuple/mapping shape preserved where feasible) so reconstruction is straightforward.

## Compatibility stance

- `NumericFunction` is the canonical type for new code.
- `NumpifiedFunction` remains as a compatibility constructor/alias during migration.
- Legacy construction should behave as:
  - `NumpifiedFunction(..., symbolic=<omitted>)` ⇒ `symbolic=None`.
- `numpify(expr, vars=...)` should produce `NumericFunction(..., symbolic=expr)`.

## Issues and shortcomings in the requested instructions

1. **Tension between replacement and continued constructor definition**
   - The request asks to replace `NumpifiedFunction` with `NumericFunction`, but also specifies fresh constructor behavior for `NumpifiedFunction`. This implies a transitional period rather than immediate full removal.
2. **Round-trip fidelity for `vars()` can be ambiguous**
   - If users pass semantically equivalent but structurally different forms (for example tuple+mapping tail vs flat mapping with integer keys), exact shape preservation may require storing original input verbatim.
3. **Indexed mapping edge cases need strict rules**
   - The instruction says numeric keys start at `0`, but does not define behavior for gaps (`{0: a, 2: b}`), duplicates via mixed tuple+mapping input, or non-integer numeric-like keys.
4. **Pure keyed mode examples should avoid empty mapping unless explicitly intentional**
   - `vars=({})` / `vars={}` is valid syntax but not useful unless the callable truly has no declared parameters. This should be documented as a special-case form.

## Recommendation

Proceed with a two-step migration:

1. implement and validate `NumericFunction` + compatibility constructor behavior,
2. then complete the symbolic/legacy replacement once helper integrations and downstream usage are updated.
