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
   - target-view selector styling hooks
4. **Composed surfaces**
   - figure sidebar panels
   - legend style dialog
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
6. Shared buttons and tabs style both widget roots and inner native buttons.
7. Titles are plain content; typography comes from shared styling, not raw HTML emphasis markup.

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

## Anti-patterns to avoid

Do not reintroduce these patterns:

- generic button or dialog CSS inside feature modules
- raw viewport sizing for hosted dialogs
- raw `<b>` markup in shared dialog titles
- duplicated per-row style widgets for generic chrome
- feature-local focus ring styles
- persistent explanatory status bars that restate implementation details

## Guardrails

Use both tests and `tools/check_widget_layout.py` when changing layout code.
The guardrail tool checks for:

- hosted dialog width contracts
- required shared primitive usage
- legend header toolbar placement
- plain title content
- forbidden generic CSS duplication in feature modules

## Phase 0 note

The previous MathLive-specific control family and the legend-launched plot
editor were removed during Phase 0 decontamination. Rebuild phases should add
new layout examples only after they exist as small audited features.
