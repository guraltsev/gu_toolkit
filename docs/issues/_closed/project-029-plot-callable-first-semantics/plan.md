# Project 029: `plot()` Callable-First Semantics Alignment (Plan)

## Goal

Deliver a complete, implementation-ready design package for callable-first `plot()` semantics aligned with `play()` and `NumericFunction`, including migration and testing plans, without touching runtime behavior.

---

## Phase 1 — Contract definition (design)

### 1.1 Public API contract

Define canonical signatures and accepted input forms:

- `plot(f, var_or_range=None, *, vars=None, ...)`
- `var_or_range := Symbol | (Symbol, min, max)`

Document accepted and rejected call families with explicit examples.

### 1.2 Variable binding rules

Specify variable-resolution decision tree:

1. range tuple,
2. explicit symbol,
3. `vars=...`,
4. safe inference for unambiguous unary cases,
5. deterministic ambiguity error otherwise.

### 1.3 Conflict policy

Finalize conflict rules and wording:

- range tuple vs legacy bounds kwargs => hard error,
- malformed tuples => validation error,
- duplicate/contradictory variable sources => hard error.

**Deliverable:** signed-off API contract and conflict matrix.

---

## Phase 2 — NumericFunction/provider semantics (design)

### 2.1 Supported/unsupported provider states

Finalize exact compatibility matrix:

- supported: unfrozen, frozen without provider, provider matching current figure manager,
- unsupported: external provider.

### 2.2 Dynamic-variable conventions

Document how plotting normalization should treat symbols/parameters as dynamic where needed, in line with existing `NumericFunction` conventions.

### 2.3 Provider detachment direction

Specify requirements for a future `NumericFunction` detach/rebind API preserving dynamic-variable behavior, used as migration guidance for provider mismatch cases.

**Deliverable:** provider semantics spec + error and migration guidance.

---

## Phase 3 — Internal architecture blueprint (design)

### 3.1 Normalization helper design

Define canonical `normalize_plot_input(...)` responsibilities and return schema.

### 3.2 Error-construction architecture

Define centralized error factories/messages to guarantee consistency across dispatch paths.

### 3.3 Compatibility adapter design

Define where legacy signature adaptation happens and where deprecation warnings are emitted.

**Deliverable:** implementation blueprint suitable for incremental coding.

---

## Phase 4 — Validation and rollout planning (design)

### 4.1 Test blueprint

Prepare implementation-phase tests:

- positive paths: expression, unary callable inference, explicit multi-var via `vars`, supported `NumericFunction` provider states,
- negative paths: ambiguous inference, malformed tuples, external provider rejection, conflict cases,
- regression coverage for currently supported workflows.

### 4.2 Migration plan

Define phased rollout and deprecation schedule with user messaging.

### 4.3 Documentation plan

Define updates required in API docs/examples to enforce callable-first style.

**Deliverable:** test matrix + migration and documentation checklists.

---

## Proposed work breakdown structure (WBS)

1. API contract and examples.
2. Dispatch/normalization decision tables.
3. Provider compatibility and dynamic-variable semantics.
4. Error catalog with rewrite guidance.
5. Test matrix and migration timeline.

---

## Risks and mitigations

- **Risk:** ambiguity with legacy signatures causes regressions.
  - **Mitigation:** strict normalization boundary + early ambiguity errors + regression tests.
- **Risk:** provider semantics are misunderstood by users.
  - **Mitigation:** explicit mismatch error copy and migration recipes.
- **Risk:** divergence between `plot()` callable handling and `NumericFunction` conventions.
  - **Mitigation:** make `NumericFunction` conventions normative for callable introspection and binding.

---

## Definition of done (design project)

- Complete approved summary and plan docs for project 029.
- Decision log includes conflict policy and provider policy.
- Implementation team can execute without reopening unresolved semantic questions.
