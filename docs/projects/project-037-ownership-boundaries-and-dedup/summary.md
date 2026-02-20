# Project 037: Ownership Matrix, Boundary Contracts, and Duplication Elimination

## Status

**Planning (new execution-focused successor to selected Project-036 goals)**

## Goal/Scope

Execute the highest-value architecture work that is currently under-defined or incomplete, without forcing premature extractions from `Figure.py` that have diminishing returns.

This project focuses on:
- establishing a concrete **ownership matrix** for Figure ecosystem responsibilities,
- removing **duplicate implementations** that address the same functionality,
- clarifying and codifying **domain boundaries and interaction rules** between orchestration, plot semantics, parameters, view runtime, and UI adapters,
- sequencing this work against related active projects so overlap is explicit.

This project does **not** include speculative new module creation where equivalent infrastructure already exists.

## Summary of design

### 1) Ownership matrix first (authoritative responsibility map)

Create and maintain a method-level ownership matrix for `Figure.py` and its collaborators. Every responsibility should map to exactly one owner category:
- facade-only forwarding,
- orchestrator sequencing,
- service-owned logic (existing modules first, not new wrappers),
- deferred extraction (with explicit trigger criteria).

The matrix must include present owner, target owner, confidence level, migration action (retain/move/merge/delete), and rationale.

### 2) Duplicate-functionality elimination as an explicit track

Treat duplication as first-class architecture debt, not incidental cleanup. Immediate candidate scope (aligned with project-033 findings):
- symbol/key resolution duplication,
- duplicated constant datasets (e.g., Greek-letter metadata),
- overlapping normalization utilities with partially divergent behavior.

For each duplicate cluster:
- define canonical owner module,
- define compatibility behavior and error semantics,
- replace secondary implementations,
- add targeted regression tests.

### 3) Boundary contracts over abstraction proliferation

Codify boundaries and allowed interactions between modules that already exist:
- `Figure.py` as orchestration + public facade sequencing,
- `figure_plot.py` for per-plot render/math policy,
- `figure_parameters.py` for parameter state/control lifecycle,
- `figure_view_manager.py` for view state transitions,
- `figure_layout.py`/`figure_legend.py`/`figure_info.py` for UI manager responsibilities,
- `debouncing.py` for reusable debounce behavior.

Primary rule: no new mediator class unless it owns novel behavior that cannot be cleanly placed in existing owners.

### 4) Merge/align overlapping planning across projects

Document explicit relationships with:
- project-035 (umbrella architecture program),
- project-033 (DRY refactoring),
- project-032 (legacy umbrella sequencing),
- project-036 (concern review and extraction triage).

Project-037 becomes the execution-focused vehicle for ownership/boundary/dedup outcomes that were previously spread across those documents.

### 5) Deliverables

- ownership matrix artifact (doc table, updated as code changes),
- boundary contract/spec section with allowed dependency directions,
- duplicate-cluster inventory with disposition and test mapping,
- implementation `plan.md` with phased milestones that keep repository functional at each step.

## Open questions

1. Where should the ownership matrix live long-term (Project-037 summary vs standalone architecture policy file)?
2. Should duplicate elimination land as one focused PR stream or be folded into feature-adjacent refactors?
3. Should boundary-rule enforcement begin with documentation + review checklist only, or add automated import-boundary checks immediately?
4. Which `Figure.py` methods are explicitly accepted as permanent orchestrator logic (not extraction candidates)?

## Challenges and mitigations

- **Challenge:** Ownership decisions can drift as refactors land.
  - **Mitigation:** require matrix updates in any PR touching mapped methods.

- **Challenge:** Deduplication can cause subtle behavior regressions.
  - **Mitigation:** characterize existing behavior with focused tests before consolidating implementations.

- **Challenge:** Boundary rules may be documented but ignored.
  - **Mitigation:** add architecture review checklist items and optional lint/import-policy guardrails.

- **Challenge:** Cross-project overlap creates planning ambiguity.
  - **Mitigation:** include explicit “supersedes/depends-on/informs” mapping for related projects in this project and reciprocal references in those project summaries.

## TODO

- [ ] Build and publish a method-level ownership matrix for `Figure.py` + key collaborators.
- [ ] Classify each `Figure.py` method as retain-in-orchestrator, move, merge, or defer-with-trigger.
- [ ] Define and document canonical owners for known duplicate-functionality clusters.
- [ ] Execute deduplication for one high-confidence cluster as pilot (with tests).
- [ ] Document domain boundary contracts and forbidden dependency directions.
- [ ] Produce `plan.md` with phased implementation slices and acceptance checks.
- [ ] Add cross-links and disposition notes in related projects (032/033/035/036).

## Exit criteria

- [ ] Ownership matrix exists and covers all public `Figure` methods plus major internal orchestration helpers.
- [ ] Every tracked duplicate-functionality cluster has a documented canonical owner and disposition.
- [ ] At least one duplicate cluster is fully consolidated with regression tests.
- [ ] Boundary contracts are documented and referenced by active architecture projects.
- [ ] Project-036 extraction proposals are explicitly triaged into abandoned/deferred/moved categories.
- [ ] A concrete implementation plan exists (`plan.md`) and is executable in stable phases.
