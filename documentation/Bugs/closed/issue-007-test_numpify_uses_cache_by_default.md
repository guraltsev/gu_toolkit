# Issue 007: `import gu_toolkit.numpify as numpify_module` resolves to function object

## Summary
`tests/test_numpify_cache_behavior.py::test_numpify_uses_cache_by_default` failed with `AttributeError: 'function' object has no attribute 'numpify_cached'` because `import gu_toolkit.numpify as numpify_module` bound to the package-level `numpify` function export instead of the `gu_toolkit.numpify` submodule.

## Root cause
- `__init__.py` re-exported the `numpify` callable as `gu_toolkit.numpify`.
- That package attribute name collides with the submodule name `gu_toolkit.numpify`.
- In this import form (`import gu_toolkit.numpify as ...`), the attribute collision caused code to receive the function object rather than the module object expected by tests.

## Implemented fix
- Renamed the top-level re-export from `numpify` to `numpify_expr` in `__init__.py`.
- Kept `numpify_cached` and related numpify symbols exported.
- This removes the top-level name collision so `import gu_toolkit.numpify as numpify_module` resolves to the actual submodule.

## Validation
- Test execution in this environment is currently blocked by missing dependency `sympy`, so full pytest confirmation could not be completed here.
- The namespace collision has been removed in package exports, which addresses the observed failure mechanism.

## Disposition
**Fixed in package namespace exports by avoiding submodule-name shadowing.**


## Closure note (2026-02-14)
Closed because the namespace-shadowing regression is no longer present: `tests/test_numpify_cache_behavior.py::test_numpify_uses_cache_by_default` passed in the provided run.
