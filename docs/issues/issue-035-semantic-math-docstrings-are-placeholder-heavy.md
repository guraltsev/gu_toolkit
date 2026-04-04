# Issue 035: Semantic-math public docstrings are placeholder-heavy and do not meet the repository’s own documentation standard

## Status
Open

## Summary
Key semantic-math APIs (`symbol`, `ExpressionContext`, `ExpressionContext.from_symbols`, `ExpressionContext.transport_manifest`, `IdentifierInput`, `ExpressionInput`, and related methods) use boilerplate docstrings that preserve section headings but do not explain behavior, parameters, return values, or realistic usage.

This is not just a style problem. The notebook is explicitly educational, and these helpers are meant to be discoverable from `help(...)`. Right now the docstrings do not answer the user’s core questions: what the API is for, what the parameters mean, what it returns, or which follow-up guide/example to read next.

## Evidence
- Notebook `examples/MathLive_identifier_system_showcase.ipynb`, cell 5, contains reviewer notes calling out the docstrings for `symbol` and similar APIs as effectively content-free.
- `docs/guides/public-api-documentation-structure.md` says users opening `help(...)` should be able to answer:
  - what the API is for,
  - how to call it,
  - what parameters and return values mean,
  - and what to read next (`lines 6-14`).
- The same guide requires meaningful summaries, parameter semantics, optional-argument explanations, and concrete examples (`lines 34-115`).
- Actual semantic-math docstrings are mostly placeholders:
  - `src/gu_toolkit/identifiers/policy.py:525-566` (`symbol`)
  - `src/gu_toolkit/mathlive/context.py:171-255` (`ExpressionContext`, `from_symbols`)
  - `src/gu_toolkit/mathlive/context.py:840-874` (`transport_manifest`)
  - `src/gu_toolkit/mathlive/transport.py:244-313` (`build_mathlive_transport_manifest`)
  - `src/gu_toolkit/mathlive/inputs.py:122-201` (`IdentifierInput`, `parse_value`)
- Repeated filler phrases include:
  - “This API accepts the parameters declared in its Python signature.”
  - “Result produced by this API.”
  - examples of the form `result = ...`.

## TODO / Approach to solution
- Rewrite the docstrings for the semantic-math public surface with actual semantic content:
  - explain canonical identifiers vs display LaTeX,
  - explain what the context stores,
  - explain what `parse_value()` returns,
  - explain what `transport_manifest()` is for.
- Use at least one real example per API family instead of `result = ...`.
- Improve “Learn more” to point to appropriate further documentation. These may be: related functions, external documentation (e.g. specific sympy or mathlive functionality), or more. It can include generic references to e.g. showcase notebooks but it must also include more specific references. 

## Exit criteria
- All code, especially that returned by `help(symbol)`, `help(ExpressionContext)`, `help(ExpressionContext.from_symbols)`, `help(IdentifierInput)`, and `help(ExpressionInput)` are informative without needing source inspection.
- Placeholder sentences such as “This API accepts the parameters declared in its Python signature” are removed from all public surface and replaced by informative descriptions
- The updated docstrings satisfy the expectations documented in `docs/guides/public-api-documentation-structure.md`.
