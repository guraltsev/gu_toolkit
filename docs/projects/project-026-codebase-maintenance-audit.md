# Project 026: Codebase Maintenance Audit Follow-through

**Status:** Active  
**Priority:** Medium

## Status
Active

## Goal/Scope
Track follow-up actions from the code-analysis report after removing the legacy `refactor/` bucket.

## Completed Since Audit
- [x] Figure context stack moved to thread-local storage (`figure_context.py`), resolving the prior thread-safety concern.

## TODO checklist
- [ ] Close open bug tickets raised from the audit (see active issues 018-020).
- [ ] Re-run structural audit after those bugs are resolved.
- [ ] Re-prioritize decomposition/reorganization projects with fresh code metrics.
- [ ] Archive this project to `_completed/` once follow-through items are closed.


## Exit criteria
- [ ] Planned deliverables are implemented and validated by tests.

## Summary of design
The implementation/design details for this project are captured in the existing project-specific sections above (for example, context, proposed areas, implementation plan, or architecture notes). This section exists to keep the project format consistent across active project records.

## Open questions
- None currently beyond items already tracked in the TODO checklist.

## Challenges and mitigations
- **Challenge:** Scope drift as related cleanup and modernization work is discovered.
  **Mitigation:** Keep TODO items explicit and only add new work after triage.
- **Challenge:** Regressions while refactoring existing behavior.
  **Mitigation:** Require targeted tests and keep delivery phased so the toolkit remains usable between milestones.
