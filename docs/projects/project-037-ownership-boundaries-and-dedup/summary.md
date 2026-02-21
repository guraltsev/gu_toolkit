# Project 037: Ownership Matrix, Boundary Contracts, and Duplication Elimination

## Status

**Planning (execution-focused architecture track)**

## Goal/Scope

Provide the execution control plane for architecture streamlining by turning high-level intent into actionable ownership and boundary artifacts.

Project-037 owns:
- method-level ownership matrix for `Figure` ecosystem responsibilities,
- concrete boundary-contract documentation and allowed dependency directions,
- duplicate-cluster execution tracking and dispositions,
- phased implementation plan slices that stay repository-safe.

## Scope boundary (under umbrella project-032, Phase 1)

- **032 (Umbrella):** Sequencing authority. 037 does not set portfolio order.
- **035 (Architecture):** North-star and invariants authority. 037 operationalizes 035's direction; it must not redefine it.
- **033 (DRY):** Implements duplicate-logic consolidation. 037 records canonical-owner decisions that 033 executes.
- **023 (Package Reorg):** Implements physical migration. 037 records placement decisions that 023 executes.
- **036 (Archived):** Historical analysis in `_completed/project-036-figure-orchestrator-separation/`. 037 consumes it for triage context; disposition categories (abandoned/moved/deferred) are documented in the archived file.

## Core deliverables

1. **Ownership matrix artifact**
   - method/responsibility,
   - current owner,
   - target owner,
   - action (`retain`, `move`, `merge`, `defer`, `abandon`),
   - rationale and confidence.

2. **Boundary contract artifact**
   - allowed module dependency directions,
   - forbidden dependency patterns,
   - orchestration interaction rules.

3. **Duplicate cluster ledger**
   - cluster id and canonical owner,
   - compatibility/error-semantics notes,
   - implementation project link (033/023),
   - test coverage mapping.

4. **Phased plan (`plan.md`)**
   - small, executable, stable slices,
   - acceptance checks per slice.

## Sequencing role (under project-032)

- Use 035 invariants as constraints.
- Feed canonical-owner decisions into 033.
- Feed physical-placement decisions into 023.
- Keep archived-036 concerns explicitly triaged and dispositioned.

## TODO

- [x] Publish first ownership matrix revision for `Figure.py` + key collaborators.
- [x] Publish boundary-rule table with allowed/forbidden directions.
- [ ] Publish duplicate-cluster ledger with canonical-owner proposals.
- [ ] Land at least one pilot dedup cluster through project-033 with regression tests.
- [x] Create `plan.md` with phased milestones and repository-safety checks.
- [x] Add reciprocal scope-link notes in 032/033/035/023 (036 archived).

## Progress checklist

- [x] Added ownership matrix artifact (`ownership-boundary-matrix-v1.md`) for `Figure.py` orchestration methods and collaborator ownership boundaries.
- [x] Added boundary rule table with explicit allowed/forbidden dependency directions and enforcement notes.
- [x] Added revision analysis (`revision-analysis-v2.md`) distinguishing current vs desired ownership/boundary state for all `REVISE` rows.
- [x] Added consolidated matrix (`ownership-boundary-matrix-v3-consolidated.md`) merging v1 and v2 with code-verified correctness/feasibility review.
- [ ] External architecture review of matrix and boundary table before moving project status beyond planning.

## Exit criteria

- [ ] Ownership matrix is complete for all public `Figure` methods and major orchestration helpers.
- [ ] Boundary contracts are documented and referenced by execution projects.
- [ ] Duplicate clusters have canonical-owner dispositions and linked implementation tracks.
- [ ] At least one dedup cluster is implemented end-to-end with tests.
- [ ] Archived project-036 proposals are fully dispositioned as moved/deferred/abandoned/done.
- [ ] Ongoing updates show no scope overlap drift with 032/035/033/023.
