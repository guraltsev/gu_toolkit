# Issue 051: `IdentifierInput.parse_value()` / `ExpressionInput.parse_value()` can return stale MathJSON after the visible text changes

## Status
Closed (2026-04-04)

## Summary
The MathLive widget wrappers always forwarded `self.math_json` into the parsing layer whenever that payload was present. If the widget text changed later, `parse_value()` could keep returning the older structured result instead of the newer visible text.

That behavior was especially misleading in notebook code and in fallback/headless environments where Python-side trait mutation can happen before the browser recomputes transport state. The widget layer needed an explicit freshness rule instead of blindly trusting any non-`None` `math_json` payload.

## Evidence
- Before the fix, this reproduced in pure Python:

  ```python
  widget = IdentifierInput(value="x")
  widget.math_json = "x"
  widget.value = "y"
  assert widget.parse_value() == "x"  # stale result before the fix
  ```

- `src/gu_toolkit/mathlive/inputs.py` previously passed `self.math_json` directly into `ExpressionContext.parse_identifier()` / `ExpressionContext.parse_expression()`.
- `ExpressionContext.parse_identifier()` and `ExpressionContext.parse_expression()` correctly prefer structured transport when callers tell them that payload is current, so the freshness decision belongs in the widget layer.
- The fix introduced a frontend-synced `transport_source_value` in `src/gu_toolkit/mathlive/widget.py` plus widget-side change ordering in `src/gu_toolkit/mathlive/inputs.py`, so stale structured payloads can be ignored until they match the current visible value again.
- Regression coverage now lives in `tests/semantic_math/test_mathlive_inputs.py` for both identifier and expression widgets.
- Documentation was aligned in:
  - `examples/MathLive_identifier_system_showcase.ipynb`
  - `docs/guides/api-discovery.md`
  - `docs/guides/semantic-math-refactoring-philosophy.md`

## TODO / Approach to solution
- [x] Track enough widget-side state to tell whether a `math_json` payload still belongs to the current visible text.
- [x] Add a frontend-synced source-value snapshot for real browser commits.
- [x] Fall back to the newer text when an older structured payload becomes stale.
- [x] Preserve the normal "prefer structured transport" rule when MathJSON is still synchronized.
- [x] Add regression tests for identifier and expression widgets.
- [x] Update notebook/guides wording so they describe synchronized MathJSON rather than unconditional preference.

## Exit criteria
- [x] Changing widget text after an earlier `math_json` payload no longer returns stale parses.
- [x] Matching MathJSON still remains authoritative when it corresponds to the current visible text.
- [x] Identifier and expression widget regressions cover the stale-transport case.
- [x] The docs explain the synchronized-transport rule accurately.
