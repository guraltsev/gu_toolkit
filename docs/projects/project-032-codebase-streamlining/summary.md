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

---

## Portfolio inventory

### Coordinated projects (active)

| Project | Title | Status | Phase | Scope owner for | Out of scope for that project |
|---|---|---|---|---|---|
| **005** | Testing Infrastructure | Near-complete (pending review) | 0 | CI test breadth/depth, coverage progression, notebook/browser test posture | Architecture decomposition decisions |
| **021** | Packaging Hardening | Active (partial) | 0 | Versioning/release workflow, packaging hygiene, contributor install/build docs | Internal module decomposition or ownership matrix work |
| **035** | Architecture Modularization Program | Discovery | 1 | Target architecture and program-level invariants (north-star design) | Method-level execution bookkeeping |
| **037** | Ownership/Boundary/Dedup Execution | Planning | 1 | Method-level ownership matrix, boundary contracts, dedup execution tracking | Replacing the umbrella or redefining program north-star |
| **033** | DRY Refactoring | Backlog | 2 | Duplicate-functionality consolidation (`resolve_symbol`, constants, normalization helpers) | Topology moves unless required by canonical-owner placement |
| **023** | Package Reorganization | Backlog | 2 | Physical module topology, snake_case normalization, import migration | Behavior-changing refactors and duplicate-logic policy |

### Archived under this umbrella

| Project | Title | Reason | Location |
|---|---|---|---|
| **022** | Figure Module Decomposition | Completed | `_completed/project-022-figure-module-decomposition/` |
| **031** | Static Analysis Tooling | Completed | `_completed/project-031-static-analysis-tooling/` |
| **026** | Codebase Maintenance Audit | Superseded by this umbrella; residual bug-ticket work tracked in `docs/Bugs/` | `_completed/project-026-codebase-maintenance-audit.md` |
| **036** | Figure Orchestrator Separation | Analysis retained as archived reference; execution scope moved to 037 | `_completed/project-036-figure-orchestrator-separation/` |

### Related projects (not coordinated by this umbrella)

These feature projects are tracked independently but have coordination touch-points with the streamlining portfolio:

| Project | Title | Status | Touch-point |
|---|---|---|---|
| **025** | SmartPad2D Widget | Discovery | Will consume parameter-manager interfaces stabilized by 035/037 |
| **030** | Dedicated Legend Side Panel | Complete (Phase 6 deferred to 034) | Foundation for 034; validated sidebar/manager patterns reused by streamlining |
| **034** | Legend Panel UX Refresh | Discovery | `Plot.effective_style()` contract relates to 035 architecture direction; absorbs 030 Phase 6 |

---

## Implementation phases and dependencies

### Phase 0 — Foundation safety and release hygiene

| Project | Remaining work | Gate for |
|---|---|---|
| **005** | Coverage-threshold progression, pytest-pattern consistency audit, browser-level widget test evaluation | Phase 2 refactors rely on test confidence |
| **021** | `.gitignore` expansion, versioning policy documentation, release workflow/checklist | Phase 2 module moves need clean packaging |

Phase 0 projects can run in parallel with each other and with Phase 1 planning. They must reach "green enough" status before Phase 2 code movement begins.

### Phase 1 — Architecture direction and execution scaffolding

| Project | Deliverable | Depends on |
|---|---|---|
| **035** | Architecture invariants checklist, backend/UI contract stance, naming policy | Phase 0 not blocking (planning only) |
| **037** | Ownership matrix, boundary contracts, duplicate-cluster ledger, phased plan | 035 invariants (must implement, not redefine); archived 036 analysis as input |

Phase 1 is planning and artifact production, not code changes. It can overlap with Phase 0. Project-037 must wait for 035's architecture direction to stabilize before publishing the ownership matrix.

### Phase 2 — Code movement and consolidation

| Project | Work | Depends on |
|---|---|---|
| **033** | Consolidate duplicate logic into canonical owners | 037 canonical-owner decisions; 005 test coverage for safety |
| **023** | Move modules into subpackages with normalized names/imports | 037 placement decisions; 021 packaging gates; 033 canonical owners resolved (or coordinated concurrently) |

033 and 023 are coordinated but distinct:
- 033 decides *canonical owner* for duplicates.
- 023 decides *final physical location* and import topology.

Small 033 slices can land before or during 023, but ownership decisions must be recorded in 037 to prevent drift.

### Phase 3 — Closeout

1. Verify all archived-036 concerns are dispositioned in 037 (moved/deferred/abandoned/done).
2. Archive completed projects.
3. Verify umbrella exit criteria are met.

---

## Dependency graph

```text
Phase 0 (parallel)             Phase 1 (parallel with 0)       Phase 2                 Phase 3
──────────────────             ──────────────────────────       ───────                 ───────
005 (Testing)     ─────────────────────────────────────────┐
                                                           ├──→ 033 (Dedup)   ──┐
021 (Packaging)   ─────────────────────────────────────┐   │                    ├──→ Closeout
                                                       │   │                    │
                  035 (Architecture target) ──→ 037 (Ownership/boundary) ──┤    │
                                                       │       ├──→ 023 (Package migration) ──┘
                                                       └───────┘
                  036 (archived analysis) ─── informs 037 triage only
```

Key constraints:
- Phase 2 projects (033, 023) must not begin heavy refactors until Phase 0 safety nets (005, 021) are mature and Phase 1 decisions (037) are published.
- 035 and 037 can begin during Phase 0 since they produce planning artifacts, not code changes.
- 033 and 023 can run concurrently if ownership decisions from 037 are available; otherwise 033 should land first so 023 can place consolidated code in its final location.

---

## Current status snapshot (2026-02-20)

### Phase 0

- **005 (Testing):** Core infrastructure implemented. 154 tests, coverage at 75%, notebook CI job running. Remaining: coverage-threshold progression, pytest-pattern audit, browser-level widget test evaluation. Near-complete pending external review.
- **021 (Packaging):** Baseline packaging in place (`pyproject.toml`, `tox.ini`, dependency groups). Remaining: `.gitignore` expansion, versioning policy, release workflow. Partially complete.

### Phase 1

- **035 (Architecture):** Architecture direction documented (layered split, typed contracts, incremental snake_case). Open decisions recorded. No concrete invariants checklist published yet.
- **037 (Execution):** Scope and deliverables defined. No artifacts (ownership matrix, boundary contracts, dedup ledger) produced yet. Depends on 035 stabilizing.

### Phase 2

- **033 (DRY):** Three duplication sites identified (`_resolve_symbol`, Greek letter data, `_normalize_vars`). No consolidation work started. Blocked on 037 canonical-owner decisions.
- **023 (Package Reorg):** Proposed subpackage structure documented. No migration work started. 022 dependency (Figure decomposition) is now satisfied (archived as complete). Blocked on 037 placement decisions and 021 packaging gates.

### Archived since last update

- **036 (Figure Orchestrator Separation):** Archived as analysis-only reference. Execution scope moved to 037. Disposition categories (abandoned/moved/deferred) are documented in the archived file.
- **026 (Codebase Maintenance Audit):** Archived as superseded by this umbrella. Residual bug-ticket work tracked in `docs/Bugs/`.

---

## Coordination checklist

- [x] Maintain a single cross-project dependency table in this document.
- [x] Ensure each coordinated project has explicit "in scope / out of scope" text.
- [x] Archive project-036 and retain as triage reference for 037.
- [x] Archive project-026 (superseded by this umbrella).
- [x] Verify project-023's dependency on project-022 is satisfied (022 completed).
- [ ] Ensure project-037 contains the active ownership matrix and boundary-contract artifacts before Phase 2 begins.
- [ ] Ensure project-033 and project-023 do not duplicate responsibilities (owner selection vs physical migration).
- [ ] Reconcile all archived-036 items into 037 disposition categories.
- [ ] Re-check 005 and 021 closure readiness before authorizing broad package migration in 023.
- [ ] Confirm 035 architecture invariants are stable before 037 publishes the ownership matrix.

---

## Exit criteria

- [ ] All coordinated child projects are either completed or explicitly superseded/archived.
- [ ] No unresolved scope overlap exists among 023/033/035/037.
- [ ] Ownership/boundary decisions are recorded once (in 037) and referenced, not copied, by related projects.
- [ ] Package topology and dedup outcomes are complete and consistent with 035 architecture invariants.
- [ ] Testing (005) and packaging (021) gates are strong enough to preserve refactor safety throughout Phase 2.
- [ ] All archived-036 proposals are fully dispositioned in 037.

---

## Coordination notes

- Project-032 is the umbrella portfolio index and sequencing authority.
- Project-035 defines architecture intent (north-star and invariants).
- Project-037 tracks execution-grade ownership/boundary/dedup artifacts.
- Archived project-036 is retained as analysis context in `_completed/`; it is not active execution scope.
- Feature projects (025, 030, 034) are tracked independently; coordination touch-points are noted above but those projects do not report to this umbrella.
