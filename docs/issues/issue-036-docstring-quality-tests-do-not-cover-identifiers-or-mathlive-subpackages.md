# Issue 036: Docstring regression tests do not cover the `identifiers` or `mathlive` subpackages

## Status
Open

## Summary
The repository has a docstring-structure test, but it only scans top-level modules in `src/gu_toolkit/*.py`. The semantic-math APIs with the weakest docstrings live in subpackages (`src/gu_toolkit/identifiers/` and `src/gu_toolkit/mathlive/`), so the current regression test gives false confidence.

This explains how the placeholder-heavy semantic-math docstrings can exist while the docstring test suite still passes.

## Evidence
- `tests/test_public_api_docstrings.py:33-42` iterates over `SRC_ROOT.glob('*.py')`, not a recursive glob, so nested packages are skipped entirely.
- The same file enforces only heading presence, not content quality (`tests/test_public_api_docstrings.py:40-49`).
- The poor docstrings called out in the notebook live under:
  - `src/gu_toolkit/identifiers/policy.py`
  - `src/gu_toolkit/mathlive/context.py`
  - `src/gu_toolkit/mathlive/transport.py`
  - `src/gu_toolkit/mathlive/inputs.py`
- Local run during analysis:
  - `pytest tests/test_public_api_docstrings.py -q`
  - result: `2 passed`
- That passing result coexists with the clearly placeholder semantic-math docstrings described in Issue 035.

## TODO / Approach to solution
- Make the docstring test recursive (`rglob('*.py')`) or explicitly include public subpackages.
- Extend the test so it catches obvious placeholder content, not just section headers.
- Add at least one semantic-math-specific docstring regression test for a few representative APIs (`symbol`, `ExpressionContext`, `IdentifierInput`, `ExpressionInput`).

## Exit criteria
- The docstring regression suite visits public modules in `src/gu_toolkit/identifiers/` and `src/gu_toolkit/mathlive/`.
- The current placeholder semantic-math docstrings would fail the strengthened test suite.
- After documentation fixes, the tests pass and protect the semantic-math package from regressing back to heading-only boilerplate.
