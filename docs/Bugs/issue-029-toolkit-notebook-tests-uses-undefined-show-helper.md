# Issue 029: `Toolkit_notebook_tests.ipynb` calls undefined `show()` helper in B3 render check

## Status
Open

## Summary
Assessment (2026-02-17): implementation is partially complete; coverage and/or documentation gaps listed below keep this issue open.

State-of-completion checklist:
- [ ] Notebook test section **B3** still calls `show()` inside `with fig_gui:` and raises `NameError`.
- [ ] Public notebook namespace exports `render()` but not `show()`, so the B3 snippet is currently not executable as written.
- [ ] No automated regression test currently validates the notebook's B3 render snippet against the exported API surface.

## Evidence
- `docs/notebooks/Toolkit_notebook_tests.ipynb` includes B3 code that executes `show()` and a preserved `NameError` traceback block.
- `__init__.py` re-exports notebook helpers including `render`, but does not export a `show` helper.
- `Figure.py` and `notebook_namespace.py` do not define a top-level `show()` helper callable for context-managed use.

## TODO
- [ ] Decide the intended public API contract for notebook rendering in examples:
  - either replace notebook calls with supported API (for example `render()` or explicit figure display flow),
  - or implement and document a first-class `show()` helper.
- [ ] Update `docs/notebooks/Toolkit_notebook_tests.ipynb` B3 to remove the stale traceback block and use the chosen supported API.
- [ ] Add regression coverage for this notebook bug in a dedicated notebook-quality test suite:
  - add a test that parses notebook code cells and fails if unsupported helper names (like bare `show()`) are used,
  - add a test that executes (or statically validates) B3 snippet semantics against exported notebook helpers,
  - ensure the new tests run in CI with the rest of notebook quality checks.
- [ ] Document the canonical render/display helper in notebook docs so future examples stay consistent.

## Exit criteria
- [ ] B3 cell executes without `NameError` on a clean notebook run.
- [ ] Notebook no longer contains embedded traceback placeholders for this scenario.
- [ ] Automated notebook regression tests fail on unsupported helpers and pass for the corrected snippet.
