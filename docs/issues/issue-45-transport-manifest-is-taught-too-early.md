# Issue: The showcase teaches the low-level transport manifest before the user-facing workflow

## Summary
The notebook introduces the frontend transport manifest before it gives readers a simple, successful widget workflow. That pushes learners into a JSON-like internal representation too early and makes the tutorial feel backend-first instead of showcase-first.

The problem is amplified because the manifest keys used in the notebook (`fieldRole`, `latexHead`, `template`) are not documented in the guides as a user-facing schema.

## Evidence
- Notebook cell 11 builds `manifest = ctx.transport_manifest(field_role='expression')`, reindexes it into `symbols_by_name` / `functions_by_name`, and asserts on raw keys such as `latex`, `latexHead`, and `template`.
- The first truly interactive widget examples do not appear until later (`IdentifierInput` in cell 13 and `ExpressionInput` in cell 16), so readers see transport internals before they see the main workflow.
- `src/gu_toolkit/mathlive/transport.py:315-342` shows that `build_mathlive_transport_manifest()` returns a raw `dict[str, Any]` transport object with `version`, `fieldRole`, `symbols`, and `functions` entries.
- `src/gu_toolkit/mathlive/widget.py:303-405` shows that the frontend consumes `latex`, `latexHead`, and `template` internally for menus, insertion templates, and serializer hooks.
- A search across `docs/guides/` for `fieldRole`, `latexHead`, or `template` returns no guide-level schema documentation, so the notebook is effectively making readers reverse-engineer internal transport structure.
- Notebook cell 8's review comments already point in the same direction: the notebook should start from working functionality, not from internals.

## TODO / Approach to solution
- Reorder the notebook so it starts with a minimal working widget example and a concrete user task.
- Move manifest inspection later, after `ExpressionContext`, `IdentifierInput`, and `ExpressionInput` have already been shown conceptually.
- If manifest inspection remains, label it clearly as a derived frontend transport artifact and document the small schema that readers are expected to understand.
- Consider a friendlier summary helper instead of raw dict indexing in the tutorial.

## Exit criteria
- A first-time reader can get a widget working before encountering transport internals.
- Transport keys used in the notebook are either documented or hidden behind a clearer abstraction.
- The notebook reads like a tutorial first and an implementation deep-dive second.
