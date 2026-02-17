# Issue 023: Example notebook callable plot raises missing `x` parameter context KeyError

## Status
Open (fix updated after reviewer feedback; pending external review)

## Summary
State-of-completion checklist:
- [x] Deterministic regression test exists for callable arg-name mismatch with explicit `vars=(x, a)` rebinding.
- [x] Callable normalization handles both explicit `vars=` rebinding and single-variable implicit rebinding (including `SymbolFamily` plot symbols).
- [x] Project-level callable-first test suite covers single-variable and multi-variable callable plotting paths.
- [x] Example notebook callable walkthrough now uses runnable content and no longer includes captured `KeyError` traceback text.
- [x] Notebook parity acceptance tests pass after placeholder cleanup and traceback-guard coverage additions.

## Evidence
- `tests/test_project029_plot_callable_first.py` now includes regression coverage for single-variable callable arg-name rebinding and `SymbolFamily` plotting-variable compatibility.
- `docs/notebooks/Toolkit_overview.ipynb` callable tutorial cells now show valid callable-first examples, use NumPy math in numeric callables, and remove stale BUG/traceback placeholders.
- `tests/test_notebook_documentation_quality.py` now validates both (a) placeholder BUG marker absence and (b) absence of captured issue-023 missing-`x` traceback text.

## TODO
- [x] Reproduce the failure with a deterministic regression test.
- [x] Implement callable normalization fix and assert expected behavior in tests, including notebook `SymbolFamily("x")` usage.
- [x] Replace notebook traceback/BUG placeholder with working runnable example text and code.
- [x] Re-run notebook documentation quality tests after notebook cleanup.
- [ ] External reviewer sign-off.

## Exit criteria
- [x] Callable plotting tutorial path in notebook runs without `KeyError` tracebacks in published content.
- [x] Automated tests cover callable-first render/re-render behavior and notebook quality gates.
- [ ] External review confirms closeout readiness.
