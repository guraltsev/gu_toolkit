# Issue 023: Example notebook callable plot raises missing `x` parameter context KeyError

## Status
Open

## Summary
State-of-completion checklist:
- [x] Deterministic regression test exists for callable arg-name mismatch with explicit `vars=(x, a)` rebinding.
- [x] Callable normalization fix for explicit `vars=` rebinding is implemented in `Figure._normalize_plot_inputs`.
- [x] Project-level callable-first test suite covers single-variable and multi-variable callable plotting paths.
- [ ] The example notebook still contains the captured `KeyError` traceback and `#BUG` marker in callable walkthrough cells.
- [ ] Notebook parity acceptance test is still failing due to placeholder bug markers.

## Evidence
- `tests/test_project029_plot_callable_first.py::test_plot_callable_first_explicit_vars_rebinds_callable_order_to_plot_variable` passes.
- `tests/test_notebook_documentation_quality.py::test_toolkit_overview_notebook_has_no_placeholder_bug_markers` currently fails because notebook bug markers remain.
- `docs/notebooks/Toolkit_overview.ipynb` still includes `#BUG: see below` and a markdown traceback block for missing `x` context.

## TODO
- [x] Reproduce the failure with a deterministic regression test.
- [x] Implement callable normalization fix and assert expected behavior in tests.
- [ ] Replace notebook traceback/BUG placeholder with working runnable example text and code.
- [ ] Re-run notebook documentation quality test after notebook cleanup.

## Exit criteria
- [ ] Callable plotting tutorial path in notebook runs without `KeyError` tracebacks in published content.
- [ ] Automated tests cover callable-first render/re-render behavior and notebook quality gates.
