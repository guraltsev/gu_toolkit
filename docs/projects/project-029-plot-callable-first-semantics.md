# Project 029: `plot()` Callable-First Semantics Alignment

**Status:** Proposed

## Goal/Scope
Design (without implementation) a forward-compatible update to `plot()` so its first-argument semantics align with `play()`:
- callable/expression first, plotting variable second,
- explicit support for range tuples in the form `(var_symbol, min, max)`,
- clear behavior for `NumericFunction` provider ownership,
- predictable dispatch and meaningful errors for unsupported/provider-mismatched cases.

This project is design-only. No runtime/API behavior changes are included in this project.

## Summary of Intended API Semantics
The new `plot()` input model should accept a first argument `f` and infer/resolve plotting variables using either:
1) a second positional variable argument, or
2) a `(var_symbol, min, max)` tuple, or
3) explicit `vars=...` for multi-variable callables.

### Supported `f` (first argument) categories
`plot(f, ...)` should support:
1. **Sympy expression**.
2. **`NumericFunction` (unfrozen)**.
3. **`NumericFunction` (frozen, no provider)**.
4. **`NumericFunction` whose provider is this figure's parameter manager**.
5. **Python callable with exactly one positional variable**.
6. **Python callable with multiple variables** only when `vars=(...)` is provided.

### Explicitly unsupported for now
- **`NumericFunction` with an external provider** (i.e., provider is not this figure's parameter manager) should raise a meaningful, actionable error (or `NotImplementedError` with guidance).

## Proposed Call Shapes (Design Contract)
Primary target forms:
- `plot(f, x)`
- `plot(f, (x, xmin, xmax))`
- `plot(f, vars=(x1, x2, ...), ...)` for multi-variable callable/function contexts

Compatibility notes (design intent):
- Existing forms should be audited and either retained, deprecated, or rejected with clear messaging.
- Ambiguous calls must fail early with a deterministic error explaining how to rewrite the call.

## Dispatch and Resolution Design
### Phase 1: Classify `f`
Establish a strict precedence order:
1. Sympy expression
2. `NumericFunction`
3. Generic callable
4. Otherwise: type error with accepted categories

### Phase 2: Resolve variable binding
Variable resolution decision tree:
1. If second positional arg is `(var, min, max)`, treat as canonical range tuple.
2. Else if second positional arg looks like a single variable symbol, use it as variable.
3. Else if `vars=` provided:
   - required for multi-argument callables,
   - validated for arity and symbol normalization.
4. Else infer only when unambiguous (single free symbol / unary callable).
5. Else raise informative ambiguity error.

### Phase 3: Provider compatibility checks (`NumericFunction` only)
- `unfrozen`: supported.
- frozen with no provider: supported.
- provider bound to current figure parameter manager: supported.
- provider bound elsewhere: unsupported in this phase; raise explicit error.

Error messaging should include:
- detected provider identity/context,
- expected provider context,
- short migration hint (e.g., rebind/unfreeze/recreate in current figure context).

## API Surface and Signature Evolution (Design)
Candidate signature direction (illustrative):
- `plot(f, var_or_range=None, *, vars=None, ...)`

Where:
- `var_or_range` accepts either `Symbol` or `(Symbol, min, max)`.
- `vars` is reserved for explicit multi-variable binding.

Design constraints:
- Avoid introducing positional argument ambiguity with existing optional parameters.
- Prefer keyword-only expansion for new controls.
- Ensure internal normalization converts all accepted inputs into one canonical spec object before sampling/rendering.

## Internal Architecture Plan (No Code Yet)
1. Introduce a normalization helper concept (e.g., `normalize_plot_input(...)`) returning a canonical structure:
   - function kind
   - resolved variable list
   - optional range specification
   - provider validation result
2. Keep provider-validation logic isolated for easier future enablement of cross-provider support.
3. Centralize error construction so all unsupported/ambiguous cases share consistent guidance.

## Validation and Test Blueprint
Design-time acceptance tests to add during implementation phase:

### Positive coverage
- Sympy expression with explicit variable.
- Sympy expression with `(var, min, max)`.
- Unary callable without `vars` (infer).
- Multi-arg callable with explicit `vars`.
- Supported `NumericFunction` variants listed above.

### Negative coverage
- Multi-arg callable without `vars` -> explicit guidance error.
- `NumericFunction` with external provider -> not-implemented/provider-mismatch error.
- Ambiguous variable inference cases -> deterministic ambiguity error.
- Malformed range tuple (wrong arity/type/order) -> validation error.

### Regression coverage
- Existing supported `plot()` and `play()` workflows remain intact or emit explicit deprecation notices where intended.

## Migration and Compatibility Strategy
- Phase A: Add compatibility layer + warnings where legacy call patterns overlap.
- Phase B: Switch docs/examples to callable-first style.
- Phase C: tighten/retire ambiguous legacy forms after deprecation window.

## Open Questions
- Should `(var, min, max)` take precedence over legacy `min/max` kwargs when both are present, or be mutually exclusive?
- For callable introspection, what is the exact accepted definition of "positional variable" with defaults/`*args`?
- Should external-provider `NumericFunction` errors suggest a concrete helper API (if available) to rebind provider?

## TODO checklist
- [ ] Confirm and document canonical `plot()` signature for transition period.
- [ ] Specify exact dispatch precedence in developer docs.
- [ ] Define canonical internal normalized input schema.
- [ ] Draft user-facing errors for each unsupported/ambiguous case.
- [ ] Specify deprecation policy for legacy argument orders.
- [ ] Add implementation-phase tests per validation blueprint.
- [ ] Update user docs/examples to callable-first style once implementation starts.

## Exit criteria
- [ ] Design is approved with explicit dispatch precedence and ambiguity policy.
- [ ] Unsupported external-provider behavior is documented with exact error contract.
- [ ] Implementation blueprint and test plan are detailed enough for phased delivery.
- [ ] Migration/deprecation path is explicit and reviewed.
