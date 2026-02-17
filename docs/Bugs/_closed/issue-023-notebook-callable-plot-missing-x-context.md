# Issue 023: Example notebook callable plot raises missing `x` parameter context KeyError

## Status
Closed

## Summary
State-of-completion checklist:
- [x] Deterministic regression tests exist for callable arg-name mismatch and explicit `vars=(x, a)` rebinding.
- [x] Callable normalization handles explicit `vars=` rebinding and single-variable implicit rebinding (including `SymbolFamily` plot symbols).
- [x] Project-level callable-first test suite covers single-variable and multi-variable callable plotting paths.
- [x] Example notebook callable walkthrough uses runnable content and does not include captured `KeyError` traceback text.
- [x] Documentation is aligned with runtime behavior for this issue path.

## Evidence
- `tests/test_project029_plot_callable_first.py` includes coverage for callable rebinding, single-variable callable behavior, and `SymbolFamily` plotting-variable compatibility.
- `docs/notebooks/Toolkit_overview.ipynb` callable tutorial cells show runnable callable-first examples and do not include issue-023 traceback placeholders.

## TODO
- [x] Reproduce the failure with a deterministic regression test.
- [x] Implement callable normalization fix and assert expected behavior in tests.
- [x] Replace notebook traceback/BUG placeholder with working runnable content.
- [x] Validate closeout state against current code and notebook docs.

## Exit criteria
- [x] Callable plotting tutorial path in notebook runs without `KeyError` tracebacks in published content.
- [x] Automated tests cover callable-first render/re-render behavior.
- [x] Notebook content is aligned with implemented callable behavior.
