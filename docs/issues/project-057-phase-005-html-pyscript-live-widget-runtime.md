# Project 057 / Phase 005: HTML PyScript live widget shell surface

## Status
Proposed (revised)

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Support standalone HTML files with inline PyScript + a Pyodide kernel by injecting a **live widget runtime** and mounting the same peer section widgets into responsive HTML slots.

This phase is the concrete second transport target for the revised section model.

## Current context
The repository already has important runtime pieces:

- Pyodide/browser timing support in `src/gu_toolkit/runtime_support.py`
- Plotly FigureWidget support probing in `src/gu_toolkit/runtime_support.py`
- multiple anywidget-based components (`PlotlyPane`, legend bridges, sliders, sound helpers, `TabListBridge`)
- browser-side visibility / geometry logic already present in `PlotlyPane`

What it still does **not** have is:

- a standalone HTML widget manager / bootstrap
- an HTML slot-mount surface for section widget roots
- a transport-neutral figure mount contract that is not notebook-only

## What this phase must accomplish

### 1. Add a standalone HTML live widget bootstrap
Create the JavaScript / bootstrap layer needed to:

- start or connect to the Pyodide-backed widget runtime in the page
- load `ipywidgets` views correctly
- load `anywidget`-backed views correctly
- keep widget models live instead of statically embedding HTML

This phase must not fake interactivity with screenshots or static markup.

### 2. Add an HTML mount surface for peer section instances
Create the HTML-specific mount surface that can mount stable section widget roots into named DOM targets.

This mount surface must work with section instances, not singleton shell categories.

That means it must be able to mount, for example:

- multiple legend sections
- multiple info sections / info-card groups
- stage sections
- parameter sections
- output sections

into arbitrary `<div>` slots.

### 3. Make the DOM responsible for visibility
For standalone HTML, visibility should be controlled by the DOM / CSS shell.

That means:

- page switches should normally hide/show mounted sections instead of remounting them
- controls such as tabs or buttons should be shell controls over DOM visibility
- hidden sections should stay mounted where practical
- visible / hidden transitions should be available to the Python side as shell lifecycle signals

This is the key architectural simplification requested by the user.

### 4. Support both conventional and arbitrary section mapping
The HTML shell should support:

- the normal default arrangement where a plot is shown with its associated legend and info sections, and
- arbitrary mappings where the layout intentionally pairs unrelated sections.

The mount API therefore needs both:

- a default layout / template path that uses associations, and
- an explicit slot assignment path that can override those associations.

### 5. Preserve the “peer, not subordinate” rule in HTML
Do **not** create HTML APIs that imply legends or info cards must be children of a plot panel.

In HTML, just as in notebooks, sections are peers.

Associations may inform defaults, but the shell must still allow arbitrary remapping.

### 6. Ensure anywidget-based pieces keep working in standalone HTML
The HTML runtime must support the toolkit’s existing anywidget-backed pieces, including at least:

- `PlotlyResizeDriver`
- legend interaction / context bridge
- slider / modal bridges
- any accessibility bridge used for shell page controls

### 7. Provide canonical standalone HTML examples
Add at least:

- one conventional example showing a plot with its associated legend / info sections in a responsive layout
- one example or verification artifact showing that section mapping is arbitrary and not structurally subordinate

Those examples should demonstrate live widget mounting, not static embedding.

## Deliverables for this phase

- standalone HTML widget bootstrap/runtime support
- an HTML mount-surface API for peer section instances
- responsive slot-mount examples
- verification guidance for live widget behavior in standalone HTML
- at least one example proving that sections are peers rather than hard children of a plot panel

## Out of scope

- rewriting notebook presenters into a custom HTML UI
- abandoning `ipywidgets` / `anywidget`
- static export as a substitute for live runtime support
- final Plotly sizing sign-off across all arrangements

## Exit criteria

- [ ] A standalone HTML + inline PyScript page can run a live figure with a Pyodide-backed widget runtime.
- [ ] The same section widget roots used in notebook mode can be mounted into external HTML slots.
- [ ] DOM / CSS visibility controls the HTML shell rather than Python-only remount logic.
- [ ] Multiple legend and info sections can be mounted independently in standalone HTML.
- [ ] Conventional default arrangements and arbitrary remapped arrangements are both possible in standalone HTML.
- [ ] Anywidget-based toolkit helpers used by the figure shell still function in standalone HTML.
