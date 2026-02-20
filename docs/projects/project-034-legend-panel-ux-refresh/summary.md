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
- `FigureLayout.sidebar_container` currently orders sections as Parameters -> Info -> Legend, so legend is below parameters today.
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

---

## Review: Architectural Concerns and Recommendations

*Added 2026-02-20 during design review.*

After reading the full project document against the actual codebase (`figure_legend.py`, `figure_layout.py`, `Figure.py`, `figure_plot.py`, `PlotlyPane.py`, `Slider.py`, and the project-030 test suite), the following concerns and recommendations are raised. The intent is to prevent fragile design choices before implementation begins.

### Concern 1: Click-zone partitioning via JS event target inspection is fragile

**Issue.** The design proposes row-click toggles visibility "unless event target is inside the label zone." This requires JS-side `event.target`/`event.currentTarget` inspection to distinguish label clicks from row clicks. In the ipywidgets DOM, widget sub-elements are wrapped in generated container divs whose structure is not under toolkit control and varies across ipywidgets versions and notebook frontends (JupyterLab, Notebook 7, VS Code, Colab).

**Risk.** Any DOM restructuring by ipywidgets or the notebook host will silently break the hit-test logic, producing either:
- label clicks that also toggle visibility (false positive), or
- row clicks that stop working entirely (false negative).

This is the kind of bug that won't surface in Python-only tests and has no clean fallback.

**Recommendation.** Instead of target inspection on a single row container, use **two explicit, non-overlapping click surfaces**:
- The indicator circle (or a wrapper containing it) receives a Python `on_click` handler that toggles visibility. This is the toggle affordance.
- The label element remains inert for now (reserved for future edit). It has no click handler of its own.
- No JS event delegation or target filtering is needed.

This is a standard pattern already used in the codebase (e.g., `Slider.py` `btn_reset.on_click`, `btn_settings.on_click`). It avoids DOM structure assumptions entirely.

### Concern 2: Hover-driven trace width mutation introduces a new cross-component coupling

**Issue.** The design proposes that hovering a legend row calls "figure/plot update path to apply temporary +15% line width scale." This means `LegendPanelManager` must reach into `Plot` trace handles and mutate Plotly `line.width` transiently, then revert on hover-leave.

**Risks:**
- **Race conditions.** If a render cycle fires during hover (slider drag, relayout debouncer), the render will read back the inflated width as if it were the base style, or overwrite the transient width with the base value, causing visual flicker.
- **Fragile revert.** If the hover-leave event is missed (mouse leaves the notebook viewport, cell re-renders, DOM detach), the trace stays at the inflated width permanently.
- **API coupling.** `LegendPanelManager` currently has no reference to `Plot` internals beyond `plot.visible` and `plot.label`. This feature would require the manager to know about `plot.thickness`, `plot._update_line_style`, or direct Plotly trace handle access, breaking the current clean separation.

**Recommendation.** Either:
- **(A) Defer hover-highlight to a later phase.** It is the most complex and fragile feature in this project and provides the least essential value. Implement the rest of the UX refresh first, then assess whether hover-highlight is worth the coupling cost.
- **(B) Implement hover-highlight purely via CSS.** Instead of mutating actual Plotly trace data, apply a CSS visual effect (e.g., a subtle glow, outline, or background highlight) to the *legend row itself* on hover. This provides a visual affordance without touching the Plotly trace state at all. The cross-component coupling and race condition risks disappear.
- **(C) If trace-width hover is truly required,** introduce a formal `Plot.set_transient_emphasis(active: bool)` method that manages its own base-width snapshot and revert. Keep the transient state inside `Plot` (not the legend manager), and have `render()` respect the transient flag. This localizes the complexity.

### Concern 3: Label fit pipeline (scale + fade + tooltip) requires JS that does not exist in the codebase yet

**Issue.** The design proposes measuring rendered label width post-MathJax, applying CSS scale-down, then a gradient fade mask, then a delayed tooltip. The codebase currently has exactly one embedded JS module (`PlotlyPane.py` `PlotlyResizeDriver`) which uses `anywidget`. No other widget in the toolkit uses custom JS. There is no existing infrastructure for attaching per-row JS observers, measuring MathJax output dimensions, or managing delayed tooltips.

**Risk.** Building a second embedded JS module (or extending `PlotlyResizeDriver`) for label measurement is a significant new infrastructure investment. The measurement logic must handle:
- MathJax async rendering (timing varies by browser and notebook kernel state).
- Label content changes that require re-measurement.
- Container resize that invalidates previous measurements.
- Multiple rows being added/removed dynamically.

This is a non-trivial frontend mini-framework that will need its own maintenance surface area.

**Recommendation.** Use a **CSS-only progressive approach** for label overflow that avoids runtime measurement:
1. Set a `max-width` on the label container (tied to tile width).
2. Apply `overflow: hidden; text-overflow: ellipsis; white-space: nowrap;` for plain-text labels.
3. For MathJax labels, use `overflow: hidden` with a CSS gradient fade mask (`mask-image: linear-gradient(...)`) applied unconditionally to the trailing edge. This works without needing to measure whether overflow actually occurred.
4. Use the native `title` attribute (or `widgets.HTMLMath` with a wrapper) for full-label tooltip on hover. Standard browser title tooltips have a built-in delay and require zero JS.

This eliminates the MathJax measurement timing problem entirely. If the CSS-only approach proves insufficient after testing, the JS measurement layer can be added incrementally as a follow-up.

### Concern 4: Style-derived indicator requires a style-readback contract that does not exist

**Issue.** The design proposes deriving the indicator circle's fill color and border style from the plot's trace color, dash, and width. Currently, `Plot` exposes `color`, `thickness`, `dash`, and `opacity` as properties that read back from the Plotly trace handle. However, Plotly auto-assigns colors when `color=None` (the common case), and the auto-assigned color is not known until after the trace is rendered on the frontend. Reading `plot.color` when no explicit color was set returns `None`, not the auto-assigned color.

**Risk.** For the common case where users don't set explicit colors, the indicator circle will have no color to derive from. This means the indicator will either show a fallback color that doesn't match the trace, or it will need to query the Plotly figure widget for the actual rendered color, which requires trace-index-aware reads from `figure_widget.data[i].line.color`.

**Recommendation.** Define a `Plot.effective_style()` method (or similar) that returns resolved style metadata including Plotly-assigned defaults. The legend indicator should read from this method, not from the raw property accessors. The method should:
- Return explicit values when set.
- Fall back to querying the Plotly trace handle's actual `line.color` (which Plotly does populate after trace creation).
- Return a stable sentinel when color is truly unavailable, so the indicator can render a neutral state.

This should be designed as a general-purpose style readback contract, since future UI features (style editing in Project-030 Phase 6, info cards, export previews) will also need resolved style information.

### Concern 5: The sidebar reorder is a breaking change to existing tests with no phased rollout

**Issue.** Moving legend above parameters changes `sidebar_container.children` order, which is directly asserted in `test_project030_phase1_layout.py::test_sidebar_contains_legend_section_after_info_section`. The current design treats this as a simple change, but the sidebar order affects visual layout, tab order, and accessibility navigation.

**Recommendation.** This is straightforward and the right call. Just note that the test update should be done as the very first commit so that CI stays green throughout the branch.

### Concern 6: The `LegendRowModel` dataclass will need a significant expansion

**Issue.** The current `LegendRowModel` holds `(plot_id, container, toggle, label_widget, is_visible_for_active_view)`. The proposed design replaces `toggle: Checkbox` with an indicator element and adds hover state, disabled state, style-indicator state, and a future label-click-zone reference. The dataclass will grow substantially.

**Recommendation.** Rather than inflating the dataclass, extract the row widget composition into a dedicated `LegendRowWidget` class (or similar) that encapsulates:
- Widget construction (indicator + label + container layout).
- Style synchronization (color/dash/width readback and indicator update).
- State management (visible/disabled toggling, hover state).
- Event wiring (click handlers on indicator, future label handlers).

`LegendPanelManager` would then hold `dict[str, LegendRowWidget]` instead of `dict[str, LegendRowModel]`. This follows the same composition pattern used by `SmartFloatSlider` (in `Slider.py`), where widget construction, event wiring, and state management are all encapsulated in the widget class rather than spread across a manager and a passive dataclass.

This decomposition also makes it straightforward to add per-row features later (e.g., editable labels, style pickers from Phase 6) without further inflating the manager.

### Concern 7: No concrete plan for how JS event wiring is delivered

**Issue.** The document says "use explicit DOM structure/classes and JS event hooks attached to row elements" but does not specify the delivery mechanism. The only JS delivery mechanism in the codebase is `anywidget` (used by `PlotlyResizeDriver`). The legend rows are standard `ipywidgets` (HBox, HTMLMath). Standard ipywidgets do not support attaching arbitrary JS event listeners.

**Options and their trade-offs:**
- **(A) Use `anywidget` for the row container.** This means rewriting the row as a custom `anywidget.AnyWidget` with embedded ESM JS. This gives full DOM access but is a significant departure from the current `ipywidgets.HBox`-based composition.
- **(B) Inject JS via a hidden `widgets.HTML` widget** containing a `<script>` tag that walks up the DOM to find sibling elements. This is fragile and depends on DOM structure.
- **(C) Avoid JS entirely** and use only Python-side `observe`/`on_click` handlers with CSS classes. This is the most conservative and maintainable approach.

**Recommendation.** Strongly prefer option **(C)** for the initial implementation. The click-toggle and disabled-state features can be done purely with Python handlers and CSS classes (via `add_class`/`remove_class`). The hover-highlight feature should either use CSS-only effects (see Concern 2B) or be deferred. Only escalate to `anywidget` if a specific feature provably cannot be done with Python + CSS.

This avoids introducing a second `anywidget` module, avoids DOM structure assumptions, and keeps the legend implementation testable with the same Python-only test infrastructure used by Project 030.

### Summary of recommended modifications to the plan

| Proposed feature | Recommendation | Rationale |
|---|---|---|
| Click-zone partitioning via JS target inspection | Replace with two explicit click surfaces (indicator and label) | Avoids DOM structure fragility |
| Hover-driven +15% trace width | Defer or implement as CSS-only row highlight | Avoids cross-component coupling and race conditions |
| Label fit pipeline (scale + measure + fade + tooltip) | Use CSS-only overflow handling (`text-overflow`, gradient mask, `title` attr) | Avoids new JS infrastructure and MathJax timing issues |
| Style-derived indicator | Add `Plot.effective_style()` readback contract | Handles auto-assigned Plotly colors correctly |
| JS event hooks on row elements | Use Python `on_click`/`observe` + CSS classes only | Matches existing codebase patterns, stays testable |
| `LegendRowModel` expansion | Extract to `LegendRowWidget` class | Clean encapsulation, enables future per-row features |
| Sidebar reorder | Proceed as planned, test update first | Straightforward, correct |

### Overall assessment

The project's **goals and scope are well-defined and valuable**. The UX improvements (tile layout, style indicators, disabled cues, responsive wrapping) are genuine improvements over the checkbox-based v1 legend.

The **primary risk** is in the implementation approach: the document leans toward JS event wiring and DOM manipulation patterns that are foreign to this codebase, fragile across notebook frontends, and difficult to test. Several features (click-zone partitioning, hover trace mutation, MathJax label measurement) can be achieved more robustly with Python-side handlers and CSS, matching the patterns already established in `Slider.py` and `figure_layout.py`.

The recommended approach is: **implement the full visual/interaction redesign using Python + CSS first**, defer JS-dependent features to a follow-up if the CSS approach proves insufficient, and invest in a `Plot.effective_style()` readback contract that will serve this project and future UI features.
