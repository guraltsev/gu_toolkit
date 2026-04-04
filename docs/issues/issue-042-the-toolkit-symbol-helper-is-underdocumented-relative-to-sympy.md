# Issue 042: The toolkit `symbol()` helper is underdocumented relative to SymPy

## Status
Open

## Summary
The notebook imports `sympy as sp` and `symbol` from `gu_toolkit.identifiers` side by side, but it never explains why the toolkit helper exists or how it differs from raw SymPy constructors. The implementation shows that `symbol()` is a validated wrapper around `sp.Symbol` with optional LaTeX override registration, but the docstring and guides do not say that clearly.

This leaves readers unsure whether they should use `symbol`, `sp.Symbol`, or `sp.symbols`, and what extra behavior the toolkit helper adds.

Furthermore, check that the toolkit exposes symbols. If it is defined in the wrong place, move its implementation to the correct place. THAT is a  convenience method that REPLACES sp.symbols and maintains API compatibility, except it does checking of symbol validity. Document this! 

## Evidence
- Notebook cell 6 contains a review note questioning whether `symbol` is overriding a SymPy callable and asking for explicit documentation.
- `src/gu_toolkit/identifiers/policy.py:525-566` shows the actual behavior:
  - validate the canonical identifier name,
  - optionally register `latex_expr`,
  - then return `sp.Symbol(canonical, **kwargs)`.
- The current `symbol` docstring does not explain any of that; it is the same placeholder pattern called out elsewhere.
- Local environment check during analysis:
  - `hasattr(sympy, "symbol") == False`
  - `sp.Symbol` exists
  - `sp.symbols` exists
  This suggests the real confusion is not a literal top-level override, but poor explanation of the toolkit helper’s relationship to SymPy.
- `docs/guides/api-discovery.md` includes a row for `symbols` / `SymbolFamily` helpers (`line 61`) but does not document the single-symbol toolkit helper `symbol`.
- A repo-wide documentation search during analysis did not find a user-facing guide section explaining when to prefer toolkit `symbol()` over raw SymPy constructors.

## TODO / Approach to solution
- Document `symbol()` explicitly as a thin wrapper around `sp.Symbol` that adds:
  - canonical identifier validation,
  - optional LaTeX override registration,
  - and pass-through SymPy assumptions via `**kwargs`.
- Compare it directly with `sp.Symbol` and `sp.symbols`.
- Add that explanation to both:
  - the `symbol` docstring,
  - and at least one discoverability guide / example notebook.
- Link to the relevant SymPy constructor docs or, at minimum, name the SymPy equivalents in the docstring.

## Exit criteria
- A user reading `help(symbol)` can tell when to use `symbol`, `sp.Symbol`, or `sp.symbols`.
- The notebook no longer leaves the import relationship ambiguous.
- The semantic-math docs explain the extra behavior that the toolkit helper adds on top of raw SymPy symbol creation.
