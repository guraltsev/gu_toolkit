# Project 032: Codebase Streamlining (Umbrella)

**Status:** Active
**Priority:** High
**Type:** Umbrella project (portfolio coordination)

## Goal/Scope

Coordinate and sequence the maintainability/architecture streamlining portfolio so active projects have:
- non-overlapping ownership,
- explicit dependency order,
- and shared completion gates.

Project-032 is a planning-and-governance umbrella. It does not carry implementation tasks that belong to a child project.

## Portfolio boundaries (source of truth)

This umbrella coordinates the projects below and defines strict ownership boundaries.

| Project | Scope owner for | Out of scope for that project |
|---|---|---|
| **005** Testing Infrastructure | CI test breadth/depth, coverage progression, notebook/browser test posture | Architecture decomposition decisions |
| **021** Packaging Hardening | Versioning/release workflow, packaging hygiene, contributor install/build documentation | Internal module decomposition or ownership matrix work |
| **023** Package Reorganization | Physical module topology, snake_case normalization, import migration | Behavior-changing refactors and duplicate-logic policy |
| **033** DRY Refactoring | Duplicate-functionality consolidation (`resolve_symbol`, constants, normalization helpers) | Topology moves unless required by canonical-owner placement |
| **035** Architecture Modularization Program | Target architecture and program-level invariants (north-star design) | Detailed method-level execution bookkeeping |
| **036** Figure Concern Analysis | Historical analysis record and extraction-triage rationale | New implementation execution (moved to 037) |
| **037** Ownership/Boundary/Dedup Execution | Method-level ownership matrix, boundary contracts, execution tracking of dedup/boundary slices | Replacing the umbrella or redefining program north-star |

## Implementation order and interdependencies

### Phase 0 — Baseline safety and release hygiene
1. **005** (testing reliability and confidence floor)
2. **021** (packaging/versioning/release readiness)

These can run in parallel and should stay ahead of heavy refactors.

### Phase 1 — Architecture direction and execution scaffolding
3. **035** (confirm architecture invariants and modernization target)
4. **037** (convert architecture intent into ownership matrix + boundary contracts + dedup execution slices)

Project-037 operationalizes 035. It must not redefine 035’s north-star; it implements it.

### Phase 2 — Code movement and consolidation
5. **033** (consolidate duplicate logic into canonical owners)
6. **023** (move modules into subpackages with normalized names/imports)

033 and 023 are coordinated:
- 033 decides *canonical owner* for duplicates.
- 023 decides *final physical location* and import topology.

Where needed, small 033 slices can land before or during 023, but ownership decisions must be recorded in 037 to avoid drift.

### Phase 3 — Closeout
7. Reconcile remaining 036 concerns as **deferred/abandoned/done** in 037.
8. Archive completed projects and mark umbrella exit criteria complete.

## Dependency graph (updated)

```text
005 (Testing)  ───────────────┐
021 (Packaging) ──────────────┤
                              ├──→ 035 (Architecture target)
                              │            │
                              │            └──→ 037 (Ownership/boundary execution)
                              │                      │
                              │                      ├──→ 033 (Dedup implementation)
                              │                      └──→ 023 (Package migration)
                              │
036 (Concern analysis record) ─────────────→ informs 037 triage only
```

## Current status snapshot (2026-02-20)

- **Completed:** 031 (static analysis) is archived and no longer a scheduling gate.
- **Active foundational:** 005 and 021 remain open but materially progressed.
- **Active architecture coordination:** 035 (north-star) and 037 (execution vehicle) are the primary architecture tracks.
- **Execution work:** 033 and 023 remain open and should be sequenced through 037 ownership/boundary decisions.
- **Analysis-only:** 036 is maintained as reference/triage context, not as an implementation project.

## Umbrella TODO checklist (coordination only)

- [ ] Maintain a single cross-project dependency table in this document.
- [ ] Ensure each coordinated project has explicit “in scope / out of scope” text and reciprocal links.
- [ ] Ensure project-037 contains the active ownership matrix and boundary-contract artifact references.
- [ ] Ensure project-033 and project-023 do not duplicate each other’s responsibilities (owner selection vs physical migration).
- [ ] Reconcile project-036 items into 037 disposition categories (moved/deferred/abandoned/done).
- [ ] Re-check 005 and 021 closure status before authorizing broad package migration in 023.

## Umbrella exit criteria

- [ ] All coordinated child projects are either completed or explicitly superseded/archived.
- [ ] No unresolved scope overlap exists among 023/033/035/037.
- [ ] Ownership/boundary decisions are recorded once (037) and referenced, not copied, by related projects.
- [ ] Package topology and dedup outcomes are complete and consistent with architecture invariants.
- [ ] Testing and packaging gates are strong enough to preserve refactor safety.

## Coordination notes

- Project-032 remains the umbrella portfolio index.
- Project-035 defines architecture intent.
- Project-037 tracks execution-grade ownership/boundary/dedup artifacts.
- Project-036 is retained as context and rationale, not parallel execution scope.
