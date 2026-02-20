# Project 032: Codebase Streamlining (Umbrella)

**Status:** Active
**Priority:** High
**Type:** Umbrella project

## Goal/Scope

Coordinate the set of improvement projects that collectively streamline
and organize the codebase for long-term maintainability. This umbrella
tracks sequencing, dependencies, and overall progress across the
constituent subprojects.

This project was created based on the comprehensive code review documented
in `docs/Discussions/code-review-strengths-weaknesses.md`.

## Motivation

The codebase has strong architectural foundations — composition-based
delegation, Protocol-driven extensibility, immutable snapshot design,
and exceptional documentation. The primary maintainability risks are:

1. `Figure.py` has grown into an over-leveraged coordinator (67 KB).
2. 29 modules in a flat namespace with no subpackage structure.
3. Type annotations exist but are not verified by any static analysis tool.
4. Code duplication in symbol resolution and constant data.
5. Conservative test coverage floor (50%) with no notebook test automation.
6. Packaging artifacts and release workflow not fully hardened.

## Subprojects and sequencing

The subprojects are ordered by a combination of dependency relationships
and impact. Projects earlier in the sequence unblock or de-risk later ones.

### Phase 1: Safety net (can start immediately, in parallel)

| Project | Title | Priority | Rationale |
|---------|-------|----------|-----------|
| **031** | Static Analysis Tooling | High | Lowest effort, immediate value. Catches regressions and makes subsequent refactoring safer. |
| **005** | Testing Infrastructure | Medium | Raise coverage floor and integrate notebook tests. Provides regression safety for all later work. |
| **021** | Packaging Hardening | Medium | `.gitignore`, versioning, release docs. Low-risk, independently completable. |

### Phase 2: Core decomposition (after Phase 1 tooling is in place)

| Project | Title | Priority | Rationale |
|---------|-------|----------|-----------|
| **022** | Figure Module Decomposition | High | Highest daily-maintainability impact. Reduces the largest module to a focused coordinator. |
| **033** | DRY Refactoring | Medium | Extract shared utilities (symbol resolution, Greek constants). Can proceed in parallel with 022 or be folded into 023. |

### Phase 3: Structural reorganization (after Phase 2)

| Project | Title | Priority | Rationale |
|---------|-------|----------|-----------|
| **023** | Package Reorganization | Medium | Codifies the layered architecture into subpackages. The `figure/` subpackage migration is cleanest after 022 completes; other subpackages (`math/`, `widgets/`, `core/`, `snapshot/`) can proceed independently. |

### Dependency graph

```
031 (Static Analysis) ──┐
005 (Testing)     ──────┼──→ 022 (Figure Decomp) ──→ 023 (Package Reorg)
021 (Packaging)   ──────┘         ↑                        ↑
                            033 (DRY Refactoring) ─────────┘
```

- **031, 005, 021** have no inter-dependencies and can proceed in parallel.
- **022** benefits from 031 (type checker catches refactoring errors) and
  005 (higher coverage catches regressions).
- **033** can proceed in parallel with 022 or be folded into 023.
- **023** depends on 022 for the `figure/` subpackage; other subpackages
  are independent. The layout decision from 021 feeds into 023.

## TODO checklist

### Phase 1: Safety net
- [x] **Project 031:** ruff + mypy configured and passing in CI.
- [x] **Project 031:** Pre-commit hooks documented.
- [ ] **Project 005:** Coverage threshold raised to 70%.
- [ ] **Project 005:** Notebook tests integrated into CI.
- [ ] **Project 021:** `.gitignore` expanded.
- [ ] **Project 021:** Versioning scheme documented.

### Phase 2: Core decomposition
- [ ] **Project 022:** Module-level helpers extracted to `figure_api.py`.
- [ ] **Project 022:** Plot input normalization extracted.
- [ ] **Project 022:** View management extracted to `ViewManager`.
- [ ] **Project 022:** `Figure.py` reduced to under 800 lines.
- [ ] **Project 033:** Shared `resolve_symbol` utility extracted.
- [ ] **Project 033:** `_normalize_vars()` simplified.

### Phase 3: Structural reorganization
- [ ] **Project 023:** `math/` subpackage migrated.
- [ ] **Project 023:** `widgets/` subpackage migrated.
- [ ] **Project 023:** `core/` subpackage migrated.
- [ ] **Project 023:** `snapshot/` subpackage migrated.
- [ ] **Project 023:** `figure/` subpackage migrated.
- [ ] **Project 023:** Backward-compatibility shims deprecated.
- [ ] **Project 023:** All module names normalized to snake_case.

## Exit criteria

- [ ] All subprojects are completed and archived.
- [ ] `Figure.py` is under 800 lines.
- [ ] Modules are organized into subpackages by responsibility.
- [ ] Static analysis (ruff + mypy) passes in CI.
- [ ] Coverage threshold is at or above 70%.
- [ ] Public API (`from gu_toolkit import ...`) is unchanged throughout.
- [ ] Code duplication targets are eliminated.

## Challenges and mitigations

- **Challenge:** The subprojects span multiple work sessions and may
  interact in unexpected ways.
  **Mitigation:** Phase gating ensures each layer stabilizes before the
  next begins. The test suite and static analysis provide regression
  safety.

- **Challenge:** Reorganization may disrupt ongoing feature work.
  **Mitigation:** Public API is frozen throughout. Feature branches that
  depend on internal paths should be rebased after each subpackage
  migration.

- **Challenge:** Maintaining momentum across 6 subprojects.
  **Mitigation:** Phase 1 projects are small and independently
  completable, providing early wins and building confidence for the
  larger structural changes.

## Completion Assessment (2026-02-18)

- [x] Phase-1 static-analysis subproject (031) is complete and can be treated as closed.
- [ ] Remaining Phase-1 gates are still open (`005` notebook CI/coverage outcomes, `021` packaging hardening).
- [ ] Phase-2 (`022`, `033`) and Phase-3 (`023`) restructuring objectives remain open.
- [ ] Umbrella exit criteria are not yet met because multiple dependent projects are incomplete.

**Result:** Umbrella project remains **open**.

---

## Coordination update (2026-02-20)

Ownership-matrix and boundary-contract execution details are now tracked in project-037 (`docs/projects/project-037-ownership-boundaries-and-dedup/summary.md`) to reduce overlap between umbrella planning artifacts.
