# Issue 052: The MathLive showcase mixed browser-driven demos with kernel-side regression cells and reused the same widgets across sections

## Status
Closed (2026-04-04)

## Summary
The showcase notebook used the same widget instances for both reader-facing demos and later regression assertions. It also relied on kernel-side trait mutation as though that were evidence of browser interactivity, which blurred the difference between manual frontend edits and automated backend checks.

That made the notebook harder to trust pedagogically: the reader-facing demo looked interactive, but the verification path mutated the same object later and therefore risked teaching the wrong mental model.

## Evidence
- The identifier section reused `identifier_widget` for both the visible tutorial cell and the later regression cell.
- The expression MathJSON section reused `expression_widget` from the earlier text-based section instead of constructing a fresh transport-test widget.
- There was no explicit live-frontend example showing browser-side injection/event dispatch, even though the notebook commentary was complaining about that distinction.
- The updated notebook now:
  - keeps `identifier_widget` as the visible demo widget,
  - adds an optional JavaScript injection cell for live frontends,
  - uses a fresh `identifier_regression_widget` for kernel-side checks, and
  - uses a fresh `expression_mathjson_widget` for the MathJSON regression.
- `tests/semantic_math/test_showcase_notebooks.py` now checks that the manual demo, optional JavaScript cell, feedback cell, and regression cells remain structurally separated.

## TODO / Approach to solution
- [x] Separate browser-facing manual exploration from backend regression coverage.
- [x] Add an optional JavaScript injection cell that drives the visible identifier demo widget in live notebook frontends.
- [x] Use fresh widgets for the identifier and expression regression sections.
- [x] Explain explicitly that the regression path is kernel-side and should not mutate the earlier teaching widgets.
- [x] Add notebook-structure tests protecting the split.

## Exit criteria
- [x] The visible demo cells and the regression cells no longer share the same widget instances.
- [x] The notebook contains a clear browser-side interaction path for live frontends.
- [x] The MathJSON regression section no longer mutates `expression_widget` from the earlier teaching section.
- [x] Structural notebook tests protect the separation.
