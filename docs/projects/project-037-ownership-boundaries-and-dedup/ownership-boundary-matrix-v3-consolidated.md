# Project 037 — Consolidated Ownership Matrix v3 (`Figure.py` ecosystem)

## Status

**Draft — consolidated from v1 + revision analysis v2, validated against current code**

## Summary

This document consolidates:

- `ownership-boundary-matrix-v1.md` (full initial matrix + BR-01..BR-10), and
- `revision-analysis-v2.md` (REVISE-row implementation check + desired-state direction),

into one implementation-checked matrix for Project 037.

Primary verification inputs used for this consolidation:

- `Figure.py`
- `figure_plot.py`
- `figure_parameters.py`
- `figure_view.py`
- `figure_view_manager.py`

---

## A) Consolidated ownership matrix (all rows, implementation-checked)

Legend:

- **Current owner (verified):** based on current code behavior.
- **Desired owner:** target ownership boundary for convergence.
- **Correctness vs code:** whether current implementation matches intended boundary direction.
- **Complexity:** practical migration complexity from current to desired state.

| Area | Representative API/methods in `Figure.py` | Current owner (verified) | Desired owner | Consolidated action | Correctness vs code | Complexity | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Figure construction + collaborator wiring | `Figure.__init__`, `_create_view_runtime`, `_runtime_for_view` | `Figure` orchestrates wiring and per-view runtime creation | `Figure` thin orchestrator + collaborator factories where useful | **retain + thin** | **Aligned** | **Medium** | Wiring is centralized and coherent; extraction should avoid reducing readability. |
| Workspace/view lifecycle | `add_view`, `set_active_view`, `view`, `remove_view`, `active_view_id`, `views` | `Figure` facade + `ViewManager` state owner | `ViewManager` owner, `Figure` facade | **retain facade; continue moving internals** | **Mostly aligned** | **Low-Medium** | `ViewManager` already owns view registry/active transitions; `Figure` still performs UI/runtime sync orchestration. |
| Layout/sidebar synchronization | `_sync_sidebar_visibility`, `title` accessors, display wrapper paths | `Figure` delegates sidebar visibility to `FigureLayout` | `FigureLayout` authoritative, `Figure` entrypoint | **retain entrypoints + delegate policy** | **Aligned** | **Low** | No boundary inversion observed. |
| Plot host access | `figure_widget`, `figure_widget_for`, `pane`, `pane_for` | View runtime mapped in `Figure` per-view runtime table | View runtime owner surfaced via `Figure` facade | **retain facade** | **Aligned** | **Low** | Keeps compatibility while preserving runtime locality. |
| Parameter API | `parameter`, `add_param`, `parameters`, `params`, `add_param_change_hook`, `snapshot` | `Figure` API facade + `ParameterManager` registry/hook store | `ParameterManager` authoritative | **retain facade + delegate** | **Mostly aligned** | **Low** | One leakage remains: `Figure.render` iterates manager hooks directly. |
| Range + viewport state | `x_range`, `y_range`, `_viewport_x_range`, `_viewport_y_range`, `current_x_range`, `current_y_range` | Shared: `Figure` API + Plotly live layout + `View` storage | `View`/`ViewManager` contract (home/default vs viewport/current) with `Figure` facade only | **approve move to view-owned contract** | **Partially aligned** | **Medium-High** | Existing semantics are functional but split across layers and names. |
| Sampling policy | `sampling_points` | Figure default + per-plot override fallback (`Plot.render`) | View default + plot override (`Figure` compatibility facade) | **approve migration to view-scoped default** | **Not aligned yet** | **Medium** | Current default is figure-global; migration needs compatibility behavior. |
| Plot registration + style normalization | `plot`, `plot_style_options` | `Figure.plot` owns normalization, id/update path, and registry mutation | Plot registry/service + `Plot` runtime, `Figure.plot` as facade | **approve extraction** | **Not aligned yet** | **High** | Current path is monolithic but stable; extraction should be slice-based. |
| Render orchestration | `render`, `_throttled_relayout`, `_run_relayout`, `_log_render` | `Figure` central orchestrator + per-view debouncer plumbing | `Figure` orchestrator + extracted render coordinator policy helpers | **retain orchestrator + extract policy helpers** | **Aligned direction, overly broad method** | **Medium** | Keep orchestration root in `Figure`, reduce god-method pressure. |
| Info panel/public info hooks | `info`, `info_output` | `Figure` facade + `InfoPanelManager` owner | `InfoPanelManager` authoritative | **retain facade + delegate** | **Aligned** | **Low** | Boundary intent already clean. |
| Hook management | `add_hook`, `add_param_change_hook` (+ render-time invocation path) | Registration in `ParameterManager`; execution loop currently in `Figure.render` | `ParameterManager` for param hooks + separate render/system hook channel in `Figure` | **approve split ownership and execution boundary** | **Partially aligned** | **Medium** | Current API aliases are fine; execution-path separation is pending. |
| Notebook integration/context | `_ipython_display_`, `__enter__`, `__exit__` + figure-context helpers | `Figure` + `figure_context` | Same | **retain** | **Aligned** | **Low** | Fits orchestrator-facing responsibilities. |
| Code generation/export | `to_code`, `code`, `get_code` | `Figure` facade + dedicated codegen path | Same, with heavy logic in codegen module | **retain facade + keep heavy logic external** | **Aligned** | **Low** | Already mostly in desired shape. |

---

## B) Consolidated boundary rules BR-01..BR-10 (with code-state check)

| Rule ID | Direction | Policy | Current state |
| --- | --- | --- | --- |
| BR-01 | `Figure` -> collaborators (`FigureLayout`, `ParameterManager`, `InfoPanelManager`, `LegendPanelManager`, `ViewManager`, `Plot`) | Allowed | Present |
| BR-02 | `FigureLayout` -> `Figure` | Forbidden | No direct dependency observed in current modules |
| BR-03 | `ParameterManager` -> `Figure` | Forbidden | Manager uses render callback contract and does not import `Figure` runtime internals |
| BR-04 | `Plot` -> parameter context protocol (not concrete manager) | Allowed (contract-only) | `Plot` still accesses `self._smart_figure.parameters.parameter_context` and other figure defaults |
| BR-05 | `Plot` -> `FigureLayout` | Forbidden | No layout dependency in plot runtime |
| BR-06 | `InfoPanelManager` / `LegendPanelManager` -> parameter read/observe contract | Allowed (read + observe) | Compatible with current role split |
| BR-07 | `ViewManager` -> plot/parameter internals | Forbidden | `ViewManager` remains view-state only |
| BR-08 | Collaborators -> `Figure` private methods | Forbidden | Mostly respected; `Plot` remains coupled to concrete `Figure` object (public API usage) |
| BR-09 | Utility modules -> domain modules (reverse import) | Forbidden | Sampled modules follow this |
| BR-10 | Adapter layer (`PlotlyPane`) -> orchestration/policy modules | Forbidden | Appears respected |

### Highest-risk discrepancy (confirmed)

`BR-04` remains the most significant unresolved boundary: `Plot` depends on concrete figure-owned parameter/range access. The target is a narrow provider protocol injected at plot creation (or via a registry service) so plot evaluation remains stable if figure internals evolve.

---

## C) Strengths and weaknesses of the desired state

### Strengths

1. **Clearer ownership boundaries:** per-domain responsibilities become explicit (view state vs parameter state vs plot runtime vs layout).
2. **Lower coupling risk:** protocol-based parameter/range access reduces direct dependency on `Figure` internals.
3. **Better dedup leverage (Project 033):** extraction points become obvious (`Figure.plot` pipeline, hook execution policy, range contract).
4. **Safer package reorg (Project 023):** boundary rules provide directional guardrails before physical module moves.
5. **Improved testability:** thinner orchestrator and extracted services allow narrower unit tests and less notebook-heavy end-to-end dependence.

### Weaknesses / risks

1. **Migration complexity in hot paths:** `plot()` and `render()` are high-traffic APIs; behavior regressions are easy to introduce.
2. **Compatibility surface is broad:** existing public aliases and historic semantics constrain refactor freedom.
   Note: backwards compatibility is not an issue and can be freely ignored (currently is private project)
4. **State-contract churn risk:** range/home/viewport normalization affects persistence, stale handling, and live relayout behavior.
5. **Potential over-abstraction:** premature service extraction could add indirection without immediate value if not done incrementally.
6. **Inter-project coordination overhead:** 037 decisions need continuous alignment with 035/033/023 to avoid drift.

---

## D) Feasible phased convergence plan (implementation-safe)

1. **Range contract phase (Medium-High):**
   - Define one view-owned contract: `default_*_range` vs `viewport_*_range`.
   - Keep current `Figure` accessors as compatibility facade.
   - Add targeted tests for view switching + relayout persistence.

2. **Sampling policy phase (Medium):**
   - Introduce optional view-level sampling default.
   - Preserve current `Figure.sampling_points` as active-view compatibility alias.
   - Verify serialization and render fallback behavior.

3. **Plot registration extraction phase (High):**
   - Extract normalize/create/update logic behind a plot-registry helper/service.
   - Keep `Figure.plot()` signature and behavior stable.
   - Add regression tests for idempotent updates and style alias handling.

4. **Hook split phase (Medium):**
   - Keep param-change hooks in `ParameterManager`.
   - Add separate render/system hook channel in `Figure`.
   - Remove direct manager internals iteration from generic render path.

5. **Boundary hardening phase (Medium):**
   - Introduce provider protocol for `Plot` parameter/range access (address BR-04).
   - Add boundary contract tests for BR-03/BR-04/BR-08.

---

## E) Updated checklist

- [x] Consolidate v1 matrix + v2 revision analysis into one implementation-checked artifact.
- [x] Validate each matrix row against current code ownership and behavior.
- [x] Validate boundary-rule feasibility against current module interactions.
- [x] Add explicit strengths/weaknesses analysis for desired-state architecture.
- [ ] Run an external architecture review pass and convert remaining partial rows into approved execution slices.
