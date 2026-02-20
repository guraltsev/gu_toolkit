# Project 037 — Revision Analysis v2 (`Figure.py` ownership boundaries + dedup)

## Purpose

This document analyzes the `REVISE` rows in `ownership-boundary-matrix-v1.md` against the **current code state** and proposes a practical **desired state** for convergence.

Primary inputs:

- `docs/projects/project-037-ownership-boundaries-and-dedup/ownership-boundary-matrix-v1.md`
- `Figure.py`
- `figure_plot.py`
- `figure_parameters.py`
- `figure_view.py`
- `figure_view_manager.py`

---

## 1) Ownership matrix revision for `Figure.py` + key collaborators

### Current state snapshot (as implemented)

| Area (from matrix REVISE rows) | Current implementation state | Current owner in practice |
| --- | --- | --- |
| Range and viewport state | `Figure` exposes both defaults (`x_range`,`y_range`) and live viewport (`_viewport_x_range`,`_viewport_y_range`,`current_x_range`,`current_y_range`), while persisting state onto active `View`. | Shared between `Figure` (API + widget sync), `View` (stored state), and Plotly widget runtime. |
| Sampling policy | Figure-level `sampling_points` exists and is consumed by `Plot.render()` as fallback (`plot.sampling_points or fig.sampling_points or 500`). | `Figure` default with per-plot override in `Plot`; not view-owned. |
| Plot registration and style normalization | `Figure.plot()` owns ID allocation, normalize/style alias handling, parameter auto-ensure, create/update branching, and registry mutation. | Mostly `Figure`; helper modules support normalization/style and `Plot` owns curve runtime. |
| Render orchestration | `Figure.render()` renders all plots for active view, marks inactive views stale on parameter change, runs parameter hooks, and triggers info updates; relayout path also flows via `Figure` debouncing methods. | `Figure` centralized orchestrator (broad ownership). |
| Hook management | `add_hook()` aliases `add_param_change_hook()`, both are `Figure` entrypoints but registration storage is in `ParameterManager` hooks. | Split but still tightly coupled: `Figure` invokes hooks by pulling manager internals. |

### Desired state (target ownership)

| Area | Desired owner | Desired boundary |
| --- | --- | --- |
| Range and viewport state | `View` + `ViewManager` | `Figure` remains façade only that delegates to `current_view` data; all range/viewport semantics unified into explicit view model contract (home/default vs live viewport). |
| Sampling policy | `View` (default) + `Plot` (override) | Figure-level global default becomes compatibility façade mapped to active-view policy. |
| Plot registration and style normalization | Plot registry component (+ `Plot` runtime) | `Figure.plot()` remains API, delegates create/update/normalize pipeline to registry service. |
| Render orchestration | `Figure` + extracted render coordinator utility | `Figure` keeps top-level coordination; stale-marking and per-reason policy become composable strategy/helper to reduce God-method pressure. |
| Hook management | `ParameterManager` for param-change hooks; separate render/event hook channel for `Figure` | No mixed hook semantics in one map; `Figure` should not directly own manager internals iteration. |

### Discrepancy and implementation difficulty

| Area | Current vs desired gap | Difficulty |
| --- | --- | --- |
| Range and viewport | Moderate/High: API surface already broad, and plot runtime reads figure-level range APIs directly. | **Medium-High** (state model and compatibility shims needed). |
| Sampling policy | Moderate: moving figure default to view default impacts render defaults and serialization expectations. | **Medium**. |
| Plot registration/style | High: `Figure.plot()` currently coordinates several responsibilities in one path. | **High** (extract service + preserve API behavior). |
| Render orchestration | Moderate: logic centralized but coherent; extraction is mostly structural if semantics are preserved. | **Medium**. |
| Hook management | Moderate: currently one param-hook path; split requires explicit event taxonomy. | **Medium**. |

---

## 2) Boundary-rule table (allowed/forbidden directions)

This table refines BR-01..BR-10 into implementation-checkable directionality.

| Rule ID | Direction | Allowed? | Current state check |
| --- | --- | --- | --- |
| BR-01 | `Figure` -> `FigureLayout`/`ParameterManager`/`InfoPanelManager`/`LegendPanelManager`/`ViewManager`/`Plot` | Allowed | Implemented as intended. |
| BR-02 | `FigureLayout` -> `Figure` | Forbidden | No direct dependency observed. |
| BR-03 | `ParameterManager` -> `Figure` | Forbidden | Enforced: manager only uses render callback contract. |
| BR-04 | `Plot` -> parameter context protocol (not concrete manager type) | Allowed (contract-only) | **Partially met**: plot consumes `self._smart_figure.parameters.parameter_context`; still figure-coupled. **Desired state** parameter context provider is specifcied at the momement of creating and semi-private api allows redefining provider (should generally not be needed). Functionality exprosed by `PlotManager`. `Figure` worries about updates if some signifcant reorganization of parameterManager occurs. |
| BR-05 | `Plot` -> `FigureLayout` | Forbidden | Enforced: no layout import/use in plot runtime. |
| BR-06 | `InfoPanelManager`/`LegendPanelManager` -> parameter read/observe contract | Allowed (read + observe) | Appears aligned; should keep contract boundary explicit. |
| BR-07 | `ViewManager` -> plot/parameter internals | Forbidden | Enforced in current manager implementation. |
| BR-08 | Collaborators -> `Figure` private methods | Forbidden | Mostly enforced; plot uses public façade, but still holds concrete `Figure` reference. |
| BR-09 | Utility modules -> domain modules (reverse import) | Forbidden | Appears aligned in sampled modules. |
| BR-10 | `PlotlyPane` adapters -> orchestration/policy modules | Forbidden | Appears aligned. |

### Highest-risk boundary discrepancy

`BR-04` remains the largest unresolved boundary concern: plot evaluation depends on `Figure` as the gateway to parameter context and range defaults. The desired contract should inject a narrow provider protocol at plot construction time.

---

## 3) Convergence checklist (summary only)

- [ ] Finalize `REVISE` row decisions into explicit `Approved` target owners and migration actions.
- [ ] Define and document a single range contract (`default/home` vs `viewport/current`) owned by `View`.
- [ ] Introduce a view-scoped sampling policy contract and map figure-level compatibility accessors.
- [ ] Extract plot create/update/normalize pipeline behind a dedicated registry/service while preserving `Figure.plot()` façade.
- [ ] Split hook channels by domain (parameter-change hooks vs render/system hooks) and remove mixed ownership ambiguity.
- [ ] Add a narrow injected parameter-context provider interface for plot runtime (remove concrete figure-manager path reliance).
- [ ] Add contract tests that enforce boundary directions (especially BR-03/BR-04/BR-08).
- [ ] Run one pilot dedup slice from a `REVISE` row and feed results into project-033 ledger.

