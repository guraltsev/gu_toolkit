# Issue 011: `NReal_Fourier_Series` rejects constant Python numeric expressions

## Summary
`tests/test_prelude_nintegrate.py::test_nreal_fourier_series_constant_l2_normalized` fails with `TypeError: Unsupported expr type for NIntegrate: <class 'int'>` when input expression is `1`.

## Analysis
- `NReal_Fourier_Series` delegates callable construction to `_resolve_numeric_callable`.
- `_resolve_numeric_callable` supports `sp.Basic`, `sp.Lambda`, callable, and numpified functions, but not plain Python numeric scalars (`int`, `float`).
- Constant signals are natural use-cases for Fourier decomposition, so rejecting numeric literals is overly strict.

## Proposed solution
- Accept scalar numeric inputs by sympifying early (e.g., `expr = sp.sympify(expr)` for non-callables) or explicitly branch for `numbers.Real`.
- Ensure scalar evaluation returns vectorized output (`np.full_like`) over sample grid.
- Add regression tests for `expr=1` and `expr=2.5`.

## Disposition
**Real bug / missing ergonomic support.**
