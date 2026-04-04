# Issue 035: Semantic-math public docstrings are placeholder-heavy and do not meet the repository’s own documentation standard

## Status
Closed (2026-04-03)

## Summary
The semantic-math public surface now uses substantive docstrings across the canonical identifier layer and the MathLive context/transport/widget stack. The updated docstrings explain canonical identifiers versus display LaTeX, context registration, transport manifests, and widget parse semantics, and they point readers toward the semantic-math guide, showcase notebooks, and focused regression tests.

## Evidence
- `src/gu_toolkit/identifiers/policy.py` now contains rewritten docstrings for `identifier_to_latex()`, `symbol()`, and the related identifier-rendering helpers.
- `src/gu_toolkit/mathlive/context.py`, `src/gu_toolkit/mathlive/transport.py`, `src/gu_toolkit/mathlive/inputs.py`, and `src/gu_toolkit/mathlive/widget.py` now describe parsing, transport, and widget workflows with semantic examples rather than placeholder prose.
- The placeholder phrases called out in this issue (`"This API accepts the parameters declared in its Python signature."`, `"Result produced by this API."`, and generic `result = ...` examples) are absent from `src/gu_toolkit/identifiers/` and `src/gu_toolkit/mathlive/`.
- `tests/test_public_api_docstrings.py` now includes semantic-math-specific regression coverage for representative APIs such as `symbol()`, `ExpressionContext`, `build_mathlive_transport_manifest()`, `IdentifierInput`, and `ExpressionInput`.
- Verified with `PYTHONPATH=src pytest tests/test_public_api_docstrings.py tests/semantic_math/test_identifier_policy.py tests/semantic_math/test_expression_context.py tests/semantic_math/test_mathlive_inputs.py tests/semantic_math/test_symbolic_identifier_families.py -q`.

## TODO
- [x] Rewrite the semantic-math public docstrings with actual semantic content.
- [x] Use real examples per API family instead of generic `result = ...` placeholders.
- [x] Replace generic “Learn more” navigation with semantic-math-specific guidance.
- [x] Re-run targeted regression tests after the documentation refresh.

## Exit criteria
- [x] `help(symbol)`, `help(ExpressionContext)`, `help(ExpressionContext.from_symbols)`, `help(IdentifierInput)`, and `help(ExpressionInput)` are informative without needing source inspection.
- [x] Placeholder sentences such as “This API accepts the parameters declared in its Python signature” are removed from the semantic-math public surface.
- [x] The updated docstrings satisfy the repository documentation structure and are protected by regression tests.
