# Project 023: Package Reorganization — Why `Figure.py` Is Still Large

## Goal/Scope

Document why project-023 appears largely implemented at the architectural level, yet `Figure.py` remains a large file.

## Summary of design

### Executive finding

`Figure.py` is still large primarily because project-023 and project-022 solved different problems:

1. **Project-023 (package reorganization) changed structure expectations, not line-count targets.**
   - The project’s success criteria are package topology, naming normalization, and migration of modules into subpackages.
   - It does not directly require shrinking `Figure.py` beyond what project-022 already attempted.

2. **Project-022 extracted several subsystems, but preserved a thick coordinator facade.**
   - The module did shrink from ~2,098 lines to ~1,564 lines, but still retains a large orchestration surface and API-preservation wrappers.
   - This is a meaningful reduction, but not enough to make the file small.

3. **The file still owns many responsibilities that were intentionally not fully externalized.**
   - View lifecycle orchestration.
   - Range/sampling state policy and property wrappers.
   - Plot orchestration entrypoint (`plot`) and create/update branching.
   - Render pipeline wiring, hook registration, notebook display lifecycle, and context-manager semantics.
   - Snapshot/codegen convenience methods.

4. **Compatibility and ergonomics keep many methods centralized.**
   - Even where helper modules exist (`figure_plot_normalization.py`, `figure_plot_style.py`, `figure_view_manager.py`, `figure_api.py`), the public and notebook-facing usage model still routes through the `Figure` class.
   - That keeps `Figure.py` as a high-density composition root.

### Evidence snapshot

- Current size: `Figure.py` is **1,564 lines**.
- Largest remaining single method: `Figure.plot()` is **236 lines**.
- The class still contains dozens of methods spanning lifecycle, UI/runtime accessors, rendering, hooks, and serialization conveniences.
- Top-level package remains mostly flat, so package reorganization outcomes are only partially reflected in filesystem topology.

### Why this can look “largely implemented” while still being large

The repository now has many focused `figure_*` modules and manager classes, so decomposition progress is visible. But because these are consumed via `Figure` as the orchestrator/facade, complexity moved from “deep internal logic” to “broad coordination surface.” The breadth remains in one class file, so line count stays high.

## Open questions

1. Should project-023 be considered partially complete only after physical subpackage moves (`figure/`, `core/`, `math/`, etc.) are done, rather than after responsibility extraction?
2. Is the under-800 line target for `Figure.py` still required, or should success be reframed around complexity metrics (e.g., max method length, cyclomatic complexity, and import-boundary rules)?
3. Should convenience APIs (`snapshot`, codegen helpers, display/context-manager glue) move to thin adapters to keep `Figure` coordinator-only?

## Challenges and mitigations

- **Challenge:** Further shrinking `Figure.py` risks API churn in notebook workflows.
  - **Mitigation:** Keep the public surface but move implementations behind explicit service objects/adapters.

- **Challenge:** Pure line-count reductions can scatter ownership across many files.
  - **Mitigation:** Extract by cohesive domains (render lifecycle, plotting pipeline, hooks, serialization) with clear ownership contracts.

- **Challenge:** Project-023 completion can be conflated with project-022 decomposition progress.
  - **Mitigation:** Track them with separate acceptance criteria and a shared roll-up dashboard (project-035 umbrella).

## Status

**Analysis complete (2026-02-20).**

Conclusion: project-023 can appear “largely implemented” from decomposition signals, but `Figure.py` remains large because it is still the intentionally central orchestrator/facade and because filesystem-level package migration is not yet fully realized.

## TODO

- [ ] Decide whether to keep or retire the under-800 LOC `Figure.py` target.
- [ ] Define a concrete “coordinator-only” extraction plan for remaining heavy responsibilities (`plot`, render lifecycle, hook pipeline, codegen bridge).
- [ ] Execute physical subpackage migration for project-023 (`core/`, `figure/`, `math/`, `widgets/`, `snapshot/`).
- [ ] Add objective complexity gates (method length/complexity/import boundaries) to prevent coordinator regrowth.

## Exit criteria

- [ ] A documented, approved definition of “project-023 complete” exists and distinguishes it from project-022.
- [ ] `Figure.py` has either met the revised size target or passed agreed complexity thresholds.
- [ ] Package topology migration is complete and validated with tests/import checks.
- [ ] Public API behavior remains intact for notebook-facing workflows.
