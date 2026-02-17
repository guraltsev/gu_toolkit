# Issue 025: Example notebook flags code-generation API contract and emitted-code mismatches

## Status
Open

## Summary
The example notebook identifies several code-generation contract problems:
- `fig.code` should be a read-only parameter,
- option-bearing code generation should use `fig.get_code(options)`,
- generated snippets should call `display(fig)` explicitly,
- context-generated code should place `set_title(...)` inside the `with fig:` block,
- figure display should occur immediately after figure construction.

This issue tracks aligning the codegen API and emitted snippet structure with notebook expectations.

## Evidence
- In the code generation cell (`print(fig.to_code())`) of `docs/notebooks/Toolkit_overview.ipynb`, BUG comments list the exact expected contract/format changes.

## TODO
- [ ] Review current `to_code`/code property behaviors and document current-vs-intended API.
- [ ] Implement API adjustments for `fig.code` immutability and `fig.get_code(options)` option pathway.
- [ ] Update generator templates to emit `display(fig)` and proper context ordering (`set_title` inside context).
- [ ] Add snapshot-style regression tests for emitted code text and API shape.
- [ ] Add notebook-driven acceptance tests ensuring generated code re-executes successfully.

## Exit criteria
- Code generation API matches the notebook contract.
- Generated code ordering/structure is validated by automated snapshot or golden-file tests.
- Notebook BUG comments for codegen can be removed.
