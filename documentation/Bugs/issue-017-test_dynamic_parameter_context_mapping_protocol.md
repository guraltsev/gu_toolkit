# Issue 017: Dynamic parameter contexts that are mapping-like but not iterable fail at call time

## Summary
`tests/test_numpify_refactor.py::test_dynamic_parameter_context_and_unfreeze` currently fails with:

`TypeError: argument of type '_Ctx' is not iterable`

The failure is raised from `NumericFunction.__call__` in `numpify.py` during dynamic parameter resolution.

## Analysis
- The failing path is dynamic-parameter evaluation after calling:
  - `set_parameter_context(ctx)`
  - `freeze({a: DYNAMIC_PARAMETER})`
- `ctx` in the test is a context object that supports key-based retrieval but does not implement container membership via `__contains__`/iteration.
- `NumericFunction.__call__` currently checks dynamic availability with `if sym not in self._parameter_context:`.
- That membership check assumes iterability/container semantics and raises `TypeError` for mapping-like context objects that are still valid parameter providers.

## Why this is a bug
The dynamic context API is intended to accept context providers beyond plain dictionaries (e.g., figure parameter contexts and mapping-like adapters). Requiring `in` membership support in this call path is stricter than necessary and breaks valid contexts.

## Outline of fix
1. Replace membership testing with robust lookup semantics:
   - Prefer `try: value = context[sym]` and fallback to `context[sym.name]` where appropriate.
   - Catch `KeyError` for missing values and produce the existing user-facing missing-parameter error.
2. Avoid relying on `__contains__` or iteration for context objects.
3. Add/keep regression coverage with non-iterable context providers (like `_Ctx` in the failing test).

## Disposition
**Open.** Reproducible in the provided test run and currently failing.
