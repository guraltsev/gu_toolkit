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

## Explicit boundaries (to prevent overlap)

- **Does not replace project-032:** 032 remains umbrella sequencing authority.
- **Does not redefine project-035:** 035 remains architecture north-star/invariants authority.
- **Does not absorb project-023 or 033 implementation scope:** it coordinates and records ownership/disposition; those projects perform the migrations/refactors.
- **Consumes project-036 as input only:** 036 is analysis context and triage rationale.

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
- Keep 036 concerns explicitly triaged and dispositioned.

## TODO

- [ ] Publish first ownership matrix revision for `Figure.py` + key collaborators.
- [ ] Publish boundary-rule table with allowed/forbidden directions.
- [ ] Publish duplicate-cluster ledger with canonical-owner proposals.
- [ ] Land at least one pilot dedup cluster through project-033 with regression tests.
- [ ] Create `plan.md` with phased milestones and repository-safety checks.
- [ ] Add reciprocal scope-link notes in 032/033/035/036/023.

## Exit criteria

- [ ] Ownership matrix is complete for all public `Figure` methods and major orchestration helpers.
- [ ] Boundary contracts are documented and referenced by execution projects.
- [ ] Duplicate clusters have canonical-owner dispositions and linked implementation tracks.
- [ ] At least one dedup cluster is implemented end-to-end with tests.
- [ ] Project-036 proposals are fully dispositioned as moved/deferred/abandoned/done.
- [ ] Ongoing updates show no scope overlap drift with 032/035/033/023.
