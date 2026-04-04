# Issue 038: The notebook introduces the low-level transport manifest too early and without a schema

## Status
Open

## Summary
The context-building section teaches the lowest-level frontend transport object (`transport_manifest`) before it teaches the higher-level conceptual model (`ExpressionContext`, `SymbolSpec`, `FunctionSpec`). Readers are immediately exposed to raw JSON-like dict access and undocumented keys such as `fieldRole`, `latexHead`, and `template`, even though the public Python model already has named structures.

This makes the notebook harder to learn from and blurs the boundary between “public user model” and “frontend transport payload.”

## Evidence
- Notebook cell 4 explains `ExpressionContext` conceptually.
- Notebook cell 7 then jumps straight to:
  - `manifest = ctx.transport_manifest(field_role='expression')`
  - `symbols_by_name = {entry['name']: entry for entry in manifest['symbols']}`
  - `functions_by_name = {entry['name']: entry for entry in manifest['functions']}`
  - assertions against raw keys such as `['latex']`, `['latexHead']`, and `['template']`
- The public Python model already has higher-level structures:
  - `ExpressionContext.symbols` and `ExpressionContext.functions` (`src/gu_toolkit/mathlive/context.py:209-210`)
  - `SymbolSpec` fields (`src/gu_toolkit/mathlive/context.py:114-116`)
  - `FunctionSpec` fields (`src/gu_toolkit/mathlive/context.py:158-161`)
- The transport manifest is explicitly JSON-like and low-level:
  - `src/gu_toolkit/mathlive/transport.py:286-311`
- The frontend widget consumes that schema internally:
  - fallback/manifest handling in `src/gu_toolkit/mathlive/widget.py:167-203`
  - function menu/template use in `src/gu_toolkit/mathlive/widget.py:285-321`
  - serializer hook use of `latexHead` in `src/gu_toolkit/mathlive/widget.py:361-383`
- A repo-wide search of markdown docs during analysis did not find a user-facing schema reference for `fieldRole`, `latexHead`, or the manifest entry shape.

## TODO / Approach to solution
- Reorder the notebook:
  1. show `ExpressionContext`,
  2. show `ctx.symbols` / `ctx.functions` or a friendly summary,
  3. then present `transport_manifest()` as the derived frontend snapshot.
- Add a short schema explanation if the manifest remains in the notebook.
- Clearly label the manifest as a frontend transport contract, not the primary Python authoring interface.
- If Python-side manifest inspection is expected to be common, consider a typed helper or pretty-printer instead of raw nested dict access.

## Exit criteria
- A first-time reader can understand the context model before reading raw transport payloads.
- `fieldRole`, `latexHead`, `template`, and similar keys are either documented or moved behind a clearer abstraction.
- The notebook no longer treats the manifest as if it were self-explanatory user-facing state.
