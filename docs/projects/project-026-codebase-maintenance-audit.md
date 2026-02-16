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
