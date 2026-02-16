# AGENTS.md — Documentation Tree Workflow Rules

This file applies to everything under `docs/`.

## Follow documentation lifecycle conventions
- New defects go under `docs/Bugs/` with stable, sortable filenames.
- Completed issues move to `docs/Bugs/_closed/`.
- New implementation roadmaps go under `docs/projects/`.
- Completed projects move to `docs/projects/_completed/`.
- Make sure `docs/README.md` is up to date with current best practices and organization of this project. Do not include specific bug information in `docs/README.md`

## Required structure for issue files
Should contain at least the following as top level sections
- Title (`Issue NNN: ...`)
- Status
- Summary
- Evidence
- TODO checklist
- Exit criteria

## Required structure for (small) project files 
Should contain at least the following as top level sections
- Title + project ID
- Status
- Goal/Scope
- TODO checklist
- Exit criteria

## Required structure for (larger) project files
- FOLDER with information
	- Summary.md
	Should contain at least the following as top level sections
		- Title + project ID
		- Goal/Scope
		- Summary of design
		- Open questions (if any)
		- Challenges and mitigations
		- Status
		- TODO checklist
		- Exit criteria
	- Plan.md 
	Should contain at least the following as top level sections
		- Detailed blueprint for implementation
		- Description of test suite for acceptance
		- Preferably, list of phases that leave the whole toolkit in a consistent and functioning state
		- If impossible, description and mitigation.


## Hygiene
- Keep checklists current.
- Update links/references when files move.
- Do not create new content under retired buckets.
