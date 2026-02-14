# Plan: Numeric Callable API Proposal (Design Only)

## Goal

Produce a design-level proposal that unifies numeric callable behavior (freeze semantics, signature mapping, dynamic context) across:

- plain Python callables,
- numpified symbolic expressions,
- optionally `NamedFunction`-based constructs.

> Scope for this project artifact is design and documentation only (no implementation).

---

## Phase 1 — Requirements and invariants

1. Define the invariant semantics that must hold regardless of callable origin:
   - immutable-style updates for `freeze`/`unfreeze`,
   - deterministic binding precedence,
   - explicit missing-parameter errors,
   - stable and inspectable argument ordering.
2. Document unsupported or explicitly deferred cases (e.g., varargs, keyword-only policies).
3. Define context lookup contract for dynamic parameters using mapping semantics.

**Deliverable:** requirements section in proposal RFC.

---

## Phase 2 — API surface design

1. Specify constructor patterns:
   - `NumericFunction(f)`
   - `NumericFunction(f, vars=(...))`
   - `NumericFunction.from_sympy(...)`, etc.
2. Specify binding methods and return types:
   - `freeze`, `unfreeze`, context setters.
3. Specify introspection surface:
   - `vars`, `var_names`, possibly `signature` and metadata flags.
4. Specify helper consumption protocol used by `NIntegrate` and `NReal_Fourier_Series`.

**Deliverable:** concrete API section with examples and edge-case behavior table.

---

## Phase 3 — Compatibility and migration strategy

1. Define relation between `NumpifiedFunction` and `NumericFunction`:
   - subclass, wrapper, or shared mixin/base protocol.
2. Define backward-compatibility commitments for fields currently used in code (`symbolic`, `source`, etc.).
3. Define deprecation strategy, if any:
   - staged warnings,
   - timeline tied to helper migration.

**Deliverable:** migration matrix from old entrypoints to new equivalents.

---

## Phase 4 — Integration design with `NamedFunction`

1. Decide whether `NamedFunction` should expose a direct numeric adapter.
2. Define clear boundary:
   - symbolic expansion concerns remain in `NamedFunction`,
   - parameter freeze semantics remain in numeric wrapper.
3. Provide recommended usage patterns for common workflows.

**Deliverable:** integration note and “when to use what” decision guide.

---

## Phase 5 — Validation and test design (no code yet)

Define a future test plan to validate the design once implemented:

1. Conformance tests for protocol-level behavior across callable origins.
2. Regression tests for freeze/dynamic semantics currently expected from `NumpifiedFunction`.
3. Helper-level tests ensuring `NIntegrate`/Fourier behavior parity.
4. Error ergonomics tests (early validation mode vs deferred runtime mode, if adopted).

**Deliverable:** checklist of required tests and acceptance criteria.

---

## Suggested acceptance criteria for design sign-off

- A reviewer can map any supported callable origin to a single binding model.
- Freeze/unfreeze and dynamic context behavior are specified unambiguously.
- Numeric helper APIs can be specified against a stable protocol instead of concrete classes.
- Backward compatibility impact is explicitly documented with migration recommendations.

---

## Open decisions to resolve before implementation

1. Should `NumericFunction` accept names, symbols, or both as first-class keys?
2. How strict should callable signature validation be for generic callables?
3. Should unresolved parameters fail early by default or only at evaluation time?
4. Should `NamedFunction` become a producer of `NumericFunction` directly, or stay loosely coupled?

---

## Non-goals

- Implementing runtime behavior in this phase.
- Refactoring helper internals in this phase.
- Changing existing behavior without explicit migration plan.
