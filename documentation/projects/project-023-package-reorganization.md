# Project 023: Package Reorganization

**Status:** Backlog  
**Priority:** Low

## Goal
Reorganize the flat module layout into focused subpackages to improve long-term maintainability.

## Proposed Areas
- `figure/` for figure orchestration and rendering.
- `widgets/` for widget implementations.
- `math/` for symbolic/numeric helpers.
- `core/` for protocols, events, snapshots, and utilities.

## TODO
- [ ] Draft a no-break public API compatibility matrix.
- [ ] Define migration sequence (small moves with tests after each step).
- [ ] Add compatibility shims for legacy internal imports where necessary.
- [ ] Perform snake_case cleanup as part of module moves.

## Exit Criteria
- [ ] Public API remains stable.
- [ ] Internal structure is grouped by responsibility.
- [ ] Test suite passes during and after migration.
