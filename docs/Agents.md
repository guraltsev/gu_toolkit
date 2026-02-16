# AGENTS.md — Documentation Tree Workflow Rules

This file applies to everything under `docs/`.

## Follow documentation lifecycle conventions
- New defects go under `docs/Bugs/` with stable, sortable filenames (DO NOT put open issues in `open` subfolder).
- Completed issues move to `docs/Bugs/_closed/` (note the underscrore).
- New implementation roadmaps go under `docs/projects/` (DO NOT put open issues in `open` subfolder).
- Completed projects move to `docs/projects/_completed/`(note the underscrore).
- Make sure `docs/README.md` is up to date with current best practices and organization of this project. Do not include specific bug information in `docs/README.md`
- NEVER delete issues/projects. Just move them to closed/completed when they are done. 

## Required structure for issue files (markdown)
Should contain at least the following as top level sections
- Title (`Issue NNN: ...`)
- Status
- Summary
- Evidence
- TODO
- Exit criteria

## Required structure for project files
Projects should generally be contained in a named folder with files providing information
- Summary.md
	Should contain at least the following as top level sections
		- Title + project ID
		- Goal/Scope
		- Summary of design
		- Open questions (if any)
		- Challenges and mitigations
		- Status
		- TODO
		- Exit criteria
- Plan.md 
	Should contain at least the following as top level sections
		- Detailed blueprint for implementation
		- Description of test suite for acceptance
		- Preferably, list of phases that leave the whole toolkit in a consistent and functioning state
		- If impossible, description and mitigation.

If plan has not been decided on yet, it is acceptable for plan.md to be missing. 


## Hygiene
- Keep checklists current.
- Update links/references when files move.
- Do not create new content under retired buckets.
