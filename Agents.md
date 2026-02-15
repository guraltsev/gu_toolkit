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
