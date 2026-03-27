# UI layout system

This repo now has one shared UI and layout layer for notebook widgets. The goal
is to keep feature ownership where it already works well while moving generic
chrome into one documented system.

## Ownership model

The shared layer lives in `src/gu_toolkit/ui_system.py`.

It provides four levels:

1. **Tokens**
   - spacing scale
   - radii
   - control heights
   - typography sizes and weights
   - surface, border, and state colors
   - dialog width tokens
   - focus ring treatment
2. **Layout primitives**
   - section panels
   - dialog header/body/footer
   - action bars
   - tab bars
   - form sections
   - inline alerts
   - readonly value surfaces
3. **Control helpers**
   - primary, secondary, and tab buttons
   - icon buttons
   - shared text/dropdown/checkbox styling hooks
   - MathLive control styling hooks
   - target-view selector styling hooks
4. **Composed surfaces**
   - figure sidebar panels
   - legend style dialog
   - plot editor
   - slider parameter settings dialog

`src/gu_toolkit/widget_chrome.py` continues to own the browser-side bridge
widgets that need JavaScript behavior, such as modal focus handling and tab
keyboard semantics, while re-exporting the shared helpers for existing imports.

## Non-negotiable layout contracts

These invariants should stay true across future UI work:

1. Hosted dialogs are container-relative, never viewport-relative.
2. Shrinking wrappers set `min-width: 0`.
3. Shared containers default to `width: 100%` and `max-width: 100%`.
4. Standard dialogs use one vertical scroll region rather than nested traps.
5. Standard figure panels and hosted dialogs do not allow horizontal scrolling.
6. Plot type and independent-variable controls stay colocated.
7. Shared buttons and tabs style both widget roots and inner native buttons.
8. Titles are plain content; typography comes from shared styling, not raw HTML
   emphasis markup.
9. Routine validation stays inline in the dialog instead of opening a nested
   error modal.

## How to build new surfaces

Prefer composition over local CSS.

### Panels

Use `build_section_panel(...)` when you need a sidebar or output surface with:

- shared border and radius
- internal title row
- optional header toolbar slot
- overflow-safe body container

### Dialogs

Use the following building blocks together:

- `build_dialog_header(...)`
- `build_form_section(...)`
- `build_action_bar(...)`
- `build_modal_panel(...)`
- `build_modal_overlay(...)`

Use `hosted_modal_dimensions(...)` for hosted dialogs so width calculations stay
container-relative.

### Controls

Apply `configure_control(...)` or `configure_action_button(...)` instead of
restyling feature widgets locally. This keeps button, focus, invalid, and tab
behavior visually consistent.

### Math input

`MathLiveField` opts into the shared control family through the classes
`gu-control` and `gu-control-math`. Feature modules should not restyle its
border, background, radius, font sizing, or padding locally.

## Plot editor structure

The plot editor is the canonical example of the shared system.

### Header

The header uses one title, `Plot editor`, plus optional plain context text in
edit mode such as `Editing f_0`.

### Tabs

There are three tabs:

- `Expression`
- `Style`
- `Advanced`

They are real tabs with shared tab-button styling and keyboard semantics from
`TabListBridge`.

### Expression tab

The first row always defines the mathematical contract:

- cartesian: plot type + variable
- parametric: plot type + parameter + min + max
- field modes: plot type + x variable + y variable

The expression fields come after that setup row.

### Style tab

The style tab holds the per-curve display controls that used to live in the
legend line-style dialog:

- **Display**: visibility
- **Line style**: color, width, opacity, and dash for cartesian/parametric curves

### Advanced tab

The advanced tab is grouped by user intent rather than construction order:

- **Placement**: target views
- **Identity**: label and plot id presentation
- **Resolution**: samples or grid sizes

The target-view table stays available even when only the default `main` view
exists.

### Validation

Routine validation uses inline alerts inside the relevant tab. The dialog stays
open, the failing tab becomes active, and the relevant controls are marked
invalid. The secondary error modal is reserved for non-routine failures.

## Anti-patterns to avoid

Do not reintroduce these patterns:

- generic button or dialog CSS inside feature modules
- raw viewport sizing for hosted dialogs
- raw `<b>` markup in shared dialog titles
- duplicated per-row style widgets for generic chrome
- feature-local focus ring styles
- nested validation modals for normal form errors
- persistent explanatory status bars that restate implementation details

## Guardrails

Use both tests and `tools/check_widget_layout.py` when changing layout code.
The guardrail tool checks for:

- hosted dialog width contracts
- required shared primitive usage
- legend header toolbar placement
- plot-editor inline validation behavior
- plain title content
- MathLive shared-control adoption
- forbidden generic CSS duplication in feature modules
