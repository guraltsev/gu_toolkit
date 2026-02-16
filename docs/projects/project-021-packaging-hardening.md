# Project 021: Packaging Hardening

**Status:** Active  
**Priority:** Medium

## Context
Packaging is now in place (`pyproject.toml`, `requirements.txt`, `tox.ini`, pytest/coverage config), so the original refactor proposal is no longer accurate. This project tracks only remaining hardening work.

## Completed
- [x] Add `pyproject.toml` build and project metadata.
- [x] Add runtime dependency manifest (`requirements.txt`).
- [x] Add local test tooling (`tox.ini`, pytest config).

## TODO
- [ ] Expand `.gitignore` to include common Python build/test artifacts.
- [ ] Decide whether to keep flat package layout or migrate to `src/` layout.
- [ ] Add versioning/release policy notes (tagging + publish process).
- [ ] Verify optional dependency groups are documented for contributors.

## Exit Criteria
- [ ] Packaging/release docs reflect actual workflow.
- [ ] Local/dev install and test commands are documented and reproducible.
