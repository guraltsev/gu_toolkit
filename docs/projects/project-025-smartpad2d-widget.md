# Project 025: SmartPad2D Control

**Status:** Discovery  
**Priority:** Medium

## Status
Discovery

## Goal/Scope
Add a two-parameter XY pad control that can own two symbols and integrate with the existing parameter manager.

## Core Requirements
- Single control maps to two symbols (e.g. `(a, b)`).
- Drag surface + numeric fields stay synchronized.
- Uses existing parameter ownership model so slider autodetection does not duplicate controls.
- Supports throttled live updates and commit-on-release mode.

## TODO checklist
- [ ] Finalize widget contract (`values`, `get_value`, `set_value`, `on_change`).
- [ ] Decide implementation split between Python-side composite widget and JS drag surface.
- [ ] Define parameter manager registration behavior for multi-symbol controls.
- [ ] Add tests for synchronization, validation, and callback payloads.

## Exit criteria
- [ ] SmartPad2D can be attached to a figure as a first-class parameter control.
- [ ] Existing slider-based flows remain unchanged.

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

- [ ] No `SmartPad2D` runtime widget implementation is present in the codebase yet.
- [ ] Contract, architecture split, registration behavior, and tests are all still in discovery/planning.
- [ ] Therefore, this project remains **open**.

