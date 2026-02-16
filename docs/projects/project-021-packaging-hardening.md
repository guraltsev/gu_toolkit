# Project 021: Packaging Hardening

**Status:** Active  
**Priority:** Medium

## Context
Packaging is now in place (`pyproject.toml`, `requirements.txt`, `tox.ini`, pytest/coverage config), so the original refactor proposal is no longer accurate. This project tracks only remaining hardening work.

## Completed
- [x] Add `pyproject.toml` build and project metadata.
- [x] Add runtime dependency manifest (`requirements.txt`).
- [x] Add local test tooling (`tox.ini`, pytest config).

## Goal/Scope
See existing context and scope sections below for detailed boundaries.

## TODO checklist
- [ ] Expand `.gitignore` to include common Python build/test artifacts.
- [ ] Decide whether to keep flat package layout or migrate to `src/` layout.
- [ ] Add versioning/release policy notes (tagging + publish process).
- [ ] Verify optional dependency groups are documented for contributors.

## Exit criteria
- [ ] Packaging/release docs reflect actual workflow.
- [ ] Local/dev install and test commands are documented and reproducible.


## Status
Active

## Summary of design
The implementation/design details for this project are captured in the existing project-specific sections above (for example, context, proposed areas, implementation plan, or architecture notes). This section exists to keep the project format consistent across active project records.

## Open questions
- None currently beyond items already tracked in the TODO checklist.

## Challenges and mitigations
- **Challenge:** Scope drift as related cleanup and modernization work is discovered.
  **Mitigation:** Keep TODO items explicit and only add new work after triage.
- **Challenge:** Regressions while refactoring existing behavior.
  **Mitigation:** Require targeted tests and keep delivery phased so the toolkit remains usable between milestones.
