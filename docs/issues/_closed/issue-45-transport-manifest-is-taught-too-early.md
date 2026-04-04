# Issue 045: The showcase teaches the low-level transport manifest before the user-facing workflow

## Status
Closed (2026-04-04)

## Summary
The tutorial order has been reversed to be showcase-first instead of transport-first. Readers now see the working semantic context and widget workflow before they ever inspect the low-level manifest, and the manifest section now carries an explicit schema note so the browser contract is easier to place architecturally.

This was fixed together with the overlapping transport-ordering report in issue 038.

## Evidence
- `examples/MathLive_identifier_system_showcase.ipynb` now demonstrates `IdentifierInput` and `ExpressionInput` before the `transport_manifest()` code cell.
- The manifest section is now introduced as a later debugging/transport view and documents `version`, `fieldRole`, `symbols`, `functions`, `latexHead`, and `template`.
- `tests/semantic_math/test_showcase_notebooks.py` now asserts that widget code cells come before the manifest code cell.
- `src/gu_toolkit/mathlive/context.py` and `src/gu_toolkit/mathlive/transport.py` now describe the manifest as a derived frontend contract rather than as the primary authoring API.
- Verified with `PYTHONPATH=src pytest tests/semantic_math -q tests/test_public_api_docstrings.py -q`.

## TODO
- [x] Move the manifest inspection after the successful user-facing workflow.
- [x] Label the manifest as a low-level derived frontend artifact.
- [x] Add the minimal schema needed for notebook readers.
- [x] Guard the tutorial order with a regression test.

## Exit criteria
- [x] The first successful widget workflow appears before any raw manifest inspection.
- [x] The manifest is taught as an implementation boundary, not as the starting mental model.
- [x] The tutorial now feels showcase-first instead of backend-first.
