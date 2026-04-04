# Issue 047: The `IdentifierInput` section conflates interactive teaching, hidden assertions, and programmatic mutation

## Status
Closed (2026-04-04)

## Summary
The `IdentifierInput` tutorial flow now separates the visible manual workflow from the automated integration mutation/assertions. Readers first see the widget and the parsed canonical identifier, then a later cell performs the programmatic MathJSON injection used for notebook regression coverage.

This was fixed together with the overlapping notebook-demo report in issue 040.

## Evidence
- `examples/MathLive_identifier_system_showcase.ipynb` now contains a dedicated manual widget cell, a visible feedback cell, and a later regression cell instead of one overloaded hybrid cell.
- The visible output now tells the reader what canonical identifier was parsed.
- `tests/semantic_math/test_showcase_notebooks.py` now asserts that the manual display cell, visible feedback cell, and regression cell remain separate and ordered.
- The notebook still executes successfully under `NotebookClient`, so the refactor preserved its integration value.
- Verified with `PYTHONPATH=src pytest tests/semantic_math -q tests/test_public_api_docstrings.py -q`.

## TODO
- [x] Keep the manual workflow visible and easy to follow.
- [x] Surface the parsed canonical identifier explicitly.
- [x] Move the hidden mutation/assertion path into a separate regression cell.
- [x] Guard the split with a structural notebook test.

## Exit criteria
- [x] The manual `IdentifierInput` demo is understandable without reading source.
- [x] Parsed output is visible in notebook output.
- [x] Regression assertions remain, but they no longer overwhelm the teaching narrative.
