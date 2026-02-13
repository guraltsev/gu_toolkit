# Bug 004: Notebook uses unsupported `label=` kwarg in `plot(...)`

## Description
The notebook example passes `label="..."` to module-level `plot(...)` calls. Current `Figure.plot` API does not accept `label`, causing an argument error.

## Analysis
- `Figure.plot` signature includes styling options (`color`, `thickness`, `dash`, `line`, `opacity`, `trace`) but no `label` parameter.
- The notebook uses `label` in "Common examples", so users copy-pasting it will fail.
- This is an API/documentation mismatch:
  - either API intended to support trace naming but omitted,
  - or notebook is stale and should use currently supported path (e.g., trace dict/name field, or post-creation plot object label assignment).

## Summary of fix
Choose one consistent direction:
1. **Preferred UX fix:** add optional `label` support to `Figure.plot` and thread it into trace creation/update.
2. **Docs-only fix:** remove `label=` from notebook and show supported alternative.

## Detailed plan / blueprint
1. Decide contract:
   - If supporting `label`, add `label: Optional[str] = None` in `Figure.plot` and module-level `plot` wrapper.
2. Wire through implementation:
   - On new trace creation, use label as trace name.
   - On updates, apply name update when label is provided.
3. Add tests:
   - Creating with `label` sets plot label/name.
   - Updating same `id` with new label updates legend entry.
4. Update notebook examples to match finalized API.
5. If not adding API support, explicitly document replacement syntax in notebook comments.
