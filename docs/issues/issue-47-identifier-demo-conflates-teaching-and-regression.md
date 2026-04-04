# Issue: The `IdentifierInput` section conflates interactive teaching, hidden assertions, and programmatic mutation

## Summary
The `IdentifierInput` section is presented as a user-facing demo, but the main cell behaves mostly like a regression test. It displays a widget, immediately asserts internal outcomes, then overwrites the widget state programmatically. The user is never shown a clear manual workflow or a visible parsed result.

This makes the section hard to learn from, especially for someone trying to understand what to type and what output they should expect.

## Evidence
- Notebook cell 12 says the widget section "also doubles as an integration check".
- Notebook cell 13:
  - displays `IdentifierInput(context=ctx, value=r'a_{1,2}')`
  - immediately asserts `identifier_widget.parse_value() == 'a_1_2'`
  - clears `value`
  - injects `math_json` programmatically
  - asserts again
  - finishes with a narrative markdown line, but without surfacing the parsed identifier interactively
- The same cell contains review comments explicitly asking for:
  - manual instructions in markdown
  - expected output
  - a separate integration cell
  - and a dynamic output area instead of hidden assertions
- Notebook cell 8 includes a broader review note that manual testing was confusing and that the current flow was not understandable as a user-facing showcase.
- The widget stack already exposes public state that could support visible feedback:
  - `MathLiveField` syncs `value`, `math_json`, `transport_valid`, and `transport_errors` (`src/gu_toolkit/mathlive/widget.py:72-85`)
  - `IdentifierInput.parse_value()` is a public helper for semantic output (`src/gu_toolkit/mathlive/inputs.py:209-247`)

## TODO / Approach to solution
- Split the section into a manual exploration cell and a separate regression/integration cell.
- Add one markdown cell that tells the user exactly what to type and what canonical identifier they should see.
- Show the parsed result explicitly in notebook output instead of relying on invisible asserts.
- If automated coverage is needed, keep the asserts but move them out of the primary teaching path.

## Exit criteria
- A reader can manually interact with the widget and understand what happened without reading source.
- The parsed canonical identifier is visible in notebook output.
- Regression assertions remain available, but no longer dominate the tutorial cell.
