# Project 021: Packaging Hardening

**Status:** Active
**Priority:** Medium

## Goal/Scope

Harden the packaging, versioning, and release infrastructure so that
installs are reproducible, artifacts are clean, and the project is ready
for a public versioning scheme.

## Context

Baseline packaging is in place (`pyproject.toml`, `requirements.txt`,
`tox.ini`, optional dependency groups). This project tracks the remaining
hardening work: `.gitignore` expansion, versioning policy, release workflow
documentation, and resolving the flat-vs-`src/` layout question.

The layout decision is intentionally deferred until project-023 (Package
Reorganization) is planned, as the two are coupled.

## Completed

- [x] `pyproject.toml` with PEP 621 build and project metadata.
- [x] Runtime dependency manifest (`requirements.txt`).
- [x] Local test tooling (`tox.ini`, pytest/coverage config).
- [x] Optional dependency groups (`[dev]`, `[pandas]`) in package metadata.

## TODO checklist

- [ ] Expand `.gitignore` to cover standard Python build/test artifacts
      (`*.egg-info/`, `dist/`, `build/`, `.tox/`, `.coverage`, `htmlcov/`,
      `.env`, `.venv/`).
- [ ] Define versioning scheme (CalVer or SemVer) and document in
      `develop_guide/`.
- [ ] Add release checklist or GitHub Actions release-on-tag workflow.
- [ ] Document install and test commands for contributors in the developer
      guide.
- [ ] Coordinate with project-023 on the flat-vs-`src/` layout decision
      (layout migration is project-023 scope; this project documents the
      chosen convention).

## Exit criteria

- [ ] `.gitignore` covers all standard Python artifacts.
- [ ] Versioning policy is documented and the version field in
      `pyproject.toml` follows it.
- [ ] A contributor can install, test, and build by following documented
      commands.

## Challenges and mitigations

- **Challenge:** Layout decision is coupled to package reorganization.
  **Mitigation:** Defer layout migration to project-023; this project
  documents the convention once decided.

- **Challenge:** Choosing a versioning scheme for a pre-1.0 library.
  **Mitigation:** Start with `0.x.y` SemVer; upgrade to CalVer or `1.0`
  only when the public API is stable.

## Completion Assessment (2026-02-18)

- [x] Packaging baseline is implemented (`pyproject.toml`, `requirements.txt`, `tox.ini`).
- [x] CI install path for contributors is documented in workflow (`pip install -e ".[dev]"`).
- [ ] `.gitignore` is still missing several artifacts tracked in this project (`dist/`, `build/`, `.tox/`, `htmlcov/`, virtualenv folders).
- [ ] Versioning policy is still not documented in developer docs; package version remains placeholder-style (`0.0.0`).
- [ ] Release workflow/checklist is not yet defined.

**Result:** Project remains **open**. Foundational packaging exists, but hardening deliverables are incomplete.

## Scope boundary (under umbrella project-032, Phase 0)

- **021 owns:** Versioning/release workflow, packaging hygiene (`.gitignore`, build artifact cleanup), contributor install/build documentation, layout convention documentation.
- **021 does not own:** Internal module decomposition, ownership matrix, or architecture decisions (those belong to 035/037).
- **023 coordination:** The flat-vs-`src/` layout decision is documented by 021 but implemented by 023. Layout migration is 023's scope.
- **Gate role:** Phase 2 project-023 (package reorganization) depends on 021's packaging gates being clean before moving modules into subpackages.
