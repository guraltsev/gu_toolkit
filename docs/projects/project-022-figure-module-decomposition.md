# Project 022: Figure Module Decomposition

**Status:** Backlog  
**Priority:** Medium

## Status
Backlog

## Goal/Scope
Reduce `Figure.py` complexity by separating core class logic from module-level convenience helpers and proxies.

## Scope
- Move module-level helper functions (`plot`, `parameter`, `render`, etc.) to a dedicated API module.
- Keep public imports stable via `__init__.py` re-exports.
- Remove stale comments/doc duplication while splitting.

## TODO checklist
- [ ] Define target module split (`Figure` class vs helper API).
- [ ] Implement move with compatibility re-exports.
- [ ] Add regression tests for helper import paths.
- [ ] Remove stale/duplicate module comments after split.

## Exit criteria
- [ ] `Figure` core class file is materially smaller and easier to navigate.
- [ ] Existing user-facing imports remain valid.

## Summary of design
The implementation/design details for this project are captured in the existing project-specific sections above (for example, context, proposed areas, implementation plan, or architecture notes). This section exists to keep the project format consistent across active project records.

## Open questions
- None currently beyond items already tracked in the TODO checklist.

## Challenges and mitigations
- **Challenge:** Scope drift as related cleanup and modernization work is discovered.
  **Mitigation:** Keep TODO items explicit and only add new work after triage.
- **Challenge:** Regressions while refactoring existing behavior.
  **Mitigation:** Require targeted tests and keep delivery phased so the toolkit remains usable between milestones.

## Completion Assessment (2026-02-17)

- [ ] `Figure.py` decomposition has not been executed; helper APIs are still co-located with core figure internals.
- [ ] Compatibility re-export migration and corresponding regression tests are not complete.
- [ ] Target split design remains to be finalized.
- [ ] Therefore, this project remains **open**.

