# Issue: The rendering example obscures that SymPy is the actual LaTeX printer of record

## Summary
The notebook and API surface foreground `ctx.render_latex()` / `render_latex()` as if the toolkit owns a distinct LaTeX rendering engine. In the current implementation, those helpers are thin wrappers around `sympy.latex(...)` plus semantic symbol/function metadata.

That layering is not necessarily wrong, but the tutorial currently teaches it in a way that makes the rendering boundary easy to misunderstand. This is the architectural confusion behind the `#BUG` comment in the expression section.

## Evidence
- Notebook cell 16 verifies rendering behavior using `ctx.render_latex(parsed_from_text)` and then contains a review comment arguing that rendering should be done by SymPy instead of by a custom renderer.
- `src/gu_toolkit/mathlive/context.py:841-892` shows that `ExpressionContext.render_latex()` is only a convenience wrapper around `render_latex(expr, symbol_names=self.symbol_name_map(expr))`.
- `src/gu_toolkit/identifiers/policy.py:933-942` shows that `render_latex(...)` ultimately calls `sp.latex(...)`, optionally with `symbol_names=`.
- `src/gu_toolkit/identifiers/policy.py:1051-1056` shows that semantic functions participate in printing through a SymPy `_latex` hook, so SymPy is already the printer doing the final rendering work.
- The guide `docs/guides/semantic-math-refactoring-philosophy.md` still names `render_latex()` as a public rendering helper, which reinforces the impression of a toolkit-owned rendering layer unless the tutorial explains the layering carefully.

## TODO / Approach to solution
- In the notebook, explain explicitly that SymPy is the underlying printer and that the toolkit helpers mainly provide semantic symbol/function metadata.
- Decide whether the convenience wrappers should stay public. If they do, document them as convenience wrappers rather than as a separate rendering engine.
- Prefer examples that make the layering legible, for example by showing `ctx.symbol_name_map(...)` alongside the final `sp.latex(...)` call.

## Exit criteria
- Readers can tell that SymPy performs the final LaTeX printing.
- The purpose of `ctx.render_latex()` / `render_latex()` is clearly documented as convenience and metadata wiring.
- The notebook no longer encourages the impression that there is a competing custom LaTeX engine.
