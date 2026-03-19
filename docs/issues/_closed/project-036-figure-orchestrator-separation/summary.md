# Project 036: Figure Orchestrator Separation and Concern Boundaries

## Status

**Superseded for execution (analysis retained as reference)**


> Note (2026-02-20): Project-036 is maintained as an analysis and triage record only.
> Active execution scope for ownership/boundary/dedup moved to project-037 under umbrella project-032.

## Goal/Scope

Restructure the `Figure` architecture so `Figure.py` is a thin orchestrator with explicit, stable boundaries. The primary objective is not line-count reduction; it is durable **separation of concerns**, clearer ownership, and lower regression risk during future feature work.

This project includes:
- decomposition of mixed responsibilities still living in `Figure.py`,
- definition of explicit ownership boundaries for plot lifecycle, render lifecycle, view lifecycle, UI synchronization, and facade ergonomics,
- explicit collaborator contracts that the orchestrator composes,
- requirement-level guidance that can be converted into a concrete implementation `plan.md`.

This project does **not** include implementation in this document.

## Summary of design

### Current-state analysis (problem statement)

The request to separate concerns is valid. Current `Figure.py` still centralizes too many responsibilities in one class:
- API normalization and policy decisions are interleaved with lifecycle mutation.
- Rendering policy, scheduling/debouncing triggers, relayout handling, and diagnostics are coupled.
- View state transitions and widget-facing UI synchronization are blended.
- Facade helpers often contain logic rather than forwarding to subsystem owners.

The practical result is high cognitive load for maintenance and change review: even targeted adjustments (e.g., plot behavior, relayout policy, legend visibility) require editing heavily shared methods and understanding unrelated concerns.

### Architectural direction

Adopt a **workflow-first modularization** that remains concrete and Pythonic:
- `Figure` stays as the call-sequence orchestrator and public facade root.
- Domain logic moves into focused collaborators.
- Interactions use explicit public methods and small return values.
- Avoid command/event object indirection for core flows.

This preserves readability/debuggability while creating maintainable boundaries.

---

## Design decisions (updated with comments/answers)

### 1) `Figure` remains orchestrator-first, not policy-first

`Figure` should keep public signatures and end-to-end call order, but each public method should become a short orchestration script, typically:
1. normalize input,
2. delegate to owning service,
3. request render/update side effects,
4. invoke UI sync adapter if needed,
5. return facade-level result.

`Figure` should not own heavy policy logic where a collaborator can own it.

### 2) `PlotRegistry` is intentionally thin (comment integrated)

`PlotRegistry` owns **collection lifecycle** for plots, including:
- add/update/remove semantics,
- id generation/lookup,
- overwrite behavior,
- routing to create/update paths,
- bookkeeping of plot membership within the figure.

`PlotRegistry` should **not** own parsing policy or parameter-initialization policy.

### 3) Introduce a dedicated parameter/parsing policy collaborator

To enforce separation of concerns:
- a parsing-focused helper/service detects parameter dependencies from plot inputs,
- lifecycle code performs registration/application using explicit defaults and rules,
- parameter detection output should leave room for future metadata enrichment (e.g., source hints, recommended default strategy).

This resolves ambiguity from prior drafts and keeps lifecycle and detection concerns decoupled.

### 4) `RenderEngine` owns render policy and synchronous render operations

`RenderEngine` should own:
- stale detection,
- sample/trace refresh decisions,
- relayout/range application,
- render result semantics (`changed`, `rerendered`, optional diagnostics payload).

Its core API should be synchronous and explicit.

### 5) Debouncing is a reusable service (comment integrated)

Debouncing should not be embedded as ad-hoc logic in orchestrator flows.
- Introduce/standardize a generic debouncing service module that can be reused by rendering, info panels, and other UI-adjacent flows.
- `RenderEngine` should expose deterministic synchronous operations.
- `Figure` (or adapters) can opt into debounced invocation by composing the shared debounce service.

This keeps render policy deterministic while preserving UX-friendly throttling behavior.

### 6) `ViewRuntime` owns runtime view lifecycle

`ViewRuntime` should own:
- add/switch/remove view state transitions,
- active view identity,
- runtime handles and per-view registration data,
- invariant checks for active/inactive transitions.

This should build on existing `figure_view_manager` direction rather than duplicating parallel abstractions.

### 7) `FigureUIAdapter` isolates widget/notebook synchronization

A thin adapter should own:
- sidebar/legend/info-visibility synchronization,
- widget-specific updates,
- translation between internal state snapshots and UI mutation calls.

UI adapter inputs should be immutable snapshots (dataclass/dict) at boundary crossings.

### 8) Interaction philosophy and encapsulation rules (comment integrated)

Adopt explicit interaction semantics:
- avoid object-based command indirection for core service interaction,
- prefer direct calls to **public methods** on collaborators,
- strongly discourage cross-class calls into private methods,
- keep public methods thin and make heavy logic private to the owning class.

This makes coupling visible and reviewable, and reduces “hidden protocol” drift between modules.

---

## Required ownership matrix (for implementation planning)

The implementation plan should classify every current `Figure` method into one of the following buckets:
- **Facade-only:** stable convenience wrapper, minimal delegation.
- **Orchestrator sequence:** call ordering and subsystem composition only.
- **Service-owned logic:** logic must move to one of `PlotRegistry`, parameter/parsing policy helper, `RenderEngine`, `ViewRuntime`, or `FigureUIAdapter`.
- **Deprecated/merge candidates:** methods to collapse or remove after extraction.

For each method, plan must list:
- current responsibility,
- target owner,
- migration strategy (direct extraction vs adapter shim),
- required regression tests.

## Contract shape requirements

Contracts should stay minimal and implementation-friendly:
- **Call style:** explicit named methods (`plot_registry.upsert_plot`, `render_engine.render_active_view`, etc.).
- **Return style:** simple values (`bool`, enum, dataclass) only when clarity requires it.
- **Boundary data:** immutable snapshots only at adapter boundaries.
- **Error model:** explicit exceptions or typed failure results; no silent policy fallthrough.

## Alternatives considered and rejected

1. **Method-count-only split of `Figure.py`**
   - Too shallow; moves code without clarifying ownership.
   - Rejected as primary strategy.

2. **Full command/event architecture (CQRS/event-sourcing style)**
   - Adds abstraction overhead and opaque interaction pathways for this toolkit stage.
   - Rejected as primary strategy.

## Open questions

1. **How strict should boundary enforcement be in this phase?**
   - Current direction: convention-first boundaries (ownership + review discipline) now; import-lint/hard guards can follow in a hardening project.

2. **How much metadata should parameter detection return in phase 1?**
   - Proposed: start with required detection outputs plus optional extension points; avoid over-design.

3. **Should render diagnostics be standardized across services now or later?**
   - Proposed: define minimal shared diagnostics payload now for testability and observability; postpone richer telemetry.

## Challenges and mitigations

- **Challenge:** behavior drift while extracting `plot()` and render paths.
  - **Mitigation:** characterize existing behavior with focused regression tests before and during extraction.

- **Challenge:** accidental cycles between render/view/ui modules.
  - **Mitigation:** enforce one-way dependency direction from orchestrator composition; collaborators do not call each other’s private internals.

- **Challenge:** preserving notebook UX while moving UI synchronization.
  - **Mitigation:** preserve facade signatures and validate with notebook-facing tests and targeted integration checks.

- **Challenge:** hidden coupling introduced by convenience wrappers.
  - **Mitigation:** require method-level ownership mapping and private/public boundary checks in code review.

## TODO

- [ ] Produce a full method ownership matrix for `Figure` with migration targets.
- [ ] Define concrete APIs for `PlotRegistry`, parameter/parsing helper, `RenderEngine`, `ViewRuntime`, and `FigureUIAdapter`.
- [ ] Define debouncing service interface and integration points (render + non-render consumers).
- [ ] Document invariants for each collaborator (input assumptions, mutation rules, return guarantees).
- [ ] Identify which existing modules are extended vs newly introduced to avoid abstraction duplication.
- [ ] Draft phased migration strategy that keeps toolkit functioning at every phase boundary.
- [ ] Convert this summary into implementation blueprint in `plan.md`, including acceptance tests.

## Exit criteria

- [ ] `Figure.py` responsibilities are limited to orchestration, lifecycle composition, and facade delegation.
- [ ] Plot collection lifecycle is isolated in `PlotRegistry`, while parameter/parsing policy is isolated in its own collaborator.
- [ ] Render policy is isolated in `RenderEngine` with deterministic synchronous APIs.
- [ ] Debouncing exists as a reusable service used by render orchestration and available for other UI flows.
- [ ] View runtime lifecycle is isolated from UI synchronization logic.
- [ ] UI synchronization is isolated in `FigureUIAdapter` with snapshot-based boundaries.
- [ ] Public helper facade remains stable while internal policy logic is removed from wrappers.
- [ ] Documentation maps each concern to exactly one owning module.
- [ ] Regression tests cover key behavior equivalence during extraction.

---

## Review: Codebase Reality Check and Concerns

> Added 2026-02-20 — assessment of proposal against actual codebase state.

### Current-state inventory (measured from source)

Before evaluating the proposed extractions, it is essential to ground them against what `Figure.py` and its existing collaborators actually contain today:

| Module | Lines | Role |
|--------|-------|------|
| `Figure.py` | 1,564 | Orchestrator + public facade |
| `figure_plot.py` | 952 | Per-curve math/trace logic |
| `figure_layout.py` | 675 | Widget tree/layout composition |
| `figure_parameters.py` | 614 | Parameter management + controls |
| `figure_info.py` | 403 | Info panel manager |
| `figure_legend.py` | 257 | Legend panel manager |
| `figure_api.py` | 246 | Module-level convenience helpers |
| `figure_plot_normalization.py` | 199 | Stateless input normalization |
| `figure_context.py` | 175 | Figure context stack |
| `figure_view_manager.py` | 145 | `ViewManager`: view lifecycle + stale state |
| `debouncing.py` | 129 | `QueuedDebouncer`: reusable service |
| `figure_view.py` | 58 | `View` dataclass |
| `figure_plot_style.py` | 55 | Style alias resolution |

**Total figure ecosystem: ~5,472 lines across 13 modules.**

The decomposition from project-022 already extracted normalization, style resolution, view management, module-level API helpers, and the context stack. What remains in `Figure.py` at 1,564 lines breaks down roughly as:

- ~500 lines: docstrings, type annotations, parameter docs (not extractable logic)
- ~80 lines: constructor wiring (composing existing managers)
- ~120 lines: `plot()` method (orchestration of normalization → create/update → legend → render)
- ~80 lines: view lifecycle methods (delegating to `ViewManager` + runtime wiring)
- ~50 lines: relayout debouncing plumbing
- ~22 lines: `render()` method (loop + hooks + info scheduling)
- ~200 lines: property accessors/facades (x_range, y_range, viewport, sampling_points, etc.)
- ~100 lines: hooks, snapshot, codegen, info delegates
- ~50 lines: display lifecycle and context manager
- ~60 lines: imports, type aliases, `_ViewRuntime` NamedTuple, module-level re-exports

The actual extractable logic is substantially smaller than 1,564 lines. The proposal's framing of "too many responsibilities centralized" is directionally correct but overstates the density of remaining logic.

### Strengths

1. **Workflow-first over CQRS is the right call.** Rejecting command/event architecture avoids gratuitous indirection for a notebook toolkit. Direct method calls to collaborators are debuggable and reviewable.

2. **Ownership matrix requirement is excellent.** Forcing a per-method classification before implementation prevents speculative extraction. This should be done first and may reveal that several proposed modules are unnecessary.

3. **Interaction philosophy (section 8) is sound.** Discouraging cross-class private access and keeping public methods thin is a good convention that costs nothing to adopt immediately.

4. **Contract shape requirements are appropriately minimal.** Simple return values and explicit exceptions fit the codebase's style.

5. **One-way dependency direction is the single most important structural rule.** Enforcing that collaborators never call back into the orchestrator or each other's internals prevents the cycle/coupling problems that killed prior decomposition attempts in other projects.

### Concerns

#### Concern 1: Several proposed modules duplicate existing infrastructure

The plan proposes five new collaborators. Cross-referencing against the codebase:

| Proposed | Already exists as | Gap |
|----------|-------------------|-----|
| `ViewRuntime` | `ViewManager` in `figure_view_manager.py` (state transitions, active view, stale marking) + `_ViewRuntime` NamedTuple in `Figure.py` (widget handles) | Only the `_ViewRuntime` NamedTuple and its creation (~30 lines) would move. `ViewManager` already owns the state logic the proposal describes. |
| Debouncing service | `QueuedDebouncer` in `debouncing.py` (already reusable, already used by both render and info flows) | **None.** The proposal says "Introduce/standardize a generic debouncing service module" — this already exists and is already generic. |
| Parameter/parsing policy collaborator | `figure_plot_normalization.py` (stateless input normalization, parameter inference) + `figure_parameters.py` (parameter registration/control lifecycle) | The detection of parameter dependencies from plot inputs is already one function call (`normalize_plot_inputs` returning `inferred_parameters`). What additional "policy" would a new module own? |

**Risk:** Creating new modules that wrap existing ones adds indirection without new capability. The plan should explicitly state which existing modules get extended versus replaced, and what new behavior each proposed module contributes that does not already exist.

#### Concern 2: `PlotRegistry` wraps a thin dict with tightly coupled orchestration

The `self.plots` dict is currently a plain `dict[str, Plot]`. The create-vs-update branching in `plot()` (~65 lines) is not pure collection logic — it is interleaved with:
- parameter autodetection and registration (`self.parameter(parameters)`),
- legend wiring (`self._legend.on_plot_added/on_plot_updated`),
- sidebar visibility sync,
- numeric function binding and initial render.

A `PlotRegistry` that only owns add/update/remove/lookup becomes a trivial wrapper around `dict` operations. A `PlotRegistry` that also owns parameter wiring and legend notification becomes a second orchestrator competing with `Figure`.

**Recommendation:** Consider whether `plot()` is better understood as an orchestrator sequence that stays in `Figure` (per section 1's own pattern: normalize → delegate → side-effects → UI sync → return). Extracting only the ID-generation and overwrite-detection into a small helper function (not a class) may be sufficient.

#### Concern 3: `RenderEngine` has very little to extract

`Figure.render()` is 22 lines:
1. Log the render reason (rate-limited).
2. Loop over `self.plots` calling `plot.render(view_id=...)`.
3. Mark inactive views stale on parameter changes.
4. Dispatch hooks.
5. Schedule info panel update.

The actual rendering logic (sampling, trace generation, stale detection per-plot) lives in `figure_plot.py` (952 lines). A `RenderEngine` that wraps the 22-line loop and hook dispatch adds a module and an indirection layer without meaningfully reducing `Figure.py` complexity or clarifying ownership — the plot-level render policy is already in `Plot`.

**Recommendation:** If render orchestration grows (e.g., batched rendering, cross-plot dependency ordering, diagnostic aggregation), a `RenderEngine` becomes justified. Currently, it is premature. Pin it as a future extraction trigger rather than an immediate deliverable.

#### Concern 4: `FigureUIAdapter` risks double-indirection

UI synchronization is currently:
- `_sync_sidebar_visibility()` — 5 lines delegating to `FigureLayout`.
- Scattered calls to `self._legend.set_active_view()`, `self._info.set_active_view()`, `self._layout.set_view_tabs()`.

These are already one-liner delegations. Adding `FigureUIAdapter` as an intermediary creates: `Figure` → `FigureUIAdapter` → `FigureLayout` / `LegendPanelManager` / `InfoPanelManager`. The adapter would contain the same delegation calls that `Figure` currently has, just relocated.

**Recommendation:** The adapter pattern is warranted if the UI transport changes (e.g., from ipywidgets to a web-socket protocol). For now, the existing direct delegation to specialized managers is clean. Defer `FigureUIAdapter` until project-035 WS-D (frontend/backend contract) actually introduces a new transport layer.

#### Concern 5: `ViewRuntime` naming collision with existing `_ViewRuntime`

`Figure.py` already defines `_ViewRuntime(NamedTuple)` holding `figure_widget` and `pane` per view. The proposal uses "ViewRuntime" to describe a class owning state transitions, active view identity, and runtime handles. But `ViewManager` already owns state transitions and active view identity. The widget-handle storage (`_ViewRuntime` dict) is ~30 lines of setup code.

**Risk:** Implementing a new `ViewRuntime` class alongside the existing `_ViewRuntime` NamedTuple and `ViewManager` creates three overlapping abstractions for view lifecycle.

**Recommendation:** The plan should clarify whether `ViewRuntime` merges `ViewManager` + `_ViewRuntime` into one class, or extends `ViewManager`. If merging, say so explicitly. If extending, specify what new responsibilities `ViewRuntime` has that `ViewManager` lacks.

#### Concern 6: No quantitative extraction targets or LOC analysis

The proposal frames `Figure.py` as having "too many responsibilities" but does not quantify what percentage is logic versus documentation, or which specific methods exceed a complexity threshold. Of the ~1,564 lines:
- ~500 lines are docstrings and parameter documentation (necessary for a user-facing API).
- ~200 lines are property accessors that are 1-3 lines of delegation each.

The remaining ~850 lines of logic-bearing code is not trivial, but it is also not extreme for a top-level orchestrator class. The plan should establish a concrete target (e.g., "reduce Figure.py logic lines below 400") to avoid open-ended refactoring with diminishing returns.

#### Concern 7: Overlap with project-035 workstreams

Project-035 already defines:
- **WS-A:** Figure decomposition (extends project-022).
- **WS-D:** Frontend/backend contract (typed state snapshots, interaction intents).

Project-036 overlaps significantly with WS-A and partially with WS-D (the `FigureUIAdapter` concept). The relationship between these projects is not documented. Is project-036 meant to replace WS-A? Subsume it? Run in parallel?

**Recommendation:** Explicitly position project-036 relative to project-035. If 036 supersedes WS-A, update the 035 summary accordingly. If they are the same workstream, consolidate into one document.

### Revised recommendation: a focused extraction plan

Based on codebase analysis, the highest-value extractions (justified by actual complexity, not speculative cleanliness) are:

1. **Extract `plot()` create-vs-update routing into a helper** (not a full `PlotRegistry` class). This removes the densest orchestration logic from `Figure` while keeping parameter/legend wiring in the orchestrator where it belongs.

2. **Merge `_ViewRuntime` NamedTuple and its creation into `ViewManager`** (rename to `ViewRuntime` if desired). This consolidates view state and widget-handle ownership in one place instead of splitting across `ViewManager`, `_ViewRuntime`, and `Figure._create_view_runtime`.

3. **Acknowledge that `debouncing.py` already satisfies decision 5.** Mark it as done or identify specific gaps.

4. **Defer `RenderEngine` and `FigureUIAdapter`** until concrete triggers justify them (batched rendering, new UI transport, respectively). Document these as future extraction triggers with clear criteria.

5. **Adopt section 8 (interaction philosophy) immediately** as a code-review convention. This costs nothing and prevents new coupling from forming regardless of whether further extraction happens.

6. **Produce the ownership matrix first** (TODO item 1). This will objectively determine which extractions are justified and which are premature.

---

## Disposition Update (2026-02-20)

Following review of concerns and overlap with active architecture work, this project is narrowed and partially superseded.

### Abandoned in Project-036

The following items are abandoned as immediate deliverables for this project because they are currently premature or duplicative of existing infrastructure:

- Introduce a new `RenderEngine` module as a near-term extraction target.
- Introduce a new `FigureUIAdapter` layer as a near-term extraction target.
- Introduce a new debouncing service module (already satisfied by `debouncing.py`/`QueuedDebouncer`).
- Treat `PlotRegistry` as a mandatory class-level extraction independent of demonstrated net value.

### Moved to Project-037

The following outcomes are moved to **Project-037: Ownership Matrix, Boundary Contracts, and Duplication Elimination**:

- Method-level ownership matrix as the first required artifact.
- Duplicate-functionality consolidation track (in coordination with project-033).
- Domain-boundary and interaction-contract documentation across Figure ecosystem modules.
- Cross-project alignment/disposition mapping across projects 032/033/035/036.

### Deferred in Project-036 (trigger-based)

The following remain explicitly deferred and only become active if trigger conditions are met:

- `RenderEngine` extraction (trigger: cross-plot scheduling/diagnostics complexity materially increases).
- `FigureUIAdapter` extraction (trigger: transport abstraction needs beyond current notebook/widget managers).
- View runtime consolidation (trigger: measurable overlap between `ViewManager` and `_ViewRuntime` ownership causes recurring maintenance cost).

### Updated status note

Project-036 remains a design/concern-analysis record, while implementation-oriented ownership, boundary, and deduplication execution is tracked in project-037.
