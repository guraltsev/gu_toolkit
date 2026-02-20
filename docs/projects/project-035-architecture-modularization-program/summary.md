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

## Scope boundary (under umbrella project-032, Phase 1)

- **032 (Umbrella):** Portfolio sequencing authority. 035 does not set implementation order.
- **037 (Execution):** Ownership matrix, boundary contracts, dedup tracking. 037 operationalizes 035's direction; 035 does not duplicate execution artifacts.
- **033 (DRY):** Implements duplicate-logic consolidation. 035 provides invariants that constrain where canonical owners land.
- **023 (Package Reorg):** Executes physical migration. 035 provides layer definitions that constrain subpackage boundaries.
- **036 (Archived):** Historical concern-analysis record in `_completed/`. Consumed by 037 for triage; no longer an active project.

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

## Coordination notes

- Project-035 is Phase 1 under umbrella project-032.
- 035 defines architecture intent; 037 operationalizes it into concrete artifacts.
- Project-036 is archived in `_completed/` as an analysis reference; its execution scope moved to 037.
- Feature project 034 (Legend Panel UX Refresh) touches the backend/UI contract direction via `Plot.effective_style()` and typed state protocols. 035 owns the general architectural stance; 034 implements it in the legend domain.
