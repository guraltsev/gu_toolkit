# Issue 042: The toolkit `symbol()` helper is underdocumented relative to SymPy

## Status
Closed (2026-04-04)

## Summary
The toolkit's `symbol()` helper is now documented explicitly as a thin wrapper around `sympy.Symbol(...)` that validates canonical identifiers, optionally stores display-LaTeX metadata, and forwards normal SymPy assumptions. The notebook and guides now also explain when to choose `symbol()`, `sympy.Symbol(...)`, or `sympy.symbols(...)`.

No implementation move was needed: `symbol()` was already in the correct place (`src/gu_toolkit/identifiers/policy.py`) and exposed through `gu_toolkit.identifiers`.

## Evidence
- `src/gu_toolkit/identifiers/policy.py` now gives `symbol()` a substantive docstring that compares it directly with `sympy.Symbol(...)` and `sympy.symbols(...)` and explains the toolkit-specific validation/metadata behavior.
- `examples/MathLive_identifier_system_showcase.ipynb` now introduces `symbol(...)` as a thin wrapper around `sp.Symbol(...)` and explains when each constructor style is appropriate.
- `docs/guides/api-discovery.md` and `docs/guides/semantic-math-refactoring-philosophy.md` now include semantic-math orientation text covering `symbol()` vs raw SymPy constructors.
- `tests/test_public_api_docstrings.py` now asserts that the `symbol()` docstring names `sympy.Symbol` and `sympy.symbols` and explains the wrapper boundary.
- Verified with `PYTHONPATH=src pytest tests/semantic_math -q tests/test_public_api_docstrings.py -q`.

## TODO
- [x] Document `symbol()` as a wrapper around `sympy.Symbol(...)`.
- [x] Explain the added toolkit behavior: canonical validation and optional LaTeX metadata.
- [x] Compare `symbol()` directly with `sympy.Symbol(...)` and `sympy.symbols(...)`.
- [x] Confirm that the implementation already lives in the correct identifier-policy module.

## Exit criteria
- [x] Users can tell when to use `symbol()`, `sympy.Symbol(...)`, and `sympy.symbols(...)`.
- [x] The extra behavior provided by `symbol()` is documented clearly.
- [x] The helper is documented where it is implemented and where readers first encounter it.
