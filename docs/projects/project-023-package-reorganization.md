# Project 023: Package Reorganization

**Status:** Backlog  
**Priority:** Low

## Status
Backlog

## Goal/Scope
Reorganize the flat module layout into focused subpackages to improve long-term maintainability.

## Proposed Areas
- `figure/` for figure orchestration and rendering.
- `widgets/` for widget implementations.
- `math/` for symbolic/numeric helpers.
- `core/` for protocols, events, snapshots, and utilities.

## TODO checklist
- [ ] Draft a no-break public API compatibility matrix.
- [ ] Define migration sequence (small moves with tests after each step).
- [ ] Add compatibility shims for legacy internal imports where necessary.
- [ ] Perform snake_case cleanup as part of module moves.

## Exit criteria
- [ ] Public API remains stable.
- [ ] Internal structure is grouped by responsibility.
- [ ] Test suite passes during and after migration.

## Summary of design
The implementation/design details for this project are captured in the existing project-specific sections above (for example, context, proposed areas, implementation plan, or architecture notes). This section exists to keep the project format consistent across active project records.

## Open questions
- None currently beyond items already tracked in the TODO checklist.

## Challenges and mitigations
- **Challenge:** Scope drift as related cleanup and modernization work is discovered.
  **Mitigation:** Keep TODO items explicit and only add new work after triage.
- **Challenge:** Regressions while refactoring existing behavior.
  **Mitigation:** Require targeted tests and keep delivery phased so the toolkit remains usable between milestones.
