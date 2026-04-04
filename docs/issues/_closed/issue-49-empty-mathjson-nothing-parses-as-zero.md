# Issue 049: Empty/sentinel MathJSON can parse as a valid value (`0` / `"Nothing"`) instead of as empty input

## Status
Closed (2026-04-04)

## Summary
Empty MathJSON sentinels such as `Nothing` are now treated as missing input instead of semantic content. On the backend, the low-level MathJSON converters now raise `MathJSONParseError` for empty/sentinel payloads. In `ExpressionContext`, empty/sentinel MathJSON no longer overrides meaningful visible text. On the frontend bridge, empty/sentinel MathJSON is normalized to `null` before syncing back to Python.

## Evidence
- `src/gu_toolkit/mathlive/transport.py` no longer maps `Nothing` to `sp.Integer(0)` and now rejects empty/sentinel payloads via `MathJSONParseError`.
- `src/gu_toolkit/mathlive/context.py` now ignores empty/sentinel MathJSON when visible text is present and raises the usual required-input error when both sides are empty.
- `src/gu_toolkit/mathlive/widget.py` now normalizes empty/sentinel MathJSON snapshots to `null` before syncing them into the Python trait layer.
- `examples/MathLive_identifier_system_showcase.ipynb` now documents the empty-input rule explicitly.
- `tests/semantic_math/test_mathlive_inputs.py` now covers expression and identifier widgets with empty `Nothing` payloads, including fallback-to-text behavior and multiple empty-payload encodings.
- `tests/semantic_math/test_showcase_notebooks.py` now checks that the notebook keeps the explicit empty-input explanation.
- Verified with `PYTHONPATH=src pytest tests/semantic_math -q tests/test_public_api_docstrings.py -q`.

## TODO
- [x] Treat `Nothing` and equivalent empty/sentinel payloads as missing input.
- [x] Apply the rule consistently to identifier and expression parsing.
- [x] Avoid letting empty transport override meaningful text-field content.
- [x] Add regression coverage for sentinel handling and precedence.
- [x] Document the rule in the showcase notebook and guides.

## Exit criteria
- [x] Empty widget states no longer parse as `0` or `Nothing`.
- [x] Identifier and expression inputs now handle empty/sentinel MathJSON consistently.
- [x] Regression tests protect the empty-input contract.
