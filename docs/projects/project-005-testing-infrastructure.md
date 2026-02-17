# Project 005: Testing Infrastructure & CI

**Status:** Active
**Priority:** Medium

## Goal/Scope

Establish and mature the automated test infrastructure so that every PR is
validated by a reliable, comprehensive test suite with meaningful coverage
thresholds.

## Context

Core test infrastructure is in place: pytest discovers 149 tests across
26 files, GitHub Actions runs them against Python 3.10–3.12, and coverage
is reported with a conservative `fail_under = 50` floor. The remaining
work is raising that floor, integrating notebook-based tests into CI, and
adding coverage for under-tested subsystems.

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
- [ ] Add unit tests for currently-indirect-only utility functions
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
