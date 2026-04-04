# Issue 038: The notebook introduces the low-level transport manifest too early and without a schema

## Status
Closed (2026-04-04)

## Summary
The MathLive showcase now teaches the Python-side semantic model and the working widget flow before it inspects `transport_manifest()`. The manifest section was moved later in the notebook, explicitly labeled as a derived frontend snapshot, and given a small schema description so readers are not forced to reverse-engineer keys such as `fieldRole`, `latexHead`, and `template`.

This was fixed together with the overlapping transport-ordering report in issue 045.

## Evidence
- `examples/MathLive_identifier_system_showcase.ipynb` now introduces `symbol(...)`, `ExpressionContext`, `IdentifierInput`, and `ExpressionInput` before the manifest inspection section.
- The manifest section now explains the small schema readers actually need: top-level `version`, `fieldRole`, `symbols`, `functions`, plus function-entry keys `latexHead` and `template`.
- `src/gu_toolkit/mathlive/context.py` and `src/gu_toolkit/mathlive/transport.py` now describe `transport_manifest()` / `build_mathlive_transport_manifest()` as derived frontend transport contracts rather than primary Python authoring APIs.
- `tests/semantic_math/test_showcase_notebooks.py` now asserts that working widget code cells appear before the manifest code cell and that the notebook documents the key manifest fields.
- Verified with `PYTHONPATH=src pytest tests/semantic_math -q tests/test_public_api_docstrings.py -q`.

## TODO
- [x] Reorder the notebook so the user-facing model appears before raw transport dicts.
- [x] Move manifest inspection later in the notebook.
- [x] Document the minimal schema needed for `fieldRole`, `latexHead`, and `template`.
- [x] Add regression coverage so the tutorial stays workflow-first.

## Exit criteria
- [x] Readers see the conceptual model and working widgets before raw transport payloads.
- [x] The manifest is labeled as a derived frontend snapshot rather than as the main Python interface.
- [x] `fieldRole`, `latexHead`, and `template` are explained when they are shown.
