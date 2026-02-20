# Project 034: Legend Panel UX Refresh

## Status
Discovery

## Goal/Scope

Upgrade the toolkit-owned sidebar legend so it supports richer interaction and visual affordances suitable for notebook workflows.

In scope:
- Reorder the sidebar so **Legend appears above Parameters**.
- Restyle legend rows as subtle, responsive tiles.
- Replace checkbox-driven visibility with tile-click behavior (except label hit area).
- Replace checkbox glyph with a styled circular visual indicator derived from trace style.
- Add clear disabled-state cues when a function is hidden.
- Add legend-row hover interactions that temporarily enlarge corresponding trace width (+15%).
- Improve responsive behavior for legend rows (min/max widths, side-by-side wrapping when space allows).
- Improve label fit handling (scale down up to 20%, then right-edge fade truncation, delayed full-label tooltip).

Out of scope:
- Editable labels (future feature), but this project must preserve a dedicated label click zone for future edit actions.
- General redesign of the full sidebar information architecture beyond legend placement/order and legend row UX.

## Summary of design

### Request analysis

The requested behavior is a substantial UX upgrade over the current v1 legend:
1. Layout priority change (legend before parameters).
2. A richer interaction model (row-level toggle, hover highlighting, click exclusion zone for label).
3. Visual parity with plotted traces (indicator fill + linestyle/width border semantics).
4. Advanced text-fit behavior for LaTeX labels (scale, fade truncation, delayed tooltip).

### Code analysis (current state)

Current implementation is intentionally minimal:
- `FigureLayout.sidebar_container` currently orders sections as Parameters → Info → Legend, so legend is below parameters today.
- `LegendPanelManager` currently renders each row as `HBox([Checkbox, HTMLMath])` and uses only checkbox state changes to control `plot.visible`.
- Row widgets currently do not define hover behavior, tile affordances, click-zone partitioning, responsive wrapping constraints, or delayed tooltips.
- Existing tests for Project 030 assert this current ordering and checkbox semantics, meaning this project will require intentional test updates/additions.

### Preferred approach

Use a **custom legend-row composition with explicit CSS classing + frontend event wiring**, while keeping `LegendPanelManager` as the single lifecycle coordinator.

Key design points:
1. **Sidebar order update**
   - Reorder `FigureLayout.sidebar_container` children to place legend section before parameter section.
2. **Tile-based row model**
   - Replace `Checkbox` control with a row container that contains:
     - a circular style-indicator element,
     - a dedicated label element (`HTMLMath`) with a protected click zone.
   - Row click toggles visibility unless event target is inside the label zone.
3. **Style-derived indicator**
   - Fill color: lower-opacity variant of trace color/opacity.
   - Border style/width: derived from trace line dash + width.
4. **Disabled visual cue**
   - Add row-level disabled class (e.g., lowered opacity + muted indicator).
5. **Hover coupling with traces**
   - On row hover enter/leave, call figure/plot update path to apply temporary +15% line width scale and revert on leave.
6. **Responsive tiles**
   - Make legend container wrap (`flex-flow: row wrap`) with tile min/max widths.
7. **Label fit behavior**
   - Measure rendered label container width and apply staged behavior:
     1) scale down up to 0.8;
     2) if still overflow, apply right fade mask.
   - Attach delayed tooltip to show full label after hover timeout.

This is preferred because it preserves existing manager architecture while enabling the UI/event fidelity needed for the requested behavior.

## Open questions

- No blocking design decision is required for project creation; defaults can be specified in implementation planning for:
  - tooltip delay duration,
  - exact disabled styling thresholds,
  - per-trace-type hover-width handling when a trace has no line width concept.

## Challenges and mitigations

1. **Challenge: ipywidgets native controls are limited for rich hit-testing and hover micro-interactions.**
   - Mitigation: use explicit DOM structure/classes and JS event hooks attached to row elements, while retaining Python-side authoritative state.

2. **Challenge: temporary hover width changes must not corrupt persisted plot styling.**
   - Mitigation: store base width in row/plot metadata and apply reversible transient updates only during hover.

3. **Challenge: LaTeX fit measurement can be asynchronous due to MathJax rendering timing.**
   - Mitigation: run measurement after render ticks with debounce/retry, then apply scale/fade classes deterministically.

4. **Challenge: test stability for UI behavior that depends on frontend interactions.**
   - Mitigation: split tests into deterministic Python state tests plus narrowly scoped frontend-contract tests for class/state wiring.

## TODO

- [ ] Update project-030-era assumptions to new legend-first sidebar ordering.
- [ ] Redesign legend row widget model from checkbox row to tile row.
- [ ] Add style-indicator rendering contract from plot style metadata.
- [ ] Add row-click visibility toggle with label-zone click exclusion.
- [ ] Add disabled visual-state classes and synchronization.
- [ ] Add hover-driven temporary trace width amplification (+15%) and rollback.
- [ ] Add responsive tile layout constraints (min/max widths, wrap behavior).
- [ ] Add label fit pipeline: scale-down (max 20%), fade truncation, delayed full-label tooltip.
- [ ] Add/adjust tests for layout order, interaction behavior, and visibility synchronization.
- [ ] Update docs/developer guide to reflect new legend interaction model.

## Exit criteria

- [ ] Sidebar renders legend section above parameters.
- [ ] Legend visibility toggles work via tile click (excluding label region).
- [ ] Checkbox is fully replaced by style-indicator circle derived from trace style.
- [ ] Hidden traces have a clear, persistent visual cue in legend rows.
- [ ] Hovering legend row increases matching trace width by ~15% and reverts on hover end.
- [ ] Legend rows wrap responsively with defined min/max tile widths.
- [ ] Label overflow behavior follows scale-then-fade policy, with delayed full-label tooltip.
- [ ] Updated tests pass and verify the new behavior.
- [ ] Documentation reflects the updated legend workflow.
