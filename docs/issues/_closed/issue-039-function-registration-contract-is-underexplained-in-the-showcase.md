# Issue 039: The function-registration contract is underexplained in the showcase notebook

## Status
Closed (2026-04-04)

## Summary
The showcase now explains why `ExpressionContext` tracks symbols and functions separately, what `include_named_functions=False` means, and when `from_expression(...)`, `register_symbol(...)`, or `register_function(...)` are the better construction paths.

This was fixed together with the overlapping function-registration report in issue 046.

## Evidence
- `examples/MathLive_identifier_system_showcase.ipynb` now states that `ctx.symbols` holds atomic names while `ctx.functions` holds callable heads, and it explains why `from_symbols(..., functions=[...])` asks for both categories.
- The same notebook now explains that `include_named_functions=False` keeps the tutorial scoped to the explicitly registered names instead of silently importing the whole `NamedFunction` registry.
- `src/gu_toolkit/mathlive/context.py` now gives `ExpressionContext.from_symbols()` a substantive docstring covering separate symbol/function tracking, `include_named_functions`, `from_expression(...)`, `register_symbol(...)`, and `register_function(...)`.
- `docs/guides/api-discovery.md` and `docs/guides/semantic-math-refactoring-philosophy.md` now include semantic-math orientation text that makes the symbol/function split discoverable outside the notebook.
- `tests/test_public_api_docstrings.py` now asserts that the relevant docstrings explain these authoring boundaries.
- Verified with `PYTHONPATH=src pytest tests/semantic_math -q tests/test_public_api_docstrings.py -q`.

## TODO
- [x] Explain why symbols and callable heads are distinct semantic categories.
- [x] Explain what `include_named_functions` does in practical terms.
- [x] Mention the alternative APIs (`from_expression(...)`, `register_symbol(...)`, `register_function(...)`).
- [x] Add regression coverage so the explanation remains part of the public docs.

## Exit criteria
- [x] A reader can explain why functions are registered separately from symbols.
- [x] The role of `include_named_functions` is clear without reading source.
- [x] The tutorial's chosen construction path now reads as intentional rather than arbitrary.
