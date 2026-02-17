# Issue 025: Example notebook flags code-generation API contract and emitted-code mismatches

## Status
Ready for external review

## Summary
The example notebook identified several code-generation contract problems:
- `fig.code` should be a read-only property,
- option-bearing code generation should use `fig.get_code(options)`,
- generated snippets should call `display(fig)` explicitly,
- context-generated code should place `set_title(...)` inside the `with fig:` block,
- figure display should occur immediately after figure construction.

This issue tracks aligning the codegen API and emitted snippet structure with notebook expectations.

## Evidence
- In the code generation cell (`print(fig.to_code())`) of `docs/notebooks/Toolkit_overview.ipynb`, BUG comments list the expected contract/format changes.
- `Figure.to_code()` existed, but there was no `fig.code` property and no `fig.get_code(options)` helper.
- Generated code previously ended with `fig` expression display instead of explicit `display(fig)`, and title emission for context-mode code was outside `with fig:`.

## Remediation plan
- Add a read-only `Figure.code` property that delegates to `to_code()`.
- Add `Figure.get_code(options)` as the option-bearing convenience API.
- Update code generation imports/output so emitted scripts use explicit `display(fig)` and include `set_title(...)` within `with fig:` for context-manager style.
- Add/expand regression tests for API shape and generated-code structure.

## TODO
- [x] Review current `to_code`/code property behaviors and document current-vs-intended API.
- [x] Implement API adjustments for `fig.code` immutability and `fig.get_code(options)` option pathway.
- [x] Update generator templates to emit `display(fig)` and proper context ordering (`set_title` inside context).
- [x] Add snapshot-style regression tests for emitted code text and API shape.
- [ ] Add notebook-driven acceptance tests ensuring generated code re-executes successfully.

## Exit criteria
- Code generation API matches the notebook contract.
- Generated code ordering/structure is validated by automated snapshot or golden-file tests.
- Notebook BUG comments for codegen can be removed.
