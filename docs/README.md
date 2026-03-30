# Docs tracker

This folder uses a lightweight lifecycle model:

- **Bugs (`issues/`)** track defects with clear reproduction/fix criteria.
- **Projects (`issues/`)** track scoped bodies of work with TODO checklists.
- **Discussions (`Discussions/`)** hold exploratory design notes that are not yet executable plans.
- **Developer guides (`guides/`)** document implementation behavior and architecture.

## Top-level sections

- `issues/`: active bug reports and projects.
- `issues/_closed/`: resolved issues and completed projects.
- `Discussions/`: exploratory/decision content.
- `develop_guide/`: durable implementation guides.

---

## Selected guides

- `guides/develop_guide.md`: architecture ownership map and maintenance rules.
- `guides/legend-plot-editor.md`: legend-driven plot creation and editing UI.
- `guides/ui-layout-system.md`: shared tokens, primitives, invariants, and layout guardrails.
- `guides/parametric-plotting.md`: public API and implementation notes for
  parametric curves.
- `guides/render-batching-and-snapshots.md`: render queue + snapshot pipeline.
- `guides/parameter-animation.md`: animation behavior and public API.
- `guides/parameter-key-semantics.md`: name-authoritative parameter identity rules.
- `guides/scalar-field-styling.md`: contour and temperature styling, palettes, range control, and diffraction-oriented examples.
- `guides/api-discovery.md`: task-oriented map from user goals to the right public APIs, guides, examples, and tests.
- `guides/public-api-documentation-structure.md`: required structure and discoverability rules for public docstrings.

---

## Issue workflow (`docs/issues`)

### Issue naming

Use stable, sortable names:

- `bug-018-short-description.md`
or
- `project-018-short-description.md`


### Active bug file requirements

Each active issue file should contain:

1. **Title** (`Issue NNN: ...`).
2. **Status** (`Open`, `Blocked`, `In Progress`, etc.).
3. **Summary** (1-3 paragraphs).
4. **Evidence** (files/tests/observed behavior).
5. **TODO checklist** with actionable tasks.
6. **Exit criteria** (what must be true to close it).

### Closing issues

When fixed or otherwise resolved:

1. Move file to `issues/_closed/`.
2. Update status/disposition in the file body.
3. Keep original issue ID in filename.
4. Link to validating tests/commits when available.


### Active project file requirements

Every active project should include:

1. **Title + project ID** (`Project NNN: ...`).
2. **Status** (`Backlog`, `Active`, `Discovery`, `Blocked`).
3. **Goal/Scope** section.
4. **TODO checklist** of remaining work.
5. **Exit criteria** (completion definition).

### Preferred project structures

Use a **project folder** by default:

- `project-0NN-topic/summary.md`
- `project-0NN-topic/plan.md` (optional only when implementation planning is not yet decided)

Legacy single-file projects may exist, but new projects should use the folder structure so summary and execution planning stay separated.

### Completing projects

When a project is done:

1. Move file/folder to `projects/_completed/`.
2. Mark final status and completion date.
3. Leave a concise summary of delivered outcomes.

---

## Documentation hygiene rules

1. **Keep TODOs current**: update checklists whenever scope/status changes.
2. **Prefer executable tracking**: defects -> issues, implementation roadmaps -> projects.
3. **Update links after moves**: ensure cross-references remain valid.
4. **Use consistent IDs**: new issues/projects should use the next available number.
