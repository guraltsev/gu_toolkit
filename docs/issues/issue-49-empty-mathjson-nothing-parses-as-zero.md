# Issue: Empty/sentinel MathJSON can parse as a valid value (`0` / `"Nothing"`) instead of as empty input

## Summary
The backend currently treats the MathJSON sentinel `Nothing` as real semantic input. On the expression path it becomes `0`; on the identifier path it becomes the literal identifier `Nothing`.

That is a plausible explanation for the notebook review complaint that manual testing kept producing `0`. More importantly, it means empty or placeholder frontend transport can be accepted as valid user input instead of being rejected as empty.

## Evidence
- `src/gu_toolkit/mathlive/transport.py:82-89` maps the standard symbol `"Nothing"` to `sp.Integer(0)`.
- `src/gu_toolkit/mathlive/context.py:1248-1262` shows that `parse_expression(...)` prefers any provided `math_json` payload before it checks whether the text is empty.
- `src/gu_toolkit/mathlive/widget.py:447-475` snapshots `expr.json` directly into the synced `math_json` trait, with no special filtering for empty/sentinel payloads.
- Reproduction in the current repo environment:
  - `ExpressionInput(value='').math_json = 'Nothing'` then `parse_value()` returns `0`.
  - `ExpressionInput(value='x').math_json = 'Nothing'` still returns `0`, because MathJSON wins over text.
  - `IdentifierInput(value='').math_json = 'Nothing'` returns `'Nothing'` instead of raising an "input required" style error.
- There is no focused regression test covering the empty/sentinel transport case; the current semantic-math tests cover many MathJSON cases but not this one.
- Notebook cell 8 contains the review note: "I tried manually and could not figure it out. Value was always returning 0." The current `Nothing -> 0` transport path is consistent with that user experience.

## TODO / Approach to solution
- Treat `Nothing` (and any equivalent empty/sentinel payloads) as absence of semantic input, not as a valid expression/identifier.
- Apply that rule consistently across identifier and expression parsing.
- Add regression tests covering empty fields, sentinel payloads, and precedence between text and MathJSON when one side is effectively empty.
- Document the empty-input behavior so manual notebook testing is predictable.

## Exit criteria
- Empty widget states do not parse as `0` or `'Nothing'`.
- Expression and identifier inputs handle empty/sentinel MathJSON consistently.
- Regression tests protect the empty-input contract.
