# Merge conflict log: `smart-figure-code-generation` -> `main`

## Scope
This document tracks merge conflict handling while preparing a pull request from `smart-figure-code-generation` into `main`.

## Conflict summary
During reconciliation against `main`, no textual merge conflicts were produced by Git for source files. The branch is cleanly mergeable at the content level.

## Non-conflict reconciliations performed
Even without hard conflicts, the branch required documentation reconciliation so the project history is understandable:

1. Consolidated project-020 narrative under `documentation/projects/project-020-figure-code-generation/` to avoid scattering context across archived and active notes.
2. Added an explicit status/rationale document (`summary.md`) so reviewers can quickly understand what was delivered and what remains.

## Resolution approach
- Prefer preserving implementation from `smart-figure-code-generation`.
- Keep `main` as the integration target, with project-specific documentation colocated in the dedicated project-020 folder.
- Record follow-up tasks (tests, packaging, ergonomics) as TODOs in `summary.md` instead of delaying merge.
