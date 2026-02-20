# Project 037: Pytest Structure Mirroring and Test Suite Taxonomy

## Status

**Discovery (preferred approach selected; awaiting implementation planning)**

## Goal/Scope

Design a repository-wide test organization model that scales beyond a flat `tests/` directory by:
- mirroring source module structure inside `tests/` for discoverability,
- categorizing tests by scope (`unit/`, `integration/`, `functional/` or `e2e/`),
- centralizing reusable setup in layered `conftest.py` files,
- standardizing marks so logical grouping is independent of file location.

In-scope:
- target test directory layout,
- naming/placement rules,
- fixture placement strategy,
- mark registration and usage policy,
- migration sequencing constraints for the existing suite.

Out-of-scope for this summary:
- implementation details and per-file migration execution,
- writing or rewriting tests,
- introducing CI workflow changes beyond what is needed to support the new taxonomy.

## Summary of design

### Current-state analysis

The current test suite is largely flat under `tests/` with many module-specific and project-phase-specific files co-located, plus notebook tests in the same top-level folder. This works for small volume but creates increasing friction for navigation and selective execution as test count grows.

A quick codebase review also shows pytest is configured with default `test_*.py` discovery and a single `tests` testpath, which means the suite is ready for nested directories without major discovery changes.

### Preferred approach (selected)

Use a **scope-first + mirror-within-scope** structure:
- `tests/unit/` mirrors application modules for isolated logic tests.
- `tests/integration/` groups cross-module behaviors.
- `tests/functional/` (or `tests/e2e/`) holds user-journey/system-level tests.
- notebook tests move to a dedicated notebook-oriented subtree (for example `tests/notebooks/`) so they do not clutter Python test slices.

Proposed target shape:

```text
tests/
├── conftest.py
├── unit/
│   ├── conftest.py
│   ├── test_Figure.py
│   ├── figure/
│   │   ├── test_plot_pipeline.py
│   │   └── test_display_contract.py
│   └── parsing/
│       └── test_parse_latex.py
├── integration/
│   ├── conftest.py
│   └── test_figure_view_lifecycle.py
├── functional/
│   └── test_notebook_user_flow.py
└── notebooks/
    └── test_toolkit_overview.ipynb
```

Key rules:
1. Keep `test_*.py` naming convention.
2. Mirror by feature/module where possible to minimize placement ambiguity.
3. Keep global fixtures in `tests/conftest.py`; place domain fixtures in narrower `conftest.py` files.
4. Use marks (`slow`, `integration`, `notebook`, `database`, etc.) for orthogonal grouping.
5. Register project marks centrally to avoid unknown-mark warnings.

### Why this is preferred over alternatives

This repository already has a meaningful distinction between fast pure-Python tests and heavier behavioral/notebook tests. A scope-first top level preserves fast local developer loops while mirror-within-scope keeps ownership discoverable. It also aligns with standard pytest expectations and minimizes tooling risk because discovery settings already support nested layouts.

### Alternatives considered

1. **Pure mirror only (no scope split)**
   - Pros: easiest place-to-find mapping from source to tests.
   - Cons: weak control over runtime cost; difficult to isolate fast suites.

2. **Pure scope split only (no mirroring discipline)**
   - Pros: simple speed-based execution targeting.
   - Cons: placement ambiguity grows over time; inconsistent local conventions.

Given current suite growth and mixed test modalities, the combined approach is the clearest default.

## Open questions

1. Should notebook tests live under `tests/functional/notebooks/` or a separate `tests/notebooks/` lane for tooling clarity?
2. Is `functional/` or `e2e/` the preferred terminology for this repository’s highest-level tests?
3. Should legacy project-phase tests (`test_project0xx_*.py`) be preserved as historical naming, or renamed to behavior-oriented names during migration?
4. Which initial mark set should be mandatory (minimum viable taxonomy) vs optional?

## Challenges and mitigations

- **Challenge:** large rename/move churn can obscure review history.
  - **Mitigation:** migrate in phases and prefer pure move commits before behavior edits.

- **Challenge:** fixture breakage when moving tests across directory scopes.
  - **Mitigation:** define fixture ownership map before moves; add scoped `conftest.py` files incrementally.

- **Challenge:** slow tests accidentally running in fast feedback loops.
  - **Mitigation:** introduce and enforce marks for `slow`/`integration`/`notebook`; document default local command sets.

- **Challenge:** ambiguity for files that test multiple modules.
  - **Mitigation:** default placement by dominant behavior under `integration/` and mark with additional metadata.

## TODO

- [ ] Confirm top-level taxonomy names (`unit`, `integration`, `functional`/`e2e`, `notebooks`).
- [ ] Produce file-by-file migration map from current flat layout to target paths.
- [ ] Define fixture layering strategy (`tests/conftest.py` + scoped conftests).
- [ ] Define and register canonical pytest marks in project config.
- [ ] Specify default developer/CI command matrix (fast vs full suites).
- [ ] Create implementation blueprint in `plan.md` after open questions are resolved.

## Exit criteria

- [ ] New test layout convention is documented with explicit placement rules.
- [ ] Source-to-test mirroring rules are defined for unit tests.
- [ ] Scope-based segmentation is defined and actionable.
- [ ] Fixture strategy via layered `conftest.py` is documented.
- [ ] Mark taxonomy and intended selectors are documented.
- [ ] Implementation planning handoff is ready (but not yet executed).
