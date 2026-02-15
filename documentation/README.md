# Documentation Organization

This folder uses a lightweight lifecycle structure so active work is easy to find and completed work is archived without losing history.

## Top-level sections

- `Bugs/`: issue reports and bug-tracking notes.
- `projects/`: project-level planning and execution notes.
- `Discussions/`: exploratory notes and decision discussions.
- `develop_guide/`: developer-facing implementation guides.
- `refactor/`: larger technical design and refactor proposals.

## Bug workflow (`documentation/Bugs`)

- `documentation/Bugs/`: active or triaged bug reports.
- `documentation/Bugs/closed/`: resolved bugs (fixed, invalid, or otherwise finished).

### Bug file naming

Use stable issue identifiers, for example:

- `issue-018-short-description.md`
- `bug-021-short-description.md`

## Project workflow (`documentation/projects`)

- `documentation/projects/`: active projects.
- `documentation/projects/_completed/`: completed projects.

Each project should usually live in its own folder and include:

- `summary.md`: rationale, scope, and status snapshot.
- `plan.md`: phased implementation plan and checklist.

If a project is represented by a single standalone markdown file, move that file into `_completed/` when the project is done.

## Lifecycle rules

1. Start new work in the active folders:
   - `Bugs/`
   - `projects/`
2. When work is completed, move files/folders to:
   - `Bugs/closed/`
   - `projects/_completed/`
3. Keep references up to date when paths change.
