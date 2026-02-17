# Issue 023: Example notebook callable plot raises missing `x` parameter context KeyError

## Status
Open

## Summary
The example notebook (`docs/notebooks/Toolkit_overview.ipynb`) includes a callable-first plotting cell that should work without manual parameter-context plumbing, but currently fails with a `KeyError` for missing symbol `x`.

This breaks a core tutorial path and makes the callable API appear unusable in basic scenarios.

## Evidence
- Notebook cell labeled "Numeric callable: damped oscillation" contains a captured traceback ending with:
  - `KeyError: "parameter_context is missing symbol x ('x')"`
- The same notebook marks the follow-up callable-with-params cell as `# BUG same as above`, indicating the failure pattern is not isolated.

## TODO
- [x] Reproduce the failure with a deterministic regression test in `tests/` (focused on `Figure.plot` + callable input with mismatched callable arg name vs plot symbol).
- [x] Define expected behavior for callable-first usage where `x` is the independent variable and must not be treated as missing dynamic parameter context.
- [x] Implement the fix in callable normalization so explicit `vars=(...)` rebinding is respected for Python callables.
- [x] Add a notebook-oriented regression test suite entry by encoding the failing notebook behavior in pytest.
- [ ] Update the example notebook once fixed to remove stale BUG comments and keep the example runnable.

## Implementation checklist
- [x] Assessed completion state and confirmed regression still reproducible from notebook traceback.
- [x] Planned remediation: rebind callable variable signature to explicit `vars=` symbols during plot input normalization.
- [x] Implemented fix in `Figure._normalize_plot_inputs`.
- [x] Added regression test coverage for callable argument-name mismatch (`lambda t, a: ...` with `vars=(x, a)`).
- [ ] External review and manual notebook validation pending before closure.

## Exit criteria
- Callable plotting in notebook-style flows executes without `KeyError` for `x`.
- Automated tests cover:
  - callable without extra params,
  - callable with explicit `vars=(x, A, k)` plus sliders,
  - render/re-render paths.
- The example notebook section is executable end-to-end without this failure.
