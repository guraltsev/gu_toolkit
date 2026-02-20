# Project 035: Architecture Modularization Program (Backend + UI Contract)

## Status

**Discovery / architecture-definition track**

## Goal/Scope

Define the architecture north-star and invariants for modernization, then hand execution slices to downstream projects.

Project-035 owns:
1. Target layered architecture and responsibility boundaries.
2. Backend/UI contract direction and protocol stance.
3. Program-level invariants used to evaluate refactor proposals.

Project-035 does **not** own method-level implementation tracking; that is delegated to project-037.

## Relationship to other projects (non-overlap)

- **Project-032:** Portfolio umbrella and ordering authority.
- **Project-037:** Execution owner for ownership matrix, boundary contract artifacts, and dedup execution slices.
- **Project-033:** Implements duplicate-logic consolidation decisions.
- **Project-023:** Executes physical package migration decisions.
- **Project-036:** Historical concern-analysis input only.

## Architecture direction (authoritative)

- Preserve a clear layered split:
  - Domain semantics,
  - orchestration/application lifecycle,
  - UI adapter/runtime concerns,
  - frontend interaction behavior.
- Durable semantic state is backend-authoritative.
- Transient interaction behavior is frontend-owned.
- Cross-boundary interaction should use explicit, typed state/intents.

## Open decisions (current)

1. Contract artifact strictness: **Option A** (Python dataclass/type-hint first).
2. Protocol scope: **Option B** (whole-figure protocol target, not legend-only).
3. Naming policy rollout: **incremental snake_case normalization**.

## TODO

- [ ] Publish architecture invariants as a concise checklist consumable by implementation PRs.
- [ ] Confirm minimum typed backend/frontend contract surface for first execution milestone.
- [ ] Provide acceptance criteria that 037 can map to concrete phased tasks.
- [ ] Maintain reciprocal links when 033/023/037 scopes evolve.

## Exit criteria

- [ ] Architecture invariants are explicit and referenced by execution projects.
- [ ] Contract-direction decisions are documented and stable enough for implementation.
- [ ] Scope boundary with 037 is clear and maintained (no duplicate execution tracking here).

---

## Coordination update (2026-02-20)

Project-035 remains the architecture-definition layer. Execution-oriented ownership matrix, boundary contracts, and dedup implementation tracking are intentionally centralized in project-037, under umbrella sequencing in project-032.
