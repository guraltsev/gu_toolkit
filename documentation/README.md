# Documentation Organization

This folder uses a lightweight lifecycle model:
- **Issues (`Bugs/`)** track defects with clear reproduction/fix criteria.
- **Projects (`projects/`)** track scoped bodies of work with TODO checklists.
- **Discussions (`Discussions/`)** hold exploratory design notes that are not yet executable plans.
- **Developer guides (`develop_guide/`)** document implementation behavior and architecture.


## Top-level sections

- `Bugs/`: active issues/bug reports.
- `Bugs/_closed/`: resolved issues.
- `projects/`: active project plans.
- `projects/_completed/`: completed project records.
- `Discussions/`: exploratory/decision content.
- `develop_guide/`: durable implementation guides.

---

## Issue workflow (`documentation/Bugs`)

### Active issue file requirements
Each active issue file should contain:
1. **Title** (`Issue NNN: ...`).
2. **Status** (`Open`, `Blocked`, `In Progress`, etc.).
3. **Summary** (1-3 paragraphs).
4. **Evidence** (files/tests/observed behavior).
5. **TODO checklist** with actionable tasks.
6. **Exit criteria** (what must be true to close it).

### Issue naming
Use stable, sortable names:
- `issue-018-short-description.md`

### Closing issues
When fixed or otherwise resolved:
1. Move file to `Bugs/_closed/`.
2. Update status/disposition in the file body.
3. Keep original issue ID in filename.
4. Link to validating tests/commits when available.

---

## Project workflow (`documentation/projects`)

### Active project file requirements
Every active project should include:
1. **Title + project ID** (`Project NNN: ...`).
2. **Status** (`Backlog`, `Active`, `Discovery`, `Blocked`).
3. **Goal/Scope** section.
4. **TODO checklist** of remaining work.
5. **Exit criteria** (completion definition).

### Preferred project structures
Use one of these patterns:
- **Single-file project**: `project-0NN-topic.md`.
- **Project folder**: `project-0NN-topic/plan.md` + `summary.md` (for larger efforts).

### Completing projects
When a project is done:
1. Move file/folder to `projects/_completed/`.
2. Mark final status and completion date.
3. Leave a concise summary of delivered outcomes.

---

## Documentation hygiene rules

1. **No stale buckets**: do not add new files under `refactor/`.
2. **Keep TODOs current**: update checklists whenever scope/status changes.
3. **Prefer executable tracking**: defects -> issues, implementation roadmaps -> projects.
4. **Update links after moves**: ensure cross-references remain valid.
5. **Use consistent IDs**: new issues/projects should use the next available number.
