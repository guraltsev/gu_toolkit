# Issue 021: Propose AGENTS.md documentation discipline aligned with current repository practices

## Status
Closed (2026-02-16)

## Summary
This issue proposed adding contributor guidance for documentation quality and documentation-tree lifecycle workflow rules.

The requested guidance has now been implemented with a repository-level `Agents.md` and a docs-scoped `docs/Agents.md`, and the docs tree uses the `docs/` pathing conventions tracked in `docs/README.md`.

## Evidence
- `Agents.md` exists at the repository root and defines API/docstring and docs-update expectations.
- `docs/Agents.md` exists and defines issue/project lifecycle rules for the docs tree, including `_closed` and `_completed` destinations.
- `docs/README.md` reflects the current docs structure (`docs/Bugs`, `docs/projects`, `docs/Discussions`, `docs/develop_guide`).

## TODO
- [x] Review proposal wording and decide strictness for public-function examples.
- [x] Add root `Agents.md`.
- [x] Add docs-scoped `docs/Agents.md`.

## Exit criteria
- [x] Team agrees on the proposed guidance scope and strictness.
- [x] Approved guidance files are added to the repository.
- [x] Subsequent maintenance updates follow the documented structure and naming conventions.
