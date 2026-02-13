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
**Preferred UX fix:** add optional `label` support to `Figure.plot` and thread it into trace creation/update.


## Detailed plan / blueprint
Add `label: Optional[str] = None` in `Figure.plot` and module-level `plot` wrapper.
2. Wire through implementation:
   - On new trace creation, use label as trace name.
   - On updates, apply name update when label is provided.
3. Add tests:
   - Creating with `label` sets plot label/name.
   - Updating same `id` with new label updates legend entry.
   - if id is not specified, but label is make id the label (mangled to be unique)
   - allow getting plots by label `plots.by_label['label']`. Return array (possibly of lenght 0, 1 or more) of plots. 
4. Update notebook examples to match finalized API.
