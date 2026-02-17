# Issue 025: Example notebook flags code-generation API contract and emitted-code mismatches

## Status
Open

## Summary
State-of-completion checklist:
- [x] `Figure.code` read-only property is implemented and tested.
- [x] `Figure.get_code(options)` API path is implemented and tested.
- [x] Generated code structure (`display(fig)`, context ordering) is covered by snapshot tests.
- [ ] Notebook code-generation section still contains multiple `#BUG` placeholders describing unresolved guidance/contract details.
- [ ] Notebook-driven acceptance tests that execute generated snippets are not yet present.

## Evidence
- `tests/test_figure_snapshot_codegen.py` covers read-only `code`, `get_code(options)`, and output structure.
- `docs/notebooks/Toolkit_overview.ipynb` still includes `#BUG` comments in the code-generation cell.
- Notebook documentation quality test fails while these placeholders remain.

## TODO
- [x] Review current `to_code`/code property behaviors and document current-vs-intended API.
- [x] Implement API adjustments for `fig.code` immutability and `fig.get_code(options)` option pathway.
- [x] Update generator templates to emit `display(fig)` and proper context ordering (`set_title` inside context).
- [x] Add snapshot-style regression tests for emitted code text and API shape.
- [ ] Replace notebook BUG placeholders in code-generation section with finalized user guidance.
- [ ] Add notebook-driven acceptance tests ensuring generated code re-executes successfully.

## Exit criteria
- [ ] Code generation API matches notebook contract and notebook examples are clean (no placeholder BUG markers).
- [ ] Generated code ordering/structure remains validated by automated tests.
- [ ] Notebook BUG comments for codegen can be removed.
