# Issue 040: The `IdentifierInput` demo conflates interactive teaching with regression assertions

## Status
Closed (2026-04-04)

## Summary
The `IdentifierInput` section was split into a real manual walkthrough and a separate regression/integration cell. The visible demo now displays the widget first and then shows the current canonical identifier back to the reader, while the automated assertions live in a later cell so they no longer dominate the teaching path.

This was fixed together with the overlapping notebook-demo report in issue 047.

## Evidence
- `examples/MathLive_identifier_system_showcase.ipynb` now has a manual `IdentifierInput` display cell followed by a visible feedback cell that renders `Current canonical identifier: ...`.
- The programmatic MathJSON mutation and `assert` checks now live in a later `identifier_regression` cell, explicitly introduced as an automated integration check.
- `tests/semantic_math/test_showcase_notebooks.py` now asserts that the manual widget cell, the visible feedback cell, and the regression cell remain separate and correctly ordered.
- The notebook still executes end-to-end under `NotebookClient`, so the teaching/refactoring split did not break reproducibility.
- Verified with `PYTHONPATH=src pytest tests/semantic_math -q tests/test_public_api_docstrings.py -q`.

## TODO
- [x] Split the visible user demo from the regression assertions.
- [x] Show the parsed canonical identifier explicitly in notebook output.
- [x] Keep the integration assertions, but move them out of the main teaching cell.
- [x] Add regression coverage for the manual-vs-regression structure.

## Exit criteria
- [x] Readers can interact with the widget and see the canonical identifier that was produced.
- [x] Regression assertions remain available, but they no longer dominate the tutorial flow.
- [x] The section reads like a demo first and a hidden test second.
