# Issue 041: Semantic-math cross-references point to generic or missing navigation targets

## Status
Open

## Summary
The semantic-math APIs’ “Learn more” sections point readers to generic navigation targets that do not actually cover the semantic-math surface well. In particular, many docstrings point to `docs/guides/api-discovery.md` and `examples/Toolkit_overview.ipynb`, but the API-discovery guide has no semantic-math / MathLive entry at all, and the dedicated MathLive showcase notebook is not used as the main cross-reference.

This breaks the discoverability story that the repository’s documentation guide explicitly requires.

## Evidence
- Semantic-math docstrings repeatedly point to:
  - `docs/guides/api-discovery.md`
  - `examples/Toolkit_overview.ipynb`
  Examples:
  - `src/gu_toolkit/identifiers/policy.py:555-560`
  - `src/gu_toolkit/mathlive/context.py:249-254`
  - `src/gu_toolkit/mathlive/transport.py:278-283`
  - `src/gu_toolkit/mathlive/inputs.py:195-200`
- `docs/guides/api-discovery.md:47-63` contains the task map, but it has no entry for:
  - `ExpressionContext`
  - `IdentifierInput`
  - `ExpressionInput`
  - `MathLive`
  - `mathjson_to_identifier`
  - or the identifier helper `symbol`
- `docs/guides/public-api-documentation-structure.md:96-115` requires exact next-step links and says that new public API families should update `docs/guides/api-discovery.md`.
- A dedicated semantic-math guide already exists:
  - `docs/guides/semantic-math-refactoring-philosophy.md`
- That guide already references the dedicated showcase notebook:
  - `examples/MathLive_identifier_system_showcase.ipynb`
  - `examples/Robust_identifier_system_showcase.ipynb`
  (`docs/guides/semantic-math-refactoring-philosophy.md:104-110`)

## TODO / Approach to solution
- Add a semantic-math / MathLive row to `docs/guides/api-discovery.md`.
- Update semantic-math docstrings so their primary “Learn more” links point to:
  - the semantic-math guide,
  - the dedicated MathLive showcase notebook,
  - and the focused semantic-math tests.
- Keep `Toolkit_overview.ipynb` only as a secondary cross-reference where it is genuinely relevant.

## Exit criteria
- `help(symbol)`, `help(ExpressionContext)`, `help(IdentifierInput)`, and `help(ExpressionInput)` all point users toward the correct semantic-math guide and showcase notebook.
- `docs/guides/api-discovery.md` contains a semantic-math / MathLive entry.
- The repository’s “Learn more / explore” links work as an actual navigation path rather than a dead end.
