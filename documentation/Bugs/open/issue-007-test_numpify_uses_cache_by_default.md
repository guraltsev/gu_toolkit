# Issue 002: `import gu_toolkit.numpify as numpify_module` resolves to function object

## Summary
`tests/test_numpify_cache_behavior.py::test_numpify_uses_cache_by_default` fails with `AttributeError: 'function' object has no attribute 'numpify_cached'` because `numpify_module` resolves to a function instead of the `gu_toolkit.numpify` module.

## Analysis
- The test imports `gu_toolkit.numpify as numpify_module` and expects module attributes (`numpify_cached`, `numpify`).
- Package `__init__.py` re-exports `numpify` as a top-level attribute named `numpify`, which shadows the submodule name in this import style.
- As a result, `numpify_module` may bind to the function export rather than the submodule object.

## Proposed solution
- **Recommended (bug fix):** Avoid shadowing the submodule name at package top level.
  - Option A: keep `numpify` function export but ensure `gu_toolkit.numpify` module remains addressable via explicit module binding patterns.
  - Option B: rename top-level function export alias (for example `numpify_expr`) and keep submodule namespace clean.
- As short-term test workaround, import via `import importlib; numpify_module = importlib.import_module("gu_toolkit.numpify")`.

## Disposition
**Bug in package namespace ergonomics; current tests are reasonable.**
