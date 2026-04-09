# Project 057 / Phase 001: architecture and boundaries

## Status
Proposed

## Project link
[Project 057 - Figure shell presentation/runtime refactor](project-057-figure-shell-presentation-runtime-refactor.md)

## Phase goal
Define the internal architecture and migration boundaries that later phases will implement.

This phase exists to prevent the refactor from turning into another round of shallow file shuffling. The current issue is structural: logic, presentation, shell arrangement, and display transport are fused together. Before moving code, the repository needs a clear internal contract for what will own state, what will own widgets, and what will own display/mount behavior.

## Why this phase is necessary
The current code proves that boundaries are blurred:

- `Figure` passes concrete widget boxes and modal hosts into managers (`src/gu_toolkit/Figure.py:414-468`).
- `FigureLayout` is simultaneously shell policy and one concrete notebook widget tree (`src/gu_toolkit/figure_layout.py:249-423`).
- `ParameterManager` mutates `layout_box.children` directly while also owning parameter state (`src/gu_toolkit/figure_parameters.py:198-374`).
- `LegendPanelManager` mixes plot state, dialog state, anywidget bridges, and direct widget parenting (`src/gu_toolkit/figure_legend.py:772-1012`, `1518-1587`).
- Notebook display is hard-coded through `display(self._layout.output_widget)` (`src/gu_toolkit/Figure.py:3800-3883`).

Without a deliberate contract, implementation work in later phases will drift back into the same coupling.

## What this phase must accomplish

### 1. Define the ownership model
Write down, in code comments or architecture docs accompanying the implementation, the intended responsibilities for:

- figure orchestration logic
- shell layout policy
- section controllers/state
- section presenters/widgets
- notebook display surface
- HTML display surface
- geometry/reflow signaling

The exact class names can vary, but these ownership boundaries must be explicit.

### 2. Define the core internal interfaces or protocols
Create the internal seam definitions needed for later phases. Example concepts:

- shell spec / arrangement object
- section presenter protocol
- section controller/state protocol
- display surface / mount surface protocol
- geometry-change / reflow callback contract
- tab-selection model contract

The implementation can use `Protocol`, ABCs, dataclasses, simple internal classes, or another lightweight pattern. The important part is the boundary, not the exact language feature.

### 3. Define the migration map from current classes to future roles
For each of the current heavy classes, record whether it will be:

- kept mostly as-is
- narrowed into one role
- split into controller + presenter pieces
- deprecated internally and replaced

At minimum this must cover:

- `Figure`
- `FigureLayout`
- `ParameterManager`
- `LegendPanelManager`
- current tab/view-selector handling
- display entrypoints (`show`, `_ipython_display_`)

### 4. Preserve the known-good cores
This phase must explicitly declare which pieces should remain central and should not be rewritten casually:

- `View`
- `ViewManager`
- `PlotlyPane`
- runtime timer support in `runtime_support.py`

Those parts are not the core source of the current problem.

### 5. Define the public-API compatibility strategy
Record how the refactor will preserve or intentionally extend:

- `Figure(...)`
- `show()`
- notebook rich display
- parameter authoring calls
- legend behavior from a user perspective
- view selection semantics
- any future layout/presentation configuration entrypoint

This phase should decide whether arrangement is configured at construction time, through a setter, through presets, through a spec object, or some combination of those.

### 6. Define the test plan for the rest of the project
Record what kinds of tests later phases must add or update:

- section-controller tests without full notebook layout dependency
- JupyterLab/JupyterLite regression tests
- shell arrangement tests
- HTML standalone runtime tests or manual verification surfaces
- Plotly sizing/reflow validation

## Deliverables for this phase

- a clear internal ownership map
- the chosen internal contracts/protocols for shell, sections, display surfaces, and geometry signaling
- a migration map from current classes to future boundaries
- a compatibility plan for public authoring/display APIs
- a concrete test strategy for later phases

## Out of scope

- implementing new arrangements
- splitting parameter or legend code yet
- adding HTML runtime support yet
- changing Plotly sizing behavior yet
- rewriting `View`/`PlotlyPane`

## Exit criteria

- [ ] There is one documented ownership model for shell, sections, and display surfaces.
- [ ] Later phases can point to concrete internal contracts instead of inventing new boundaries ad hoc.
- [ ] There is an explicit migration decision for `FigureLayout`, `ParameterManager`, `LegendPanelManager`, and tabs/navigation.
- [ ] The project can proceed without ambiguity about where notebook-specific code should live and where HTML-specific mounting should live.

# **Project 057 / Phase 001 — Addendum (Post-Failure Correction)**

## Status

Mandatory corrective addendum for next implementation attempt

---

## 1. Summary of failure

The previous implementation failed because it introduced an **abstract shell architecture** instead of defining a **concrete mounting model**.

Specifically, it:

* introduced conceptual entities (e.g. “placement”, “regions”, “section protocols”) that do not correspond to real runtime behavior
* attempted to design a generalized layout system prematurely
* encoded architecture planning into Python classes instead of implementation seams
* drifted away from how the system actually renders (widgets + DOM)

This resulted in:

* unnecessary indirection
* unclear execution model
* no direct path to HTML mounting
* no improvement in real flexibility

The failure is **not about incorrect details**.
It is about choosing the wrong level of abstraction.

---

## 2. Core correction

The shell must **not** be described by a Python model.

The shell must be:

> **authored as concrete DOM structure, with explicit mount points**

There is **no layout DSL**, no placement system, and no abstract region model.

---

## 3. Required design direction

### 3.1 One shell = one root

Each figure owns a single root:

```html
<gufigure-shell>
  ...
</gufigure-shell>
```

All mounting is **strictly scoped to this root**.

No global queries. No global ids.

---

### 3.2 Mount points are explicit elements

Use semantic custom elements:

```html
<gufigure-title></gufigure-title>
<gufigure-viewselector></gufigure-viewselector>
<gufigure-plot name="main"></gufigure-plot>
<gufigure-legend></gufigure-legend>
<gufigure-parameters></gufigure-parameters>
<gufigure-info></gufigure-info>
<gufigure-output></gufigure-output>
```

Rules:

* element name defines *what it is*
* attributes (e.g. `name`) disambiguate multiples
* layout is controlled by CSS, not Python

---

### 3.3 No “placement” abstraction

The following must **not exist**:

* placement classes
* region enums
* layout DSLs
* “slot specification” objects
* any abstraction describing layout instead of executing it

Correct model:

> elements exist → code finds them → widgets mount into them

---

### 3.4 Mounting contract (central rule)

All sections must follow:

* expose a **single stable root widget**
* do **not** assume parent containers
* do **not** mutate layout trees directly

Mounting is performed by the shell host:

```
find element → attach widget view → done
```

Managers must **not**:

* receive layout boxes
* control parent structure
* know where they are placed

---

### 3.5 Plot mounting and future-proofing

Plot mounting must target:

```html
<gufigure-plot name="main"></gufigure-plot>
```

Important constraints:

* current system still uses **one active View**
* do not change View behavior
* do not implement multi-plot yet

But:

* mounting must assume **multiple plot elements may exist later**
* code must not hardcode “there is only one plot container”

---

### 3.6 Resizing model (non-negotiable)

Each `<gufigure-plot>` element is the **source of truth for size**.

Rules:

* attach a `ResizeObserver` to each plot element
* on resize → trigger PlotlyPane reflow
* no Python-side width/height orchestration
* no layout-driven pixel pushing

Additionally trigger reflow on:

* visibility changes
* shell changes
* (future) tab switches

---

### 3.7 Jupyter compatibility constraint

Mounting must occur:

> **inside a single widget-owned DOM subtree**

That means:

* shell is rendered by one host widget
* all `<gufigure-*>` elements live inside it
* child widgets are mounted inside those elements

Do **not**:

* mount into arbitrary document-level DOM
* rely on global document structure

---

### 3.8 Display boundary (minimal)

Only one abstraction is allowed:

* a minimal mount surface for:

  * notebook display
  * future HTML bootstrap

This must stay small and concrete:

* no framework
* no hierarchy of display classes

---

## 4. Explicit non-goals for next attempt

The following are forbidden in Phase 001:

* ❌ layout configuration systems
* ❌ placement / region abstractions
* ❌ presenter/controller protocol hierarchies
* ❌ tab system redesign
* ❌ view system changes
* ❌ multi-plot implementation
* ❌ HTML runtime implementation

---

## 5. Required minimal outcome

The next implementation must achieve only:

1. A shell host that renders `<gufigure-*>` structure
2. Managers expose stable root widgets
3. Mounting happens via DOM lookup within shell root
4. Plot resizing driven by element size observation
5. Figure display routed through a mount surface (not hardcoded display)

Nothing more.

---

## 6. Sanity check (must pass)

Before considering Phase 001 complete:

* Can two figures render on the same page without conflict?
* Can the legend be moved in HTML without touching Python?
* Can a second `<gufigure-plot>` be added without changing core logic?
* Does Plotly resize correctly when the plot container changes size?
* Does any manager still assume a specific parent container?

If any answer is “no”, the implementation is incorrect.

---

## 7. Guiding principle

> **Prefer concrete DOM over abstract architecture.**

If a concept cannot be directly mapped to:

* an element,
* a widget,
* or a mount operation,

it does not belong in this phase.
