# Project 029: `plot()` Callable-First Semantics Alignment (Summary)

**Status:** Implemented
**Type:** Design + runtime implementation

## Objective

Define a complete, implementation-ready design for updating `plot()` so its first-argument semantics align with `play()` and with the `NumericFunction` model, while preserving backward compatibility through a controlled migration path.

This project intentionally does **not** change runtime behavior.

## Final design decisions

### 1) Canonical call model

The canonical user-facing shape is:

- `plot(f, x, ...)`
- `plot(f, (x, xmin, xmax), ...)`
- `plot(f, x, vars=..., ...)` for multi-variable callable/function contexts.

Where `f` is callable-first and variable binding is explicit or safely inferable.

### 2) Supported first-argument categories (`f`)

`plot(f, ...)` supports:

1. Sympy expression.
2. `NumericFunction` (unfrozen).
3. `NumericFunction` (frozen with no provider).
4. `NumericFunction` whose provider is the current figure's parameter manager.
5. Python callable with one positional variable (inference allowed).
6. Python callable with multiple positional variables only when `vars=...` is supplied.

### 3) Explicitly unsupported (for this phase)

- `NumericFunction` with an external provider (provider not equal to this figure's manager).

This must fail with a deterministic, actionable error. The design intentionally blocks this path until a true multi-provider model exists.

### 4) Variable/range precedence and conflict policy

- `(var, min, max)` is a first-class range form.
- Tuple range and `x_domain=` controls are **mutually exclusive**.
- If both are present, raise a meaningful error with exact rewrite guidance.

### 5) Callable arity/introspection policy

Callable positional-variable interpretation follows the same conventions used by `NumericFunction` introspection/normalization. This avoids divergence between `plot()` and `NumericFunction` behavior.

### 6) Provider and dynamic-variable policy

For symbolic expressions and partially frozen/unfrozen `NumericFunction` flows, the plotting pipeline should conceptually normalize to `NumericFunction`, bind symbol arguments, mark plotting-dependent symbols as dynamic (`DYNAMIC`), and register the figure parameter manager as the active provider in the normalized execution context.

To support migration and error recovery, `NumericFunction` should expose a provider-detach/rebind-friendly API that preserves dynamic-variable semantics.

## Dispatch and normalization contract

### Dispatch precedence

1. Sympy expression
2. `NumericFunction`
3. Generic callable
4. Otherwise -> type error listing accepted categories.

### Canonical normalization output (conceptual)

A normalization helper (`normalize_plot_input(...)`) should produce a canonical spec containing:

- function category,
- normalized callable representation,
- resolved plotting variables,
- optional range spec,
- provider-compatibility status,
- normalized sampling/render options,
- warning/deprecation metadata.

All downstream sampling/rendering should consume this canonical spec only.

## Error design contract

Errors must be deterministic and instructive. At minimum each message includes:

- detected input shape,
- exact violated rule,
- one concrete rewrite example.

Dedicated error families:

- unsupported external provider,
- ambiguous variable inference,
- malformed range tuple,
- callable arity mismatch vs `vars`,
- conflicting range declaration sources.

## Compatibility and migration strategy

1. **Documentation phase:** switch examples and docs to callable-first conventions.
2. **Tightening phase:** reject incompatible call shapes consistently.

## Non-goals (this project)

- No runtime implementation.
- No change to multi-provider architecture.
- No broad refactor outside `plot()` input semantics and associated docs/tests planning.

## Exit criteria for design completion

- Approved dispatch precedence and ambiguity policy.
- Approved provider-mismatch error contract.
- Approved canonical normalization schema.
- Approved migration/deprecation plan and test blueprint.


## Implementation notes

- `Figure.plot(...)` and module-level `plot(...)` accept callable-first forms (`plot(f, x, ...)` and `plot(f, (x, xmin, xmax), ...)`).
- Supported first arguments in runtime are: SymPy expressions, `NumericFunction`, and plain Python callables with fixed positional arguments.
- For multi-variable callables/`NumericFunction`, users must provide `vars=...` when variable inference is ambiguous.

## Completion Assessment (2026-02-17)

- [x] Runtime callable-first behavior is implemented (`Figure.plot(...)` and module-level `plot(...)`).
- [x] Regression/acceptance tests for callable-first semantics are present and passing (`tests/test_project029_plot_callable_first.py`).
- [x] Documentation and design notes are updated with callable-first conventions (project summary/plan and docs policy references).
- [x] Exit criteria for this project are satisfied.
- [x] This project is **complete** and can be moved to `docs/projects/_completed/`.

