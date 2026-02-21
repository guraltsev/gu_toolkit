# Project 037 Plan: Ownership Boundaries and Dedup Execution Blueprint

## Detailed blueprint for implementation

### 0) Current-state code analysis (implementation inputs)

This plan is based on direct inspection of the current Figure ecosystem and existing tests.

#### 0.1 Figure currently mixes orchestration and policy in hot paths
- `Figure.render()` performs active-view plot rendering, stale-mark policy, and direct hook iteration via `ParameterManager.get_hooks()`; this confirms the boundary split is only partial today.  
- `Figure.set_active_view()` handles both ViewManager transition and UI/runtime synchronization (`InfoPanelManager`, `LegendPanelManager`, axis range updates, stale clear, tab sync, sidebar visibility).  
- `Figure` owns both default ranges (`x_range`, `y_range`) and viewport range controls (`_viewport_x_range`, `_viewport_y_range`) with conversion logic repeated in several setters.

#### 0.2 Plot remains coupled to concrete Figure runtime (BR-04 gap)
- `Plot` stores a concrete `Figure` reference (`smart_figure`) and resolves parameter values through `self._smart_figure.parameters.parameter_context`.  
- `Plot.render()` reads view/range/sampling policy directly from the `Figure` object (`current_x_range`, `x_range`, `sampling_points`, `active_view_id`), and stale behavior is coordinated from both `Plot.render()` and `Figure.render()`.

#### 0.3 ParameterManager owns registration but not full execution channel
- `ParameterManager` owns hook registration and trigger callback wiring (`_on_param_change -> render_callback`).
- Execution for param-change hooks currently occurs in `Figure.render()`, not in `ParameterManager`, creating a cross-owner execution boundary.

#### 0.4 View ownership is mostly clean, but facades still carry synchronization burden
- `ViewManager` correctly owns view registry, active-view transitions, and stale flags.
- `Figure` still handles runtime widgets, per-view debouncers, axis/panel synchronization, and tab reflow orchestration.

#### 0.5 Existing tests provide a safe baseline for phased refactors
- Param-change hook API tests and render-pipeline tests exist.
- View lifecycle and stale semantics are covered in `tests/test_project019_phase12.py`.
- This allows incremental boundary shifts while preserving behavior.

---

### 1) Preferred implementation approach

Use an **incremental seam-first extraction strategy**:
1. Introduce narrow contracts/protocols first (no behavior change).
2. Route call sites through seam adapters in `Figure` (still behavior-preserving).
3. Move ownership of logic behind those seams in small slices.
4. After each slice, run focused tests + a wider regression subset.

This is preferred because the hottest behavior (`plot()`/`render()`/view switching) already has coupled responsibilities and broad API exposure; seam-first minimizes regression risk while keeping repository state functioning between phases.

---

### 2) Phase plan (repository-safe slices)

## Phase 1 — Baseline hardening and decision lock

**Objective:** freeze current behavior and lock architectural decisions before moving logic.

**Tasks**
- Create a “Project 037 duplicate cluster ledger” section in this plan (below) and cross-link candidate clusters to Project-033 and Project-023 consumers.
- Add a boundary decision appendix for BR-03/BR-04/BR-08 with owner + enforcement mechanism per rule.
- Expand or confirm golden behavior tests for:
  - param-change render->hook order,
  - stale-flag behavior for inactive views,
  - plot membership + active/inactive rendering semantics.

**Done when**
- No unresolved “who owns what” rows remain for the first execution batch.
- Test baseline for hot paths is green and documented.

**Repository safety state after Phase 1**
- No architecture movement yet; only decision artifacts/tests that preserve current behavior.

---

## Phase 2 — Range and viewport contract normalization

**Objective:** make view-range ownership explicit and remove duplicated conversion/policy drift.

**Tasks**
- Introduce a dedicated range contract (e.g., `ViewRangePolicy` or `RangeState` helper) that formalizes:
  - default ranges (home/reset),
  - viewport ranges (current pan/zoom),
  - transition rules on view switch.
- Keep `Figure.x_range`, `Figure.y_range`, `_viewport_x_range`, `_viewport_y_range` as compatibility facades delegating to the contract.
- Consolidate repeated `InputConvert` range parsing paths to one normalization function/service.
- Ensure `ViewManager.set_active_view()` and `Figure.set_active_view()` use one authoritative transition flow.

**Done when**
- One canonical range normalization path exists.
- View-switch + relayout persistence tests pass without behavior regressions.

**Repository safety state after Phase 2**
- Public API unchanged; internals delegate through a single range policy seam.

---

## Phase 3 — Hook ownership split and render pipeline cleanup

**Objective:** separate parameter-change hooks from generic render/system hooks.

**Tasks**
- Keep parameter hook registration in `ParameterManager`.
- Introduce a dedicated execution API so `Figure.render()` no longer iterates `get_hooks()` directly.
- Add a second hook channel for non-parameter render/system events if needed (Figure-owned).
- Preserve current warning semantics for failing hooks and callback ordering guarantees.

**Done when**
- Parameter hook execution path is owned by ParameterManager contract.
- Figure render pipeline uses collaborator APIs, not collaborator internals.

**Repository safety state after Phase 3**
- Existing hook APIs still work; ownership is cleaner and test-verified.

---

## Phase 4 — Plot runtime boundary hardening (BR-04)

**Objective:** decouple `Plot` from concrete `Figure` internals via provider protocols.

**Tasks**
- Define a narrow injected provider protocol for plot runtime dependencies:
  - parameter context read,
  - active view id,
  - range query,
  - figure-default sampling value,
  - trace host access for target view.
- Replace direct `Plot -> Figure` reads with protocol calls.
- Keep `Figure.plot()` external signature unchanged.
- Mark inactive-view stale behavior in one authoritative owner (Figure or ViewManager policy adapter), avoiding dual-path logic.

**Done when**
- `Plot` does not require concrete Figure internals beyond protocol boundary.
- BR-04 contract test coverage exists and passes.

**Repository safety state after Phase 4**
- Functionality unchanged for users; internal coupling reduced substantially.

---

## Phase 5 — Plot registration pipeline extraction (dedup-heavy slice)

**Objective:** pull `Figure.plot()` normalize/create/update logic into canonical owner(s).

**Tasks**
- Extract a plot-registration service that owns:
  - ID allocation/validation,
  - variable/function normalization integration,
  - create-vs-update decision path,
  - kwargs normalization for style/domain/sampling/view membership updates.
- Keep `Figure.plot()` as facade delegating to extracted service.
- Coordinate cluster ownership outcomes with Project-033 before implementation lands.

**Done when**
- `Figure.plot()` is thin orchestration facade.
- Dedup target logic lives in one canonical owner with regression tests.

**Repository safety state after Phase 5**
- API stable; most complex duplicate-prone plot setup path is centralized.

---

## Phase 6 — Boundary enforcement and packaging handoff

**Objective:** convert documentation contracts into enforceable guardrails and hand off placement decisions.

**Tasks**
- Add boundary checks (lightweight architectural tests) for BR-03/BR-04/BR-08 import/use constraints.
- Finalize duplicate-cluster dispositions and attach implementation status links (Project-033).
- Emit physical-placement guidance for each canonical owner (Project-023 handoff).
- Update Project-037 summary TODO/exit criteria status.

**Done when**
- Boundary checks run in tests.
- Duplicate ledger and placement handoff are complete and linked.

**Repository safety state after Phase 6**
- Ownership model is not only documented but enforced.

---

### 3) Duplicate cluster ledger (execution backlog for Project-033)

These are the initial clusters to process in order.

1. **Range normalization/parsing cluster**  
   Repeated `InputConvert` + tuple normalization logic across `Figure` and `Plot` setters.
   - Preferred owner: shared range normalization utility in figure-domain internals.

2. **Figure-default sentinel handling cluster**  
   Repeated `None/"figure_default"/sentinel` normalization in `Figure.sampling_points`, `Plot.sampling_points`, and plot-update paths.
   - Preferred owner: shared option-normalization helper.

3. **Hook dispatch semantics cluster**  
   Hook storage in `ParameterManager` but dispatch in `Figure.render`.
   - Preferred owner: parameter-domain hook dispatcher API.

4. **Stale-view mark/clear policy cluster**  
   Stale semantics distributed across `Figure.render`, `Plot.render`, and `ViewManager` APIs.
   - Preferred owner: ViewManager policy boundary + single orchestrator call site.

5. **Plot update kwargs normalization cluster**  
   Style/domain/sampling/view update logic in `Plot.update()` and `Figure.plot()` call preparation.
   - Preferred owner: plot registration/update service.

---

### 4) Test suite for acceptance

## 4.1 Always-run checks per phase
- `pytest -q tests/test_param_change_hook_api.py`
- `pytest -q tests/test_figure_render_pipeline.py`
- `pytest -q tests/test_project019_phase12.py`
- `pytest -q tests/test_parameter_snapshot_numeric_expression.py`

## 4.2 Boundary-contract checks to add during project
- A BR-04 test proving `Plot` can render with an injected provider double (without concrete Figure internals).
- A BR-03/BR-08 test set proving collaborators do not reach into forbidden Figure internals.
- Architectural import-direction assertions for allowed/forbidden module dependencies.

## 4.3 Extended regression cadence
- Per merged phase: run full `pytest -q` before closeout.
- For phases touching rendering behavior: include notebook/widget smoke tests already present in repository test set.

---

### 5) Decision points and alternatives

A preferred approach is identified for each decision; alternatives are listed when materially different.

1. **Provider boundary style for BR-04**
   - **Preferred:** Python Protocol interface injected into `Plot` constructor.
   DECISION: CONFIRMED
   - Alternative: thin adapter object with concrete methods but no formal Protocol typing.
   - **Decision request:** confirm Protocol-first vs adapter-only.

2. **Hook dispatch ownership location**
   - **Preferred:** keep registration + dispatch API in `ParameterManager`; `Figure` calls one method.
DECISION: CONFIRMED
   - Alternative: separate hook bus component shared by Figure and ParameterManager.
   - **Decision request:** confirm whether to avoid introducing a new shared bus in this project.

3. **Range contract placement**
   - **Preferred:** place in figure-domain module near `View`/`ViewManager` to keep range semantics view-centric.
     DECISION: CONFIRMED
   - Alternative: generic utility module (risk: domain leakage).
   - **Decision request:** confirm view-domain placement.

If these decisions are approved as preferred, proceed with the phase sequence above without additional design branching.

---

### 6) Exit criteria mapping to phases

- Ownership matrix completion for public Figure methods and orchestration helpers: **Phases 1, 5, 6**.
- Boundary contracts documented and referenced by execution projects: **Phases 1, 4, 6**.
- Duplicate clusters with canonical-owner dispositions and linked execution tracks: **Phases 1, 3, 5, 6**.
- At least one dedup cluster implemented end-to-end with tests: **Phase 5 pilot**.
- Archived-036 concerns fully dispositioned: **Phase 6 closeout review**.
- No overlap drift with 032/035/033/023: **phase-gate check at each milestone**.

## Status

**Ready for architecture review and sequencing approval before implementation starts.**
