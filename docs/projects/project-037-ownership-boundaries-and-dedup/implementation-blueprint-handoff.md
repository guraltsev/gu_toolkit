# Project 037 Implementation Blueprint (Developer Handoff)

## Status

**Planning artifact — implementation-ready guidance, no code changes included**

## Purpose

This document translates Project 037 architecture decisions into an execution-ready blueprint for developers implementing the refactor work in Project-033 and Project-023 tracks.

It expands existing Project 037 artifacts with:

- concrete file-level implementation slices,
- acceptance criteria per slice,
- dependency and sequencing constraints,
- risk controls for hot-path behavior,
- checklists for preserving external API compatibility.

---

## 1) Current-state findings (code-validated)

### 1.1 Figure hot paths currently blend orchestration and policy

The `Figure` class still owns policy logic that should migrate behind collaborator contracts:

- `set_active_view()` orchestrates state transition plus runtime synchronization (`InfoPanelManager`, `LegendPanelManager`, widget ranges, stale reset, tab sync, reflow, sidebar visibility).
- `_viewport_*` and default range setters each perform input parsing and state mutation, resulting in duplicated normalization pathways.
- `plot()` handles ID generation, input normalization, parameter auto-detection, update-vs-create branching, and style aliasing in one method.
- `render()` both orchestrates rendering and performs hook dispatch through direct `ParameterManager.get_hooks()` iteration.

### 1.2 Plot still reads concrete Figure internals directly (BR-04 gap)

`Plot.render()` depends on concrete Figure fields/methods (`active_view_id`, `current_x_range`, `x_range`, `sampling_points`, `views`, `figure_widget_for`) and directly marks stale state for non-active views.

This coupling should be replaced with a narrow runtime provider protocol to decouple plot execution from Figure internals while preserving behavior.

### 1.3 Parameter hook ownership is split across two owners

`ParameterManager` owns registration and triggers render callback on slider changes, but post-render hook execution currently lives in `Figure.render()`. This creates an ownership leak and complicates boundary enforcement.

### 1.4 Existing tests provide a strong baseline for safe incremental movement

The repository already includes tests for:

- hook ID and failure semantics,
- render pipeline behavior,
- stale-view lifecycle and view switching behavior.

These can be promoted to phase gates and augmented with new contract tests.

---

## 2) Guiding implementation principles

1. **No public API break first:** keep `Figure.plot()`, `Figure.render()`, `Plot` user-facing behavior, and existing aliases unchanged until final cleanup.
2. **Introduce seams before movement:** add contracts/protocols and adapters first, then migrate logic behind them.
3. **One owner per policy:** each policy (range resolution, hook dispatch, stale marking, sampling fallback, kwargs normalization) must have a single authority.
4. **Small, reversible slices:** each PR should complete one ownership move with green phase-gate tests.
5. **Contract tests before internals extraction:** encode expected behavior before moving logic.

---

## 3) Work package breakdown (handoff-ready)

## WP-1: Range and viewport ownership normalization

**Primary goal:** establish one canonical range contract and remove duplicated conversion paths.

### Files likely touched

- `Figure.py`
- `figure_view.py`
- `figure_view_manager.py`
- (new internal module) e.g. `figure_range_policy.py` or equivalent
- tests: `tests/test_project019_phase12.py` (+ new focused range contract tests)

### Required outcomes

- One normalization helper for `(min, max)` conversion/validation.
- `x_range`, `y_range`, `_viewport_x_range`, `_viewport_y_range`, `current_*_range` become facades over a single policy.
- Active-view transition uses one authoritative range persistence flow.

### Explicit non-goals

- Do not alter public method/property names.
- Do not change external representation of ranges.

### Acceptance checks

- View switch preserves per-view default ranges.
- Pan/zoom viewport persistence and restore behavior remain unchanged.
- Existing tests plus new range-policy tests pass.

---

## WP-2: Parameter hook dispatch ownership realignment

**Primary goal:** move parameter hook execution under `ParameterManager` contract, leaving `Figure.render()` orchestration-only.

### Files likely touched

- `figure_parameters.py`
- `Figure.py`
- tests: `tests/test_param_change_hook_api.py`, `tests/test_figure_render_pipeline.py`

### Required outcomes

- Introduce a manager-owned execution method (e.g. dispatch API) so `Figure` no longer iterates raw hook dict.
- Preserve callback ordering and warning semantics for failing hooks.
- Maintain current external hook APIs and IDs.

### Acceptance checks

- Existing hook API tests remain green unchanged.
- Hook failure still warns and does not block subsequent hooks.
- Render call path still triggers hooks after plotting for parameter-change events.

---

## WP-3: Plot runtime boundary protocol (BR-04)

**Primary goal:** decouple `Plot` runtime reads from concrete Figure internals.

### Files likely touched

- `figure_plot.py`
- `Figure.py`
- (new protocol module) e.g. `figure_plot_runtime_protocol.py`
- tests: new BR-04 provider-double test module

### Required outcomes

- Define a narrow provider protocol exposing only required reads:
  - active view id,
  - range resolution,
  - sampling default,
  - parameter context access,
  - trace/widget host for target view,
  - stale-mark request channel.
- Inject provider into `Plot` at construction from `Figure.plot()`.
- Eliminate direct `Plot -> Figure` internal reads where protocol equivalents exist.

### Acceptance checks

- Add a test where `Plot` renders via provider double (no concrete Figure object).
- Existing rendering behavior and trace updates remain unchanged.
- Inactive-view stale semantics remain intact with one authoritative owner.

---

## WP-4: Plot registration pipeline extraction (high complexity)

**Primary goal:** split monolithic `Figure.plot()` into clear services while keeping facade signature stable.

### Files likely touched

- `Figure.py`
- `figure_plot.py`
- `figure_plot_normalization.py` and related helpers
- (new service module) e.g. `figure_plot_registry_service.py`
- tests: existing plot lifecycle tests + new create/update/id/style normalization tests

### Required outcomes

- Extract and centralize:
  - ID allocation policy,
  - input normalization wiring,
  - create vs update decision,
  - kwargs/style alias normalization,
  - membership/default behaviors.
- Keep `Figure.plot()` as thin orchestration facade.

### Acceptance checks

- Repeated `plot(..., id=...)` update behavior unchanged.
- Alias handling (`width`/`thickness`, `alpha`/`opacity`) remains equivalent.
- Parameter auto-ensure behavior remains equivalent.

---

## WP-5: Boundary enforcement and package placement handoff

**Primary goal:** convert documentation-only boundary rules into enforceable checks and package-ready placement guidance.

### Files likely touched

- architecture tests under `tests/` (new)
- docs in `docs/projects/project-037-ownership-boundaries-and-dedup/`
- cross-project links to project-033/project-023 artifacts

### Required outcomes

- Add lightweight boundary tests for BR-03, BR-04, BR-08.
- Finalize duplicate-cluster disposition ledger with implementation links.
- Produce module placement map for Project-023 execution.

### Acceptance checks

- Boundary tests run in CI and fail on forbidden direction regressions.
- Each dedup cluster maps to one canonical owner and one implementation track.

---

## 4) Duplicate-cluster execution mapping (developer checklist)

1. **Range normalization cluster**
   - Source hotspots: `Figure` range setters/getters + `Plot.x_domain` parsing.
   - First implementation step: introduce shared range coercion helper used by both owners.

2. **Figure-default sentinel handling cluster**
   - Source hotspots: `Figure.sampling_points`, `Plot.sampling_points`, plot update paths.
   - First implementation step: centralize sentinel parsing (`None`/`figure_default`) into one helper.

3. **Hook dispatch cluster**
   - Source hotspots: `ParameterManager` registration + `Figure.render` execution loop.
   - First implementation step: manager-owned dispatch API with preserved warning contract.

4. **Stale-view policy cluster**
   - Source hotspots: `Figure.render`, `Plot.render`, `ViewManager.mark_stale/clear_stale`.
   - First implementation step: choose single stale-mark authority and route all calls through it.

5. **Plot kwargs normalization cluster**
   - Source hotspots: `Figure.plot` update kwargs assembly + `Plot.update` semantics.
   - First implementation step: extract normalization service with compatibility tests.

---

## 5) Sequencing and dependency graph

Recommended order:

1. WP-1 (range contract)
2. WP-2 (hook ownership)
3. WP-3 (plot provider boundary)
4. WP-4 (plot registration extraction)
5. WP-5 (boundary enforcement + package handoff)

Why this order:

- WP-1 and WP-2 reduce policy ambiguity in hot paths early.
- WP-3 becomes safer after policy channels are clarified.
- WP-4 is largest and should occur after runtime seams exist.
- WP-5 is final hardening to prevent regressions and support module migration.

---

## 6) Risk register and mitigations

- **Risk:** regressions in interactive render responsiveness.
  - **Mitigation:** preserve debouncer path; keep render orchestration root in `Figure`; run render pipeline tests every slice.

- **Risk:** stale view behavior drifts during ownership moves.
  - **Mitigation:** add explicit stale-lifecycle tests before stale policy extraction.

- **Risk:** protocol extraction adds abstraction overhead with no gain.
  - **Mitigation:** keep provider protocol minimal and driven by current concrete call sites only.

- **Risk:** partial dedup leaves split ownership unresolved.
  - **Mitigation:** require per-PR owner declaration and matrix row updates as gate.

---

## 7) Definition of done for Project 037 handoff completion

Project 037 can mark implementation handoff complete when:

- each duplicate cluster has canonical owner + linked execution PR/issue,
- boundary rules BR-03/BR-04/BR-08 are test-enforced,
- `Figure.plot()` and `Figure.render()` are orchestrator facades with extracted policy helpers,
- `Plot` runtime boundary no longer requires concrete `Figure` internals,
- project summary and matrix artifacts are updated to reflect delivered slices.

---

## 8) Suggested per-PR template for implementation teams

Each implementation PR should include:

1. **Scope:** which WP and cluster(s) are addressed.
2. **Owner move:** what ownership changed from/to.
3. **Behavior parity evidence:** tests proving no API drift.
4. **Boundary impact:** BR rules touched and how enforced.
5. **Follow-on slices:** what remains and why.

This template keeps Project-033 and Project-023 execution aligned with Project-037 governance artifacts.
