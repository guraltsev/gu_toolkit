# Issue 036: Docstring regression tests do not cover the `identifiers` or `mathlive` subpackages

## Status
Closed (2026-04-03)

## Summary
The public-docstring regression suite now scans the full `src/gu_toolkit/` tree recursively, including the semantic-math subpackages. The suite was also strengthened with semantic-math-specific quality checks so heading-only boilerplate no longer passes for representative APIs.

## Evidence
- `tests/test_public_api_docstrings.py` now uses a recursive source-file iterator instead of limiting coverage to `src/gu_toolkit/*.py`.
- The same test module asserts that the recursive scan reaches `src/gu_toolkit/identifiers/policy.py` and the `src/gu_toolkit/mathlive/` modules.
- Representative semantic-math APIs (`symbol()`, `ExpressionContext`, `ExpressionContext.transport_manifest()`, `build_mathlive_transport_manifest()`, `IdentifierInput`, and `ExpressionInput`) now have dedicated regression checks that fail on placeholder phrases and missing semantic-math navigation links.
- Verified with `PYTHONPATH=src pytest tests/test_public_api_docstrings.py -q` and with the focused semantic-math slice `PYTHONPATH=src pytest tests/test_public_api_docstrings.py tests/semantic_math/test_identifier_policy.py tests/semantic_math/test_expression_context.py tests/semantic_math/test_mathlive_inputs.py tests/semantic_math/test_symbolic_identifier_families.py -q`.

## TODO
- [x] Make the docstring scan recursive so nested public modules are visited.
- [x] Extend the suite so obvious placeholder content is rejected for semantic-math representative APIs.
- [x] Add semantic-math-specific regression coverage for the key identifier/context/input/transport helpers.

## Exit criteria
- [x] The docstring regression suite visits public modules in `src/gu_toolkit/identifiers/` and `src/gu_toolkit/mathlive/`.
- [x] The previous placeholder semantic-math docstrings would fail the strengthened test suite.
- [x] After the documentation fixes, the tests pass and protect the semantic-math package from regressing back to heading-only boilerplate.
