# Issue 046: The tutorial underexplains why function names are registered separately and what `include_named_functions` means

## Status
Closed (2026-04-04)

## Summary
The tutorial and docs now explain the semantic contract directly: symbols are atomic names, functions are callable heads, and the context tracks them separately on purpose. The docs now also explain `include_named_functions` and point readers to the alternative construction APIs when explicit `functions=[...]` is not the right choice.

This was fixed together with the overlapping function-registration report in issue 039.

## Evidence
- `examples/MathLive_identifier_system_showcase.ipynb` now explains why `ctx.symbols` and `ctx.functions` are separate registries and what `include_named_functions=False` means in the tutorial.
- `src/gu_toolkit/mathlive/context.py` now gives `ExpressionContext.from_symbols()` an architecture-focused docstring covering explicit function registration, `from_expression(...)`, `register_symbol(...)`, and `register_function(...)`.
- `docs/guides/api-discovery.md` and `docs/guides/semantic-math-refactoring-philosophy.md` now reinforce the same symbol/function boundary.
- `tests/test_public_api_docstrings.py` now checks that the relevant docstrings keep mentioning the separate registries and alternative APIs.
- Verified with `PYTHONPATH=src pytest tests/semantic_math -q tests/test_public_api_docstrings.py -q`.

## TODO
- [x] Explain why functions are registered separately from symbols.
- [x] Clarify the role of `include_named_functions`.
- [x] Mention the alternative construction paths for readers with different workflows.
- [x] Protect the explanation with docstring/guide regression checks.

## Exit criteria
- [x] Readers can explain the separate symbol/function registries without source diving.
- [x] `include_named_functions` is understandable from the public tutorial/docs.
- [x] The explicit `functions=[...]` constructor path now has a clear justification.
