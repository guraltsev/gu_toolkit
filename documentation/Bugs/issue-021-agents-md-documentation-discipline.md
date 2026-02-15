# Issue 021: Propose AGENTS.md documentation discipline aligned with current repository practices

## Status
Open

## Summary
The repository already shows strong documentation habits in many core modules (module docstrings, class/function docstrings, and public API narrative docs), but enforcement is uneven across utility modules. We should introduce `AGENTS.md` guidance that preserves the current high standard while making expectations explicit and practical for contributors.

Given this repository structure, a **single root `AGENTS.md`** is useful, and a **nested `documentation/AGENTS.md`** is also appropriate so documentation issue/project workflows remain consistent with `documentation/README.md` conventions.

## Evidence
- Core modules such as `Figure.py`, `NamedFunction.py`, and `__init__.py` already include extensive module/class/function documentation and examples.
- Utility-oriented modules (for example `numeric_operations.py`) still expose public functions but currently do not consistently provide per-function docstrings/examples.
- The repository has documentation lifecycle conventions already codified in `documentation/README.md` (issue/project structure, naming, closure workflow), which are better enforced by a scoped nested `AGENTS.md` under `documentation/`.

## Proposal
Add the following files.

### Proposed file 1: `AGENTS.md` (repo root)

```md
# AGENTS.md — API Documentation and Contributor Discipline

This repository is notebook-facing and API-facing. Preserve the existing documentation quality in core modules and extend it consistently to utility modules.

## Non-negotiable documentation rules
- Every **public-facing** function/class/module MUST be documented.
- Public-facing functions SHOULD include at least one runnable example (doctest-style or short snippet) when practical.
- For small/simple public helpers, a concise usage snippet is acceptable instead of full doctest formatting.
- Private helpers SHOULD include a short docstring stating purpose + important invariants/assumptions.

## What counts as "public-facing" in this repo
- Anything re-exported from `__init__.py` / notebook namespace or exposed as part of user workflow.
- CLI/notebook entrypoints, integration hooks, and top-level helpers users are expected to call.
- Functions/classes listed in docs, guides, or examples.

## Module-level documentation
- Each module should start with a brief docstring explaining:
  - what the module is for,
  - key concepts/structure,
  - important gotchas.

## README/docs maintenance
- If behavior, configuration, or public API changes, update docs in the same change.
- In this repository, that typically means one or more of:
  - `documentation/README.md`
  - `documentation/develop_guide/*.md`
  - project/issue/discussion docs where behavior is tracked.
- If no docs update is needed, state why in the PR summary.

## Completion checklist (before finalizing)
- [ ] Added/updated docstrings (public: clear usage; private: concise intent/invariants)
- [ ] Added/updated examples for new/changed public API where practical
- [ ] Updated module docstrings if structure changed
- [ ] Updated README/docs when public behavior changed (or explained why not)
- [ ] Ran tests/lint relevant to touched code
```

### Proposed file 2: `documentation/AGENTS.md` (scoped to docs tree)

```md
# AGENTS.md — Documentation Tree Workflow Rules

This file applies to everything under `documentation/`.

## Follow documentation lifecycle conventions
- Treat `documentation/README.md` as the source of truth for issue/project workflow.
- New defects go under `documentation/Bugs/` with stable, sortable filenames.
- Completed issues move to `documentation/Bugs/closed/`.
- New implementation roadmaps go under `documentation/projects/`.

## Required structure for issue files
- Title (`Issue NNN: ...`)
- Status
- Summary
- Evidence
- TODO checklist
- Exit criteria

## Required structure for project files
- Title + project ID
- Status
- Goal/Scope
- TODO checklist
- Exit criteria

## Hygiene
- Keep checklists current.
- Update links/references when files move.
- Do not create new content under retired buckets.
```

## TODO
- [ ] Review proposal wording and decide whether to require examples as MUST vs SHOULD for all public functions.
- [ ] If approved, add root `AGENTS.md`.
- [ ] If approved, add `documentation/AGENTS.md` for scoped docs process rules.

## Exit Criteria
- [ ] Team agrees on the proposed `AGENTS.md` scope and strictness.
- [ ] Approved `AGENTS.md` file(s) are added to the repository.
- [ ] Subsequent PRs demonstrate adherence (docstrings/examples/docs updates when applicable).
