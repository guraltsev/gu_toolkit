# Project 036: Figure Orchestrator Separation and Concern Boundaries

## Status

**Planning (requirements clarified with comments/answers incorporated)**

## Goal/Scope

Restructure the `Figure` architecture so `Figure.py` is a thin orchestrator with explicit, stable boundaries. The primary objective is not line-count reduction; it is durable **separation of concerns**, clearer ownership, and lower regression risk during future feature work.

This project includes:
- decomposition of mixed responsibilities still living in `Figure.py`,
- definition of explicit ownership boundaries for plot lifecycle, render lifecycle, view lifecycle, UI synchronization, and facade ergonomics,
- explicit collaborator contracts that the orchestrator composes,
- requirement-level guidance that can be converted into a concrete implementation `plan.md`.

This project does **not** include implementation in this document.

## Summary of design

### Current-state analysis (problem statement)

The request to separate concerns is valid. Current `Figure.py` still centralizes too many responsibilities in one class:
- API normalization and policy decisions are interleaved with lifecycle mutation.
- Rendering policy, scheduling/debouncing triggers, relayout handling, and diagnostics are coupled.
- View state transitions and widget-facing UI synchronization are blended.
- Facade helpers often contain logic rather than forwarding to subsystem owners.

The practical result is high cognitive load for maintenance and change review: even targeted adjustments (e.g., plot behavior, relayout policy, legend visibility) require editing heavily shared methods and understanding unrelated concerns.

### Architectural direction

Adopt a **workflow-first modularization** that remains concrete and Pythonic:
- `Figure` stays as the call-sequence orchestrator and public facade root.
- Domain logic moves into focused collaborators.
- Interactions use explicit public methods and small return values.
- Avoid command/event object indirection for core flows.

This preserves readability/debuggability while creating maintainable boundaries.

---

## Design decisions (updated with comments/answers)

### 1) `Figure` remains orchestrator-first, not policy-first

`Figure` should keep public signatures and end-to-end call order, but each public method should become a short orchestration script, typically:
1. normalize input,
2. delegate to owning service,
3. request render/update side effects,
4. invoke UI sync adapter if needed,
5. return facade-level result.

`Figure` should not own heavy policy logic where a collaborator can own it.

### 2) `PlotRegistry` is intentionally thin (comment integrated)

`PlotRegistry` owns **collection lifecycle** for plots, including:
- add/update/remove semantics,
- id generation/lookup,
- overwrite behavior,
- routing to create/update paths,
- bookkeeping of plot membership within the figure.

`PlotRegistry` should **not** own parsing policy or parameter-initialization policy.

### 3) Introduce a dedicated parameter/parsing policy collaborator

To enforce separation of concerns:
- a parsing-focused helper/service detects parameter dependencies from plot inputs,
- lifecycle code performs registration/application using explicit defaults and rules,
- parameter detection output should leave room for future metadata enrichment (e.g., source hints, recommended default strategy).

This resolves ambiguity from prior drafts and keeps lifecycle and detection concerns decoupled.

### 4) `RenderEngine` owns render policy and synchronous render operations

`RenderEngine` should own:
- stale detection,
- sample/trace refresh decisions,
- relayout/range application,
- render result semantics (`changed`, `rerendered`, optional diagnostics payload).

Its core API should be synchronous and explicit.

### 5) Debouncing is a reusable service (comment integrated)

Debouncing should not be embedded as ad-hoc logic in orchestrator flows.
- Introduce/standardize a generic debouncing service module that can be reused by rendering, info panels, and other UI-adjacent flows.
- `RenderEngine` should expose deterministic synchronous operations.
- `Figure` (or adapters) can opt into debounced invocation by composing the shared debounce service.

This keeps render policy deterministic while preserving UX-friendly throttling behavior.

### 6) `ViewRuntime` owns runtime view lifecycle

`ViewRuntime` should own:
- add/switch/remove view state transitions,
- active view identity,
- runtime handles and per-view registration data,
- invariant checks for active/inactive transitions.

This should build on existing `figure_view_manager` direction rather than duplicating parallel abstractions.

### 7) `FigureUIAdapter` isolates widget/notebook synchronization

A thin adapter should own:
- sidebar/legend/info-visibility synchronization,
- widget-specific updates,
- translation between internal state snapshots and UI mutation calls.

UI adapter inputs should be immutable snapshots (dataclass/dict) at boundary crossings.

### 8) Interaction philosophy and encapsulation rules (comment integrated)

Adopt explicit interaction semantics:
- avoid object-based command indirection for core service interaction,
- prefer direct calls to **public methods** on collaborators,
- strongly discourage cross-class calls into private methods,
- keep public methods thin and make heavy logic private to the owning class.

This makes coupling visible and reviewable, and reduces “hidden protocol” drift between modules.

---

## Required ownership matrix (for implementation planning)

The implementation plan should classify every current `Figure` method into one of the following buckets:
- **Facade-only:** stable convenience wrapper, minimal delegation.
- **Orchestrator sequence:** call ordering and subsystem composition only.
- **Service-owned logic:** logic must move to one of `PlotRegistry`, parameter/parsing policy helper, `RenderEngine`, `ViewRuntime`, or `FigureUIAdapter`.
- **Deprecated/merge candidates:** methods to collapse or remove after extraction.

For each method, plan must list:
- current responsibility,
- target owner,
- migration strategy (direct extraction vs adapter shim),
- required regression tests.

## Contract shape requirements

Contracts should stay minimal and implementation-friendly:
- **Call style:** explicit named methods (`plot_registry.upsert_plot`, `render_engine.render_active_view`, etc.).
- **Return style:** simple values (`bool`, enum, dataclass) only when clarity requires it.
- **Boundary data:** immutable snapshots only at adapter boundaries.
- **Error model:** explicit exceptions or typed failure results; no silent policy fallthrough.

## Alternatives considered and rejected

1. **Method-count-only split of `Figure.py`**
   - Too shallow; moves code without clarifying ownership.
   - Rejected as primary strategy.

2. **Full command/event architecture (CQRS/event-sourcing style)**
   - Adds abstraction overhead and opaque interaction pathways for this toolkit stage.
   - Rejected as primary strategy.

## Open questions

1. **How strict should boundary enforcement be in this phase?**
   - Current direction: convention-first boundaries (ownership + review discipline) now; import-lint/hard guards can follow in a hardening project.

2. **How much metadata should parameter detection return in phase 1?**
   - Proposed: start with required detection outputs plus optional extension points; avoid over-design.

3. **Should render diagnostics be standardized across services now or later?**
   - Proposed: define minimal shared diagnostics payload now for testability and observability; postpone richer telemetry.

## Challenges and mitigations

- **Challenge:** behavior drift while extracting `plot()` and render paths.
  - **Mitigation:** characterize existing behavior with focused regression tests before and during extraction.

- **Challenge:** accidental cycles between render/view/ui modules.
  - **Mitigation:** enforce one-way dependency direction from orchestrator composition; collaborators do not call each other’s private internals.

- **Challenge:** preserving notebook UX while moving UI synchronization.
  - **Mitigation:** preserve facade signatures and validate with notebook-facing tests and targeted integration checks.

- **Challenge:** hidden coupling introduced by convenience wrappers.
  - **Mitigation:** require method-level ownership mapping and private/public boundary checks in code review.

## TODO

- [ ] Produce a full method ownership matrix for `Figure` with migration targets.
- [ ] Define concrete APIs for `PlotRegistry`, parameter/parsing helper, `RenderEngine`, `ViewRuntime`, and `FigureUIAdapter`.
- [ ] Define debouncing service interface and integration points (render + non-render consumers).
- [ ] Document invariants for each collaborator (input assumptions, mutation rules, return guarantees).
- [ ] Identify which existing modules are extended vs newly introduced to avoid abstraction duplication.
- [ ] Draft phased migration strategy that keeps toolkit functioning at every phase boundary.
- [ ] Convert this summary into implementation blueprint in `plan.md`, including acceptance tests.

## Exit criteria

- [ ] `Figure.py` responsibilities are limited to orchestration, lifecycle composition, and facade delegation.
- [ ] Plot collection lifecycle is isolated in `PlotRegistry`, while parameter/parsing policy is isolated in its own collaborator.
- [ ] Render policy is isolated in `RenderEngine` with deterministic synchronous APIs.
- [ ] Debouncing exists as a reusable service used by render orchestration and available for other UI flows.
- [ ] View runtime lifecycle is isolated from UI synchronization logic.
- [ ] UI synchronization is isolated in `FigureUIAdapter` with snapshot-based boundaries.
- [ ] Public helper facade remains stable while internal policy logic is removed from wrappers.
- [ ] Documentation maps each concern to exactly one owning module.
- [ ] Regression tests cover key behavior equivalence during extraction.
