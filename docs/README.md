# Docs tracker

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

## Issue workflow (`docs/Bugs`)

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

## Project workflow (`docs/projects`)

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


## API examples policy

For plotting examples in docs and notebooks, use the callable-first API style:
- `fig.plot(expr_or_callable, x, ...)`
- `plot(expr_or_callable, x, ...)`
- range form: `plot(f, (x, xmin, xmax), ...)`

Use callable-first examples consistently in documentation and notebooks.

## Legend workflow and migration notes

The toolkit now treats the **sidebar legend panel** as the primary legend UI for notebook workflows.

- Use the per-row legend checkbox in the sidebar to show/hide plots.
- Legend rows are filtered by the **active view tab**.
- Plot labels support plain text and LaTeX-style math markup through the panel renderer.

### Mapping from old Plotly legend behavior

- Old: click Plotly legend entries in-chart to toggle traces.
- New: use the legend side-panel checkbox next to each plot label.

- Old: rely on `"legendonly"` visibility as a user-facing state.
- New: prefer boolean visibility (`True`/`False`) controlled by the side panel; legacy `"legendonly"` is compatibility-only.

- Old: `showlegend=True` as the default interactive legend surface.
- New: toolkit-owned side panel is the canonical legend interaction path; Plotly legend is no longer required for normal usage.
