# Proposal: Unified API for Numeric Callables

## Context

The current numeric stack has strong behavior in `NumpifiedFunction` (especially freeze/unfreeze and dynamic parameter-context semantics), but that capability is not yet uniformly available when users start from plain Python callables. At the same time, `NamedFunction` already provides a symbolic/numeric duality pattern that is conceptually adjacent to the same problem.

This proposal explores a unified abstraction tentatively called **`NumericFunction`** that:

1. preserves the strong binding semantics of `NumpifiedFunction`,
2. accepts non-symbolic callables directly,
3. optionally bridges symbolic-aware workflows (`numpify`, `NamedFunction`) under one model.

## Inputs reviewed

- `documentation/Discussions/numerical_helper_review.md`
- `NamedFunction.py`
- `numpify.py` and `prelude.py` (for current runtime behavior)

## What works well in the current design

1. **Freeze semantics are already useful and composable** (`freeze`, `unfreeze`, dynamic bindings, immutable-style cloning).
2. **Numeric helper resolution is centralized** (`_resolve_numeric_callable`), reducing divergence between integration and Fourier paths.
3. **Named symbolic/numeric interfaces exist already** in `NamedFunction`, proving that users value explicit symbolic and numeric channels.

## Gaps motivating a new API

1. **Plain callable ergonomics are limited** in numeric helpers:
   - multi-argument callables are intentionally rejected in generic mode,
   - `freeze` is blocked for plain callable inputs.
2. **Protocol and binding behavior differs by entrypoint**:
   - symbolic → `numpify` → `NumpifiedFunction` gets rich behavior,
   - plain callable path gets a constrained subset.
3. **Naming no longer matches scope**:
   - “NumpifiedFunction” implies symbolic compilation origin,
   - but many desired semantics are origin-agnostic callable semantics.
4. **Potential conceptual overlap with `NamedFunction`**:
   - both define callable metadata and dual execution paths,
   - users need one coherent story.

## Proposed API direction

### 1) Introduce a generalized callable wrapper: `NumericFunction`

- Construction:
  - `nf = NumericFunction(f)`
  - `nf = NumericFunction(f, args=["x", "a", "z"])`
  - `nf = NumericFunction(f, args={"x": x, "a": a, "z": z})` (symbol-aware mode)
- Behavior:
  - Supports `freeze`, `unfreeze`, dynamic parameters, parameter-context binding.
  - Maintains explicit call signature (`vars`, `var_names`, possibly inspectable signature).
  - Works whether origin is symbolic (`numpify`) or plain numeric callable.

### 2) Reposition `NumpifiedFunction` as one producer, not the semantic center

- Keep numpification-specific concerns separate:
  - `symbolic` expression storage,
  - code generation source caching,
  - SymPy-specific metadata.
- Move generic binding/call protocol into shared base behavior (name TBD):
  - `BoundNumericCallable`, `ParametricCallable`, or directly `NumericFunction`.

### 3) Provide explicit adapters instead of magic

- `NumericFunction.from_sympy(expr, vars=...)`
- `NumericFunction.from_numpified(nf)`
- `NumericFunction.from_named_function(F, args=...)`

This keeps migration obvious and avoids brittle runtime inference.

## Strengths of this direction

1. **Single mental model** across symbolic and non-symbolic callables.
2. **Feature parity** for freeze semantics regardless of callable origin.
3. **Better API discoverability** (users can start from any callable).
4. **Clear extension path** for numeric helpers (`NIntegrate`, `NReal_Fourier_Series`) to depend on one protocol.
5. **Natural bridge to `NamedFunction`** without forcing symbolic expansion for every use case.

## Weaknesses / risks / open questions

1. **Signature ambiguity for Python callables**
   - positional-only, defaults, varargs, keyword-only parameters need strict policy.
2. **Symbol identity vs name identity**
   - if both strings and symbols are accepted, collision and canonicalization rules must be explicit.
3. **Protocol complexity creep**
   - over-generalizing dynamic context lookup can make errors less legible.
4. **Backward compatibility concerns**
   - existing code may depend on current `NumpifiedFunction` attributes (`symbolic`, `source`, etc.).
5. **`NamedFunction` integration boundary**
   - not every `NamedFunction` should necessarily auto-become numeric in all contexts.

## Recommended compatibility posture

- **Do not remove `NumpifiedFunction` immediately.**
- Introduce `NumericFunction` as additive.
- Make `numpify(...)` return a `NumericFunction`-compatible object (or subclass) while preserving old attributes.
- Deprecate only after helper APIs (`NIntegrate`, Fourier, plotting helpers) can consume the new protocol end-to-end.

## Suggested minimal protocol for numeric helpers

Any object consumed by numeric helpers should provide:

- `__call__(*args)`
- `freeze(bindings=None, **kwargs)`
- `unfreeze(*keys)`
- `vars` and `var_names`
- optional `set_parameter_context(ctx)` / `remove_parameter_context()`

If helpers target this protocol, they can stay origin-agnostic.

## Practical guidance on the starter idea

Your starter idea is strong in two places:

- `nf = NumericFunction(f)` is the right ergonomic default.
- `nf(symbol_x, symbol_a, symbol_z)` as signature declaration mirrors SymPy-style explicitness.

Main refinement needed:

- Prefer **declarative signature at construction or via explicit binder methods** over overloading `__call__` for signature declaration, to avoid confusion between “configure callable” and “evaluate callable”.

Example alternatives:

- `nf = NumericFunction(f).bind_vars(x, a, z)`
- `nf = NumericFunction(f, vars=(x, a, z))`
- `nf = NumericFunction(f, names=("x", "a", "z"))`

## Conclusion

A generalized numeric-callable abstraction is a high-value direction. The strongest path is to **extract reusable freeze/binding semantics from `NumpifiedFunction` into an origin-agnostic `NumericFunction` protocol and adapter layer**, while keeping symbolic compilation features as optional enrichments rather than required identity.
