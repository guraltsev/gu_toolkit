# Issue 041: Semantic-math cross-references point to generic or missing navigation targets

## Status
Closed (2026-04-03)

## Summary
The semantic-math navigation path is now explicit. Semantic-math docstrings point readers to the API-discovery guide’s new semantic-math row, the dedicated semantic-math guide, the MathLive showcase notebook, and focused semantic-math tests instead of generic Toolkit-overview references.

## Evidence
- `docs/guides/api-discovery.md` now includes a task-map row for “Author semantic identifiers and MathLive-backed expressions” that names `symbol`, `ExpressionContext`, `IdentifierInput`, `ExpressionInput`, `mathjson_to_identifier`, and `build_mathlive_transport_manifest`.
- The same guide now includes a `**Semantic math / MathLive**` module-family entry covering `identifiers/policy.py`, `mathlive/context.py`, `mathlive/transport.py`, `mathlive/inputs.py`, and `mathlive/widget.py`.
- Representative semantic-math docstrings in `src/gu_toolkit/identifiers/policy.py`, `src/gu_toolkit/mathlive/context.py`, `src/gu_toolkit/mathlive/transport.py`, and `src/gu_toolkit/mathlive/inputs.py` now point to:
  - `docs/guides/api-discovery.md`
  - `docs/guides/semantic-math-refactoring-philosophy.md`
  - `examples/MathLive_identifier_system_showcase.ipynb`
  - focused tests under `tests/semantic_math/`
- `examples/Toolkit_overview.ipynb` is no longer used as the semantic-math docstrings’ primary navigation target.
- `tests/test_public_api_docstrings.py` now includes a regression test that checks the semantic-math API-discovery entry.

## TODO
- [x] Add a semantic-math / MathLive row to `docs/guides/api-discovery.md`.
- [x] Update semantic-math docstrings so their primary “Learn more” links point to the semantic-math guide, dedicated showcase notebook, and focused tests.
- [x] Remove generic Toolkit-overview cross-references from the semantic-math docstrings.
- [x] Add regression coverage so the navigation path stays intact.

## Exit criteria
- [x] `help(symbol)`, `help(ExpressionContext)`, `help(IdentifierInput)`, and `help(ExpressionInput)` point users toward the semantic-math guide and showcase notebook.
- [x] `docs/guides/api-discovery.md` contains a semantic-math / MathLive entry.
- [x] The repository’s “Learn more / explore” links now form a real navigation path rather than a dead end.
