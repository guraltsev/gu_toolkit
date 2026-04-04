# Issue 044: The notebook calls an unsupported `get_state()` method and fails in the repo's own execution environment

## Status
Closed (2026-04-04)

## Summary
The unsupported `identifier_widget.get_state()` call was removed from the showcase notebook. The tutorial now inspects supported public widget traits instead (`value`, `math_json`, `transport_valid`, and `transport_errors`), so the notebook executes in the repo's fallback widget runtime as shipped.

## Evidence
- `examples/MathLive_identifier_system_showcase.ipynb` no longer calls `.get_state()`.
- The replacement notebook cell now uses supported public state that exists in the fallback anywidget-backed runtime.
- `tests/semantic_math/test_showcase_notebooks.py` now explicitly asserts that `.get_state(` does not appear in the notebook source.
- The notebook execution test under `NotebookClient` now passes again.
- Verified with `PYTHONPATH=src pytest tests/semantic_math -q tests/test_public_api_docstrings.py -q`.

## TODO
- [x] Remove the unsupported `get_state()` call from the tutorial.
- [x] Replace it with supported public-trait inspection.
- [x] Keep notebook examples aligned with the fallback runtime used by tests.
- [x] Add regression coverage so `.get_state()` does not return accidentally.

## Exit criteria
- [x] The showcase notebook executes successfully in the repo's own environment.
- [x] State inspection uses supported public APIs only.
- [x] `.get_state()` is no longer part of the published tutorial path.
