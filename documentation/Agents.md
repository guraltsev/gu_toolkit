# AGENTS.md — Documentation Tree Workflow Rules

This file applies to everything under `documentation/`.

## Follow documentation lifecycle conventions
- Treat `documentation/README.md` as the source of truth for issue/project workflow.
- New defects go under `documentation/Bugs/` with stable, sortable filenames.
- Completed issues move to `documentation/Bugs/_closed/`.
- New implementation roadmaps go under `documentation/projects/`.
- Completed projects move to `documentation/projects/_completed/`.

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
