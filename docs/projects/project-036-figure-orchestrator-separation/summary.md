# Project 036: Figure Orchestrator Separation and Concern Boundaries

## Status

**Discovery**

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

### Preferred target organization (chosen)

Adopt a **ports-and-services coordinator model** centered on `Figure` as composition root:

1. **`Figure` (orchestrator only)**
   - owns service wiring, lifecycle entrypoints, and transaction boundaries;
   - contains no business-policy branches for plotting/rendering internals;
   - delegates all non-trivial behavior to dedicated services.

2. **Plot lifecycle service**
   - create/update/delete plot records,
   - enforce plot identity and overwrite policy,
   - own parameter auto-detection/registration policy,
   - produce immutable "plot change" events for downstream render service.

3. **Render pipeline service**
   - own stale detection, rerender planning, sampling execution, and trace patching,
   - isolate relayout/range synchronization policy,
   - expose explicit operations (`render_all`, `render_view`, `mark_stale`, `sync_viewport`).

4. **View runtime service**
   - own view registry, active view transitions, per-view widget runtime handles,
   - enforce validity invariants (active view must exist, runtime must be attached),
   - emit state changes consumed by UI synchronization service.

5. **UI synchronization adapter**
   - own sidebar/legend/info visibility sync and widget-only concerns,
   - remain replaceable for notebook-vs-other frontends,
   - consume typed state snapshots rather than mutating core services directly.

6. **Public API facade module(s)**
   - keep notebook-friendly surface (`plot`, `parameter`, range/title helpers) thin,
   - route to orchestrator APIs only,
   - avoid embedding behavior policy in helper wrappers.

### Contract shape

The target contracts between services should be explicit and typed:
- input command objects (e.g., `PlotCommand`, `RenderCommand`),
- output result/event objects (e.g., `PlotChanged`, `RenderReport`, `ViewStateChanged`),
- immutable snapshots for UI (`FigureStateSnapshot`, `ViewStateSnapshot`).

This keeps `Figure` readable as a workflow graph instead of a mixed policy implementation.

### Why this is the preferred approach

This approach aligns with current module trajectory (`figure_plot_normalization.py`, `figure_view_manager.py`, `figure_plot_style.py`) while fixing the remaining issue: too much decision logic still sits in `Figure.py`. It minimizes risk by evolving existing boundaries rather than introducing an entirely new framework.

## Alternatives considered

1. **Alternative A: split `Figure.py` by method-count only**
   - Fast but shallow; risks moving complexity without defining ownership contracts.
   - Rejected as primary strategy.

2. **Alternative B: complete rewrite around event sourcing/CQRS**
   - Maximum conceptual purity, but disproportionate migration risk and scope for current toolkit needs.
   - Rejected as primary strategy.

## Open questions

1. Should plot parameter auto-registration stay in plot lifecycle service, or become a standalone parameter-policy service?
2. Should render pipeline expose synchronous-only API, or also an explicit queued/debounced execution abstraction?
3. How strict should service encapsulation be (hard module boundaries with import checks vs convention-only)?

## Challenges and mitigations

- **Challenge:** Behavior drift during decomposition of `plot()` and render paths.
  - **Mitigation:** characterize existing behavior with focused regression tests before moving logic.

- **Challenge:** Circular dependencies between services (`view` <-> `render` <-> `ui`).
  - **Mitigation:** enforce one-way contracts through typed events/snapshots and dependency injection at the `Figure` composition root.

- **Challenge:** Maintaining notebook UX while separating UI adapter concerns.
  - **Mitigation:** preserve current facade signatures and validate with existing notebook-facing tests.

## TODO

- [ ] Define explicit service boundaries and ownership matrix for every current `Figure` method.
- [ ] Classify each `Figure` method as orchestrator/facade/service-owned and identify extraction destination.
- [ ] Draft typed command/event/snapshot contract primitives for plot/render/view/ui interactions.
- [ ] Produce acceptance criteria that verify "orchestrator-only" responsibilities in `Figure.py`.
- [ ] Prepare implementation blueprint in `plan.md` after boundary decisions are finalized.

## Exit criteria

- [ ] `Figure.py` responsibilities are limited to orchestration, lifecycle composition, and public delegation.
- [ ] Render pipeline policy is isolated in a dedicated service module with focused tests.
- [ ] Plot lifecycle policy is isolated in a dedicated service module with focused tests.
- [ ] View runtime lifecycle and UI synchronization are separated into distinct service/adapter modules.
- [ ] Public helper facade remains stable while policy logic is removed from wrappers.
- [ ] Documentation clearly maps each concern to a single owning module.
