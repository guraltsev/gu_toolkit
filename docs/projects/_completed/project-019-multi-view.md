# Project 019: Multi-view figure workspace

Status: **Complete**
Closed on: 2026-02-16

## Scope
Deliver multi-view plotting workspaces with:
- per-view axis defaults and active-view switching,
- view-scoped plot membership,
- view-scoped info card visibility,
- snapshot/codegen support,
- tabbed layout behavior for single-view vs multi-view.

## Completion evidence
Automated tests that pass and cover these goals:
- `tests/test_project019_phase12.py`
- `tests/test_project019_phase56.py`

Key assertions in those tests confirm:
- default/main view registration and range delegation,
- add/switch view behavior,
- plot membership helpers and view scoping,
- stale-state handling and activation refresh,
- tab visibility and tab child stability,
- context-manager scoping,
- snapshot/codegen persistence for multi-view state,
- per-view trace isolation in widgets.

## Notes
Implementation references include:
- `figure_view.py` (explicitly labeled as Project 019 phase 1/2 foundation)
- `figure_layout.py` (phase 3 tab selector behavior)

Given current test coverage and in-module phase references, this project is considered complete and moved to `projects/complete`.
