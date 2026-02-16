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
