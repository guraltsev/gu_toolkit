# Bug 002: `parse_latex` returns ambiguous `Tree` for unparenthesized product after fraction

## Description
Notebook example `parse_latex(r"\sin(x) + \frac{1}{2}\cos(3x)")` can yield an ambiguous parse tree (`Tree('_ambig', ...)`) and later plotting fails with:
`AttributeError: 'Tree' object has no attribute 'free_symbols'`.

## Analysis
- The parser wrapper prefers SymPy `lark` backend first and returns its result directly.
- For this input, `lark` may succeed syntactically but return an ambiguous `Tree` object instead of a SymPy expression.
- Downstream plotting assumes a SymPy object (`free_symbols` access in plotting path), so the ambiguity leaks and crashes later.
- Root cause is not only expression ambiguity handling but missing post-parse type validation in `parse_latex`.

## Summary of fix
- Harden `parse_latex` to guarantee return type is SymPy expression (`sympy.Basic`), never raw parser tree.
- If `lark` output is ambiguous/non-SymPy, fallback to `antlr` automatically.
- If ambiguity remains, raise `LatexParseError` with clear actionable guidance.

## Detailed plan / blueprint
1. In `ParseLaTeX.parse_latex`:
   - Parse with lark.
   - Validate result type (`isinstance(result, sp.Basic)` or equivalent).
   - If invalid (e.g., lark tree/ambig), treat as parse failure and continue to antlr fallback.
2. Preserve explicit `backend=` behavior:
   - If user explicitly sets `backend`, do not force fallback; but still consider optional validation + clearer error.
3. Add tests:
   - Case where lark returns ambiguous tree should still produce a SymPy expression via antlr fallback.
   - Ensure downstream `plot(..., parse_latex(...))` no longer raises `free_symbols` attribute error.
4. Notebook safety update:
   - Parenthesize expression (`\sin(x) + (\frac{1}{2})\cos(3x)`) in demo text as additional robustness tip.
