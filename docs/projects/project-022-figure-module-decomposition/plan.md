# Project 022 — Figure Module Decomposition (Implementation Blueprint)

## Detailed blueprint for implementation

### 1) Why this project now (cross-project alignment)

This plan updates Project 022 from a high-level extraction list into an execution blueprint that is consistent with:

- **Project 022 goals** in `project-022-figure-module-decomposition.md` (shrink `Figure.py`, isolate plot normalization, separate view lifecycle, and move module-level API wrappers).
- **Project 023 dependency** (package reorganization explicitly depends on 022 extraction first).
- **Project 032 umbrella sequencing** (022 is a Phase 2 core decomposition priority after safety-net/tooling).
- **Project 035 program posture** (private-repo migration can prefer direct cutovers over long-lived compatibility shims; prioritize architectural clarity over preserving internal paths).
- **Current repository evidence** (existing tests already reference phased decomposition and view/legend/layout split work, indicating that incremental architecture changes are feasible while keeping the toolkit runnable).

### 2) Architectural target state (what “done” should look like)

At completion, `Figure` is a small coordinator that wires dedicated subsystems:

- **Public API surface module**
  - `figure_api.py` (or package-equivalent) owns module-level helpers (`plot`, `parameter`, `render`, etc.).
  - `Figure.py` no longer contains dozens of public free-function wrappers.

- **Plot request normalization subsystem**
  - Stateless normalizer module/class handling input forms, symbol coercion, and numeric-binding setup.
  - `Figure.plot()` becomes orchestration-only (validate -> normalize -> delegate -> register/update).

- **View lifecycle subsystem**
  - Dedicated manager owning create/remove/select/lookup view operations and stale-state transitions.
  - `Figure` interacts via explicit manager API; no scattered stale-marking rules.

- **Runtime handle policy**
  - Replace mutable alias pattern (`self._figure`, `self._pane`) with explicit current-view resolution APIs.
  - All UI/plot operations fetch active handles from authoritative per-view state.

- **Observability and invariants**
  - Internal contracts documented: “what can mutate where,” “what marks stale,” “when render synchronizes state.”
  - Characterization tests lock behavior before each major extraction.

### 3) Non-goals (for this project)

- Full package move to layered subpackages (that is Project 023, after decomposition stabilizes).
- Broad DRY cleanup outside Figure-related hot paths (Project 033 scope).
- UI feature redesign (legend UX refresh projects).

### 4) Migration strategy principles

Because this is a private codebase and backward compatibility is not strictly required:

1. **Prefer direct internal cutovers** over long transition layers.
2. **Keep public notebook workflow intact** (`from gu_toolkit import ...`) unless explicitly retired.
3. **Phase in behavior-preserving refactors with characterization tests first**.
4. **Each phase must leave HEAD green and toolkit runnable** (import + plot + render smoke path works).
5. **Defer filename/package normalization** to Project 023 unless needed for a clean extraction seam.

---

## Phased implementation plan (each phase leaves working state)

### Phase 0 — Baseline lock + decomposition map

**Objective:** Freeze current behavior and make extraction boundaries explicit before code motion.

**Changes**
- Add/update characterization tests for:
  - module-level helper delegation behavior,
  - `plot()` input permutations currently accepted,
  - multi-view create/switch/remove/stale behavior,
  - alias-dependent behavior (`_figure`/`_pane`) that must be intentionally replaced.
- Add a short architecture note documenting current `Figure.py` responsibility slices and target owners.

**Working-state gate**
- All existing tests + new characterization tests pass.
- No production behavior changes.

**Exit artifacts**
- Baseline tests become acceptance oracle for subsequent phases.

---

### Phase 1 — Extract module-level Figure API wrappers

**Objective:** Remove free-function wrapper clutter from `Figure.py` into dedicated API module.

**Changes**
- Introduce `figure_api.py` (name can be adapted to final package conventions).
- Move module-level wrappers (e.g., `plot`, `parameter`, `render`, ranges/titles/labels helpers) into API module.
- Keep root-level imports stable via `__init__.py` re-exports and/or delegated imports.
- Keep `_require_current_figure()` ownership explicit (either moved with wrappers or exposed from a focused context helper).

**Working-state gate**
- Public import smoke tests pass (`from gu_toolkit import plot, parameter, render, Figure`).
- Notebook-style call path works unchanged.

**Why this order**
- Low-risk extraction with immediate LOC reduction in `Figure.py`.
- Unblocks later `Figure` coordinator simplification.

---

### Phase 2 — Extract PlotInputNormalizer subsystem

**Objective:** Remove complex normalization branches from `Figure.plot()` while preserving accepted call forms.

**Changes**
- Create stateless normalizer module/class for:
  - input shape normalization,
  - symbol coercion,
  - numeric-function variable rebinding.
- Convert `Figure.plot()` into orchestrator with explicit steps:
  1. validate raw input,
  2. normalize via subsystem,
  3. resolve style/update policy,
  4. create or update plot object.
- Eliminate deep inline if/elif normalization chains from `Figure.py`.

**Working-state gate**
- Characterization tests for supported `plot()` input forms pass.
- Plot creation/update/render smoke tests pass.

**Why this order**
- Highest complexity hotspot; isolating it reduces change-risk for subsequent view and render refactors.

---

### Phase 3 — Extract ViewManager and stale-state policy

**Objective:** Centralize view lifecycle and stale-state transitions in a single manager.

**Changes**
- Implement `ViewManager` responsible for:
  - add/remove/select/lookup view,
  - active view resolution,
  - stale-marking API (`mark_stale(view_id|all, reason)`),
  - consistency checks for active/deleted views.
- Migrate view methods from `Figure` to manager-backed delegation.
- Replace ad-hoc stale toggles in `render`/relayout hooks with manager calls.

**Working-state gate**
- Multi-view tests pass (including context switching and stale-driven rerender behavior).
- No orphan/stale active-view states after remove/switch sequences.

**Why this order**
- Completes the second major hotspot identified in Project 022 and aligns with multi-view architecture from completed Project 019/028 work.

---

### Phase 4 — Remove legacy mutable aliases (`_figure` / `_pane`)

**Objective:** Replace alias state with explicit per-view handle resolution.

**Changes**
- Add explicit accessors (e.g., `figure_widget_for(view_id)` / `pane_for(view_id)` or manager-backed equivalent).
- Update all internal callers to use explicit accessors.
- Remove or hard-error legacy aliases (private repo allows hard cutover).
- Ensure render/update paths always resolve current handles from authoritative view state.

**Working-state gate**
- No internal reads/writes of removed aliases remain.
- Render/update/legend/info interactions still pass existing tests.

**Why this order**
- Alias removal is safest after view ownership is centralized.

---

### Phase 5 — Coordinator slimming + contract hardening

**Objective:** Finalize `Figure` as coordinator-only and lock new subsystem contracts.

**Changes**
- Enforce responsibility boundaries:
  - `Figure` orchestration only,
  - no duplicated normalization/view logic.
- Add module/class docstrings for extracted subsystems and invariants.
- Add boundary tests ensuring `Figure` delegates instead of re-implementing subsystem logic.
- Record measurable outcomes (e.g., line-count delta, method-count reduction, complexity metrics).

**Working-state gate**
- Full test suite passes.
- `Figure.py` materially reduced and no longer contains extracted hotspots.

**Why this order**
- Final consolidation phase after behavior and structure are already stable.

---

## Acceptance test suite description

The acceptance suite should combine existing tests with targeted additions:

1. **Public API compatibility checks**
   - Import-path smoke tests from root package for core Figure helpers.
   - Ensure notebook-first usage pattern still works.

2. **Plot normalization parity tests**
   - Parameterized tests over accepted input forms and symbol variants.
   - Regression tests for create-vs-update branch behavior.

3. **View lifecycle/state tests**
   - Add/switch/remove view scenarios.
   - Stale-marking transitions and rerender expectations.

4. **Render pipeline integration tests**
   - End-to-end: parameter changes -> stale mark -> render -> visible update.

5. **Alias-removal safety tests**
   - Ensure no hidden dependency on `_figure` / `_pane` remains.

6. **Architecture conformance checks (lightweight)**
   - Optional: simple test/lint guard that prevents re-introducing extracted helper implementations inside `Figure.py`.

### Suggested CI gates per phase

- **Required per phase:** targeted tests + at least one integration smoke test.
- **Required at merge points:** full `pytest` run.
- **Optional but recommended:** static analysis checks from Project 031 once enabled.

---

## Risk register and mitigations

- **Risk:** Semantic drift in `plot()` normalization.
  - **Mitigation:** Phase 0 characterization matrix before extraction; preserve failing examples as regression tests.

- **Risk:** Hidden coupling to mutable aliases.
  - **Mitigation:** search-driven cleanup + alias-removal tests in Phase 4.

- **Risk:** View stale-state regressions across render paths.
  - **Mitigation:** single stale API in ViewManager + integration tests that assert lifecycle transitions.

- **Risk:** Large PR churn.
  - **Mitigation:** phase-scoped PRs with stable working state at each cut; avoid mixing Project 023 path moves into 022 phases.

---

## Deliverables checklist (project-level)

- [ ] Phase 0 baseline characterization completed.
- [x] Module-level API wrappers extracted from `Figure.py`.
- [x] Plot input normalization extracted and fully delegated.
- [ ] View lifecycle + stale-state centralized in `ViewManager`.
- [ ] Legacy `_figure` / `_pane` alias state removed.
- [ ] `Figure.py` reduced to coordinator-focused responsibilities.
- [ ] Acceptance suite green across all decomposition milestones.
- [ ] Project 022 completion note added; Project 023 dependency unblocked.


## Progress Notes (2026-02-20)

- [x] Phase 1 implemented via `figure_api.py` extraction and re-export wiring.
- [x] Phase 2 implemented via `figure_plot_normalization.py` extraction and `Figure.plot()` delegation.
- [x] Added decomposition regression tests for package helper compatibility and normalizer contracts.
- [ ] Phase 3 (ViewManager extraction) pending.
- [ ] Phase 4 (`_figure` / `_pane` alias removal) pending.
- [ ] Phase 5 coordinator slimming/hardening pending.
