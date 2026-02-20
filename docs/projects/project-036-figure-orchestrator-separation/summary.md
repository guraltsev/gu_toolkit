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

### Preferred target organization (rethought)

Adopt a **workflow-first modularization** that is intentionally concrete and Pythonic, avoiding a command/event object architecture.

1. **`Figure` remains the workflow hub, not a policy hub**
   - `Figure` keeps user-facing method signatures and call ordering;
   - each public method runs a short, readable sequence (`normalize -> mutate state -> request render -> sync ui`);
   - business decisions move into focused collaborators, but without introducing a heavy orchestration framework.

2. **Extract three concrete collaborators, aligned with existing code paths**
   - **`PlotRegistry`**: owns plot create/update/remove, id/overwrite behavior, and parameter registration decisions.
     QUESTION: We already have Plot? What does this add? Is it just a container for multiple plots? If so, that does seem reasonable 
   - **`RenderEngine`**: owns stale tracking, sampling/trace refresh, and relayout/range application.
   - **`ViewRuntime`**: owns view add/switch/remove state and runtime handles for active view widgets.
     QUESTION: We already have ViewManager? Does this overlap with that? Should the functionality just be moved there and reorganized? Discuss!

3. **Keep UI behavior in a thin adapter layer**
   - a `FigureUIAdapter` handles sidebar/legend/info visibility and widget-only updates;
   COMMENT: given project-035-architecture-modularization-program I think isolating all UI related python code is a very good idea. 
   - adapter consumes plain snapshots (`dict`/dataclass), not internal mutable objects.

4. **Use direct method calls and small return values, not command buses**
   - inputs are regular method parameters with clear names;
   - outputs are simple booleans/enums/dataclasses only where needed for clarity;
   - no `PlotCommand`/`RenderCommand` style indirection unless a concrete complexity need emerges later.
   COMMENT: FORBID complex commands. The strength of this toolkit is that it provides natural pythonic functions that can be used to delegate functionality to different managers and objects. Complex internal logic should be in private methods and internal private methods should try to avoid cross manager calls. Public methods should contain the "orchestration logic" or delegate functionality to private methods. 

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
ANSWER: given an input to plot, there should be a separate module concerned with expression/function parsing that does parameter detection. It returns the parameters. Then plot just calls the parameter registration method with sane defaults. This is a good approach as it allows sofisticated logic later on. For example, the parsing module can later decide to analyze whether parameters are additive (appear close to a +- sign) or multiplicative (*/) and then hint that the default should be 0 in the former case or 1 in the latter. This is out of scope for now but clear organization will allow for this. One will just have to redefine the return value to provide a dictionary of "additional metadata". 
3. Should render pipeline expose synchronous-only API, or also an explicit queued/debounced execution abstraction?
ANSWER: the render pipeline is subtle. It is a high performance codepath that later may need careful optimization. The functionality of the render piplene should be separated into a separate module/manager. Work hard to define its boundaries.
5. How strict should service encapsulation be (hard module boundaries with import checks vs convention-only)?
ANSWER: I do not fully understand the question. What are import checks?

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
- [ ] Define concrete collaborator APIs (`PlotRegistry`, `RenderEngine`, `ViewRuntime`, `FigureUIAdapter`) with minimal return types.
- [ ] Produce acceptance criteria that verify "orchestrator-only" responsibilities in `Figure.py`.
- [ ] Prepare implementation blueprint in `plan.md` after boundary decisions are finalized.

## Exit criteria

- [ ] `Figure.py` responsibilities are limited to orchestration, lifecycle composition, and public delegation.
- [ ] Render pipeline policy is isolated in a dedicated service module with focused tests.
- [ ] Plot lifecycle policy is isolated in a dedicated service module with focused tests.
- [ ] View runtime lifecycle and UI synchronization are separated into distinct service/adapter modules.
- [ ] Public helper facade remains stable while policy logic is removed from wrappers.
- [ ] Documentation clearly maps each concern to a single owning module.
