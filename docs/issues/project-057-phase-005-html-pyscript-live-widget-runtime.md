# Project 057 / Phase 005: HTML PyScript live widget runtime

## Status
Proposed

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Support standalone HTML files with inline PyScript + a Pyodide kernel by injecting a **live widget runtime** and mounting the same figure section widgets into responsive HTML slots.

This is the phase that turns the transport abstraction into a concrete second runtime target.

## Current context
The repository already has important runtime pieces:

- Pyodide/browser timer detection in `src/gu_toolkit/runtime_support.py:424-705`
- Plotly FigureWidget support probing in `src/gu_toolkit/runtime_support.py:708-854`
- multiple anywidget-based components throughout the toolkit (`PlotlyPane`, legend bridges, sliders, sound helpers, tabs)

What it does **not** have yet is a standalone HTML widget manager/bootstrap layer or a mount surface for placing live widgets into named HTML containers.

That is the exact missing piece for the requested HTML + PyScript target.

## What this phase must accomplish

### 1. Add a standalone HTML live widget bootstrap
Create the JavaScript/bootstrap layer needed to:

- start or connect to the Pyodide-backed widget runtime in the page
- load `ipywidgets` views correctly
- load `anywidget`-backed views correctly
- keep widget models live rather than statically embedded

This phase must not fake interactivity with static HTML snapshots.

### 2. Add an HTML display surface / mount surface
Create the HTML-specific display surface that can mount stable section-root widgets into named DOM targets.

This surface should support the slot-based shell model introduced earlier so HTML arrangement can be controlled by normal responsive CSS and DOM layout rather than by a notebook-only widget tree.

### 3. Support responsive div-based arrangements
The HTML target should be able to place the live widget roots into external `<div>` targets, for example:

- figure stage in one div
- legend in another div
- parameters in a third div
- shell tabs or alternate regions in their own targets

This directly addresses the requirement to constrain live widget outputs to different divs in responsive HTML.

### 4. Ensure anywidget-based toolkit pieces work in standalone HTML
The HTML runtime must support the toolkit’s existing anywidget-backed pieces, including at least:

- `PlotlyResizeDriver`
- legend interaction/context bridge
- slider/modal bridges
- tab accessibility bridge if used

### 5. Provide at least one canonical standalone HTML example
Add an example or verification artifact showing how to:

- start the runtime
- create the figure from PyScript/Python
- mount the figure sections into named HTML regions
- choose a non-default arrangement (for example legend below or legend in a separate tab/page)

## Deliverables for this phase

- standalone HTML widget bootstrap/runtime support
- HTML display surface / mount API
- responsive slot-mount example(s)
- verification guidance for live widget behavior in standalone HTML

## Out of scope

- rewriting notebook presenters
- abandoning `ipywidgets`/`anywidget`
- static embed/export as a substitute for live widget runtime support
- final Plotly sizing sign-off across all arrangements

## Exit criteria

- [ ] A standalone HTML + inline PyScript page can run a live figure with a Pyodide-backed widget runtime.
- [ ] The same section-root widgets used in notebook mode can be mounted into external HTML slots.
- [ ] Non-default arrangements such as hidden/bottom/tab legend placement are possible in standalone HTML.
- [ ] Anywidget-based toolkit helpers used by the figure shell still function in standalone HTML.
