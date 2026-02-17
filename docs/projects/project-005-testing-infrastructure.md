# Project 005: Testing Infrastructure & CI

**Status:** Active
**Priority:** Medium

## Goal/Scope

Establish and mature the automated test infrastructure so that every PR is
validated by a reliable, comprehensive test suite with meaningful coverage
thresholds.

## Context

Core test infrastructure is in place: pytest now discovers 154 tests across
27 files, GitHub Actions runs them against Python 3.10–3.12, and coverage
configuration is enforced with `fail_under = 75`. Remaining work focuses on
notebook-based tests in CI and deeper coverage for numeric edge cases and
widget-level behavior.

## Assessment (2026-02-17)

- Current baseline: local `pytest` run passes with **154 tests** across the existing
  suite, indicating the core infrastructure is stable for Python-side tests.
- Coverage gate is already configured above this project's original minimum
  milestone (`fail_under = 75` in `pyproject.toml`), so the historical
  “raise threshold to 70%” exit criterion is satisfied at configuration level.
- The project roadmap item for direct unit tests of utility helpers
  (`_resolve_symbol`, `_normalize_vars`, and `InputConvert` edge cases) has now
  been implemented via a dedicated regression test module.
- `plan.md` note: this legacy project is maintained as a single markdown file and
  does not currently include a separate `plan.md`; implementation followed the
  explicit TODO checklist in this document because the next step was
  unambiguous.

## Completed

- [x] `tox.ini` with `py310`, `py311`, `py312` environments.
- [x] Pytest and coverage configuration in `pyproject.toml`.
- [x] GitHub Actions workflow at `.github/workflows/tests.yml`.
- [x] Legacy manual `main()` harnesses converted to pytest-native discovery.
- [x] Cross-platform environment setup scripts (`.environment/`).
- [x] Offline pytest-cov shim for restricted environments.

## TODO checklist

- [ ] Raise coverage threshold incrementally (60% → 70% → 80%) as tests are added.
- [ ] Integrate notebook tests into CI using `nbval` or `pytest-notebook`.
- [x] Add unit tests for currently-indirect-only utility functions
      (`_resolve_symbol`, `_normalize_vars`, `InputConvert` edge cases).
- [ ] Add property-based tests (Hypothesis) for `InputConvert` and `numpify`
      numeric edge cases.
- [ ] Evaluate browser-level widget testing (Playwright or similar) for
      `PlotlyPane` and `Slider` rendering verification.

## Exit criteria

- [ ] Coverage threshold is at or above 70%.
- [ ] Notebook-based tests run in CI without manual intervention.
- [ ] All test files use standard pytest patterns.
- [ ] Priority coverage gaps (utilities, numeric edge cases) are addressed.


## Implementation progress checklist

- [x] Added direct regression tests for utility resolution and vars normalization helpers.
- [x] Added direct regression tests for `InputConvert` edge-case truncation semantics.
- [ ] External review of Project 005 updates (required before closure).

## Challenges and mitigations

- **Challenge:** Notebook tests depend on kernel availability and widget
  rendering, which is fragile in CI.
  **Mitigation:** Use `nbval --sanitize-with` or headless kernel; keep
  notebook tests in a separate CI job that is allowed to be non-blocking
  initially.

- **Challenge:** Raising coverage too aggressively may produce low-value
  tests written only to hit lines.
  **Mitigation:** Raise the floor incrementally and focus new tests on
  behavioral contracts, not line coverage.
