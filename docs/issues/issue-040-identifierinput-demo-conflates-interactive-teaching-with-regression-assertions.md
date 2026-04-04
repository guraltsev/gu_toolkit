# Issue 040: The `IdentifierInput` demo conflates interactive teaching with regression assertions

## Status
Open

## Summary
The `IdentifierInput` section displays a widget, but the cell behaves primarily like a hidden regression test. It immediately asserts parse results, programmatically overwrites the widget state, and does not show the parsed canonical identifier back to the user. That weakens the cell as a teaching artifact.

The notebook text says the cell “doubles as an integration check,” but the current balance is too far toward invisible verification and not far enough toward visible user feedback.

## Evidence
- Notebook cell 8 introduces the section as a user-facing explanation of how `IdentifierInput` normalizes what the user typed.
- Notebook cell 9:
  - displays `IdentifierInput(context=ctx, value=r'a_{1,2}')`
  - immediately asserts `identifier_widget.parse_value() == 'a_1_2'`
  - then clears `value`, injects MathJSON, and asserts again
  - finishes with a string summary, but does not display the parsed value during user interaction
- The cell’s own review note says it should:
  - instruct the user what to input,
  - provide feedback on what was entered,
  - and move assertion tests into a separate cell.
- The visible output recorded in the notebook is just the widget plus the final summary string; the parse results themselves are not surfaced interactively.

## TODO / Approach to solution
- Split the section into:
  1. an interactive exploration cell with instructions and visible parse feedback,
  2. a separate regression/assert cell.
- After display, show the canonical parsed result explicitly (printed text, callback output, or a second output cell).
- Keep the asserts for notebook regression value, but move them out of the main explanatory path.

## Exit criteria
- A reader can interact with the widget and see what canonical identifier was produced.
- The notebook separates user teaching from regression enforcement.
- The section remains runnable, but its primary visible behavior is instructional rather than test-like.
