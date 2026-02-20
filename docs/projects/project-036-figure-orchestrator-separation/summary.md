# Project 036: Figure Orchestrator Separation and Concern Boundaries

## Status

**Planning (post-discovery)**

## Goal/Scope

Restructure the `Figure` architecture so `Figure.py` is a thin orchestrator with explicit, stable boundaries. The target is not primarily line-count reduction; the target is **separation of concerns** and maintainability.

This project covers:
- decomposition of mixed responsibilities currently still living in `Figure.py`,
- definition of clear subsystem ownership (render pipeline, view lifecycle, plot lifecycle, UI synchronization, and public facade),
- introduction of explicit contracts between orchestration and subsystem services.

This project does **not** include implementation yet, and does **not** include a detailed blueprint (`plan.md`) yet.

## Summary of design

## Request and code analysis

The improvement request is correct: current `Figure.py` remains behaviorally crowded even after previous extractions. The file currently contains ~1,564 lines and 51 methods on `Figure`, with several large multi-purpose methods (`plot`, `render`, `snapshot`, `__init__`, relayout handlers) and many direct coordinator+policy+adapter responsibilities interleaved.

Observed concentration points in the current module:
- **Plot lifecycle orchestration mixed with policy:** `plot()` still performs API normalization handoff, parameter auto-registration policy, create/update routing, style decisions, trace wiring, and side effects.
- **Render pipeline mixed with event handling:** `render()`, `_throttled_relayout()`, `_run_relayout()`, `_log_render()` combine scheduling, range updates, rerender policy, and diagnostics.
- **View/runtime ownership mixed with UI sync:** add/switch/remove view methods and `_sync_sidebar_visibility()` blend domain state transitions with widget/UI behavior.
- **Facade surface mixed with subsystem internals:** many getters/setters and convenience methods are implemented directly in `Figure` instead of through a grouped facade contract.

### Preferred target organization (rethought)

Adopt a **workflow-first modularization** that is intentionally concrete and Pythonic, avoiding a command/event object architecture.

1. **`Figure` remains the workflow hub, not a policy hub**
   - `Figure` keeps user-facing method signatures and call ordering;
   - each public method runs a short, readable sequence (`normalize -> mutate state -> request render -> sync ui`);
   - business decisions move into focused collaborators, but without introducing a heavy orchestration framework.

2. **Extract three concrete collaborators, aligned with existing code paths**
   - **`PlotRegistry`**: owns plot create/update/remove, id/overwrite behavior, and parameter registration decisions.
    COMMENT RESOLUTION: `Plot` remains the per-plot runtime object; `PlotRegistry` is a lifecycle coordinator for the *collection* (lookup, overwrite semantics, creation/update routing, and delegation to parsing/parameter policy helpers).
   - **`RenderEngine`**: owns stale tracking, sampling/trace refresh, and relayout/range application.
   - **`ViewRuntime`**: owns view add/switch/remove state and runtime handles for active view widgets.
     COMMENT RESOLUTION: this is a reorganization of existing `figure_view_manager` behavior rather than a parallel concept. Prefer extending/renaming existing view-manager code paths over introducing duplicate abstractions.

3. **Keep UI behavior in a thin adapter layer**
   - a `FigureUIAdapter` handles sidebar/legend/info visibility and widget-only updates;
   COMMENT RESOLUTION: accepted. This project should align with project-035 by isolating notebook/widget-facing synchronization code in one module.
   - adapter consumes plain snapshots (`dict`/dataclass), not internal mutable objects.

4. **Use direct method calls and small return values, not command buses**
   - inputs are regular method parameters with clear names;
   - outputs are simple booleans/enums/dataclasses only where needed for clarity;
   - no `PlotCommand`/`RenderCommand` style indirection unless a concrete complexity need emerges later.
   COMMENT RESOLUTION: accepted as an explicit architecture rule for this project. Avoid command/event-bus abstractions unless a concrete future bottleneck proves necessity.

### Contract shape (pragmatic)

Contracts should stay minimal and implementation-friendly:
- **Calls:** explicit methods (`plot_registry.upsert_plot(...)`, `render_engine.render_view(...)`).
- **Returns:** lightweight values (`RenderResult`, `changed: bool`, `active_view_id: str`).
- **Shared state:** immutable snapshots only at UI boundaries where mutation safety matters.

This keeps the decomposition understandable for maintainers who work directly in `Figure.py`, while still enforcing clear ownership boundaries.

### Why this is the preferred approach

This approach aligns with current module trajectory (`figure_plot_normalization.py`, `figure_view_manager.py`, `figure_plot_style.py`) while avoiding architecture overhead that would make normal debugging and incremental refactoring harder. It minimizes risk by removing policy from `Figure.py` in small slices, with concrete modules and straightforward call flows.

## Alternatives considered and rejected

1. **Alternative A: split `Figure.py` by method-count only**
   - Fast but shallow; risks moving complexity without defining ownership contracts.
   - Rejected as primary strategy.

2. **Alternative B: complete rewrite around command/event messaging (or CQRS/event sourcing)**
   - Maximum conceptual purity, but disproportionate migration risk and scope for current toolkit needs.
   - Rejected as primary strategy.
  
## Open questions

1. Should plot parameter auto-registration stay in plot lifecycle service, or become a standalone parameter-policy service?
ANSWER: separate concerns. Introduce/standardize a parsing-focused helper/module that detects parameters (and optionally returns metadata later), while lifecycle code performs registration with defaults.
3. Should render pipeline expose synchronous-only API, or also an explicit queued/debounced execution abstraction?
ANSWER: first separate render responsibilities into a dedicated manager with clearly defined synchronous entry points; preserve existing debounced triggers as adapter/orchestrator wiring around that manager.
5. How strict should service encapsulation be (hard module boundaries with import checks vs convention-only)?
ANSWER: use convention-first boundaries in this phase (clear ownership + code review discipline), and defer import-lint enforcement to a later hardening project if needed.

## Challenges and mitigations

- **Challenge:** Behavior drift during decomposition of `plot()` and render paths.
  - **Mitigation:** characterize existing behavior with focused regression tests before moving logic.

- **Challenge:** Circular dependencies between services (`view` <-> `render` <-> `ui`).
  - **Mitigation:** enforce one-way direct method contracts and dependency injection at the `Figure` composition root; allow immutable snapshots specifically at UI boundaries.

- **Challenge:** Maintaining notebook UX while separating UI adapter concerns.
  - **Mitigation:** preserve current facade signatures and validate with existing notebook-facing tests.

## TODO

- [ ] Define explicit service boundaries and ownership matrix for every current `Figure` method.
- [ ] Classify each `Figure` method as orchestrator/facade/service-owned and identify extraction destination.
- [ ] Define concrete collaborator APIs (`PlotRegistry`, `RenderEngine`, `ViewRuntime`, `FigureUIAdapter`) with minimal return types and no command-bus indirection.
- [ ] Define interface between plot parsing/parameter detection and registration policy (including reserved shape for future metadata hints).
- [ ] Produce acceptance criteria that verify "orchestrator-only" responsibilities in `Figure.py`.
- [ ] Prepare implementation blueprint in `plan.md` after boundary decisions are finalized.

## Exit criteria

- [ ] `Figure.py` responsibilities are limited to orchestration, lifecycle composition, and public delegation.
- [ ] Render pipeline policy is isolated in a dedicated service module with focused tests.
- [ ] Plot lifecycle policy is isolated in a dedicated service module with focused tests.
- [ ] View runtime lifecycle and UI synchronization are separated into distinct service/adapter modules.
- [ ] Public helper facade remains stable while policy logic is removed from wrappers.
- [ ] Documentation clearly maps each concern to a single owning module.
