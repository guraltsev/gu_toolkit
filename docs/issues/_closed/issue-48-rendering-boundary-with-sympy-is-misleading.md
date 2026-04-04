# Issue 048: The rendering example obscures that SymPy is the actual LaTeX printer of record

## Status
Closed (2026-04-04)

## Summary
The rendering boundary is now documented explicitly: `ctx.render_latex(...)` / `render_latex(...)` remain convenience wrappers, but SymPy is still the printer of record. The notebook now shows the equivalent `sp.latex(..., symbol_names=ctx.symbol_name_map(...))` call, and the public docstrings/guides now describe the wrapper layering directly.

## Evidence
- `examples/MathLive_identifier_system_showcase.ipynb` now says that `ctx.render_latex(...)` is a convenience wrapper around SymPy's own printer and shows the matching `sp.latex(...)` call.
- `src/gu_toolkit/mathlive/context.py` now describes `ExpressionContext.render_latex()` as a convenience wrapper that delegates into `gu_toolkit.identifiers.render_latex(...)` and ultimately `sympy.latex(...)`.
- `docs/guides/api-discovery.md` and `docs/guides/semantic-math-refactoring-philosophy.md` now reinforce the same rendering boundary.
- `tests/semantic_math/test_expression_context.py` now asserts that `ctx.render_latex(expr)` matches `sp.latex(expr, symbol_names=ctx.symbol_name_map(expr))` for a representative semantic expression.
- `tests/semantic_math/test_showcase_notebooks.py` now checks that the notebook keeps the “SymPy is still the printer of record” explanation.
- Verified with `PYTHONPATH=src pytest tests/semantic_math -q tests/test_public_api_docstrings.py -q`.

## TODO
- [x] Explain in the notebook that SymPy performs the final LaTeX printing.
- [x] Document the wrapper relationship in the public docstrings/guides.
- [x] Show a concrete `sp.latex(...)` equivalence example.
- [x] Add regression coverage for the rendering boundary.

## Exit criteria
- [x] Readers can tell that SymPy is the actual printer.
- [x] The purpose of the toolkit rendering helpers is described as metadata/convenience wiring.
- [x] The notebook no longer suggests that there is a competing custom LaTeX engine.
