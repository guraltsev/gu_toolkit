# Project 057 / Phase 004: Jupyter shell surface and default-layout migration

## Status
Proposed (revised)

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Build the concrete **Jupyter shell surface** on top of the peer-section model from Phase 003 and migrate the default notebook behavior onto that model.

This phase is where the new section registry becomes a working notebook shell without falling back into:

- singleton legend / info assumptions,
- view-centric shell rules,
- or a large navigation abstraction stack.

## Current context
The repo already has a notebook layout manager and shell pages, but they are still tied to the pre-revision model.

Relevant evidence:

- `src/gu_toolkit/figure_layout.py:326-505` builds one notebook root tree with one view selector, one stage, and singleton section panels.
- `src/gu_toolkit/figure_layout.py:2192-2249` applies visibility by toggling singleton section panels and one active shell page.
- `src/gu_toolkit/figure_layout.py:629-635` still materializes display as a notebook `OneShotOutput`.
- `src/gu_toolkit/Figure.py:3818-3901` still routes display through notebook-only `display(...)` calls.

Those are useful notebook stepping stones, but not yet the final notebook shell surface for the revised section model.

## What this phase must accomplish

### 1. Build a notebook shell surface over peer section instances
Implement the concrete notebook composition layer that can mount section widget roots into notebook widget containers according to the new layout spec.

This surface should work with section instances such as:

- one or more stage sections
- zero or more legend sections
- zero or more info sections / info-card groups
- parameter sections
- output sections

The shell surface should not assume that “legend” and “info” are singletons.

### 2. Keep notebook visibility presentation-owned
The notebook shell should decide which mounted sections are visible.

That means:

- shell page containers or regions may toggle `layout.display` / CSS classes
- controls like tab bars or buttons are just shell controls over visibility
- hidden sections stay mounted where practical instead of being recreated or deeply re-parented on every switch

The shell must emit visibility lifecycle events that later phases can use for Plotly refresh / reflow.

### 3. Make the default notebook layout conventional, not restrictive
The default layout should continue to feel close to today’s notebook behavior.

But it should now be built from:

- peer section instances
- soft associations
- notebook regions / pages

The normal default code path should generate something like:

- a plot / stage section
- its associated legend section in the conventional side or bottom placement
- its associated info sections in a conventional nearby placement
- the shared parameter section
- the output section below

However, the underlying model must still allow arbitrary remapping.

### 4. Keep view selection as a compatibility surface, not as the new shell primitive
Notebook view switching may continue to exist where it already exists.

But in this phase:

- do not expand view-centric shell APIs
- do not make new legend or info notebook logic depend on active-view filtering
- do not make the new shell design revolve around the view selector

If a notebook control still selects the active plotting view, that is a compatibility feature, not the conceptual center of the shell.

### 5. Implement the notebook display surface boundary
The notebook implementation should no longer treat `OneShotOutput` as the only meaningful display contract.

The new notebook shell surface should expose a clear mount / display boundary such as:

- a root widget surface for reuse, and
- an optional notebook-cell materializer for compatibility with `display(fig)` / `fig.show()`.

This is still notebook-specific, but it should now live behind an explicit notebook display-surface boundary rather than as the figure’s only transport model.

### 6. Reuse existing notebook widget infrastructure
Reuse existing toolkit infrastructure where it helps:

- section chrome in `ui_system.py`
- `TabListBridge` where page accessibility is useful
- existing modal helpers
- anywidget-backed controls already used by the toolkit

The notebook migration should not introduce a parallel custom UI layer.

### 7. Preserve JupyterLab and JupyterLite + Pyodide behavior
This phase must keep notebook behavior working in both supported notebook environments.

That includes at least:

- JupyterLab
- JupyterLite + Pyodide

and must not silently break anywidget-backed notebook helpers already used by the figure shell.

## Deliverables for this phase

- the concrete notebook shell surface for peer section instances
- a notebook display-surface / mount path
- a default notebook layout builder that uses soft associations but does not enforce them
- notebook visibility lifecycle hooks for later Plotly hardening work
- updated notebook-focused tests and regression checks

## Out of scope

- standalone HTML widget runtime bootstrap
- final Plotly sizing sign-off across all arrangements
- removal of legacy view APIs from the public surface
- a custom notebook UI system unrelated to `ipywidgets` / `anywidget`

## Exit criteria

- [ ] JupyterLab still works on the peer-section model.
- [ ] JupyterLite + Pyodide still works on the peer-section model.
- [ ] The default notebook layout remains functionally close to today, except the full-width toggle is gone.
- [ ] The default notebook path conventionally places associated legends / info near their related plot sections without enforcing ownership.
- [ ] Notebook visibility is controlled by the shell surface rather than by singleton section assumptions.
- [ ] Notebook display is implemented through an explicit notebook mount/display boundary rather than as the figure’s only transport path.
- [ ] Existing anywidget-based notebook helpers continue to function.
