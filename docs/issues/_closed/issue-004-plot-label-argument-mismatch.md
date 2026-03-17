# Bug 004: Notebook uses unsupported `label=` kwarg in `plot(...)`

## Description
The notebook example passes `label="..."` to module-level `plot(...)` calls. Current `Figure.plot` API does not accept `label`, causing an argument error.

## Analysis
- `Figure.plot` signature included styling options (`color`, `thickness`, `dash`, `line`, `opacity`, `trace`) but no `label` parameter.
- The notebook used `label` in "Common examples", so users copy-pasting it failed.
- This is an API/documentation mismatch where the notebook demonstrated a natural legend naming pattern that the API should support.

## Implemented solution
Implemented the UX/API fix by adding first-class `label` support to both plotting entry points:

1. Added `label: Optional[str] = None` to `Figure.plot(...)`.
2. Added `label: Optional[str] = None` to module-level `plot(...)` and forwarded it.
3. Creation behavior:
   - If `label` is provided, the new trace legend name uses `label`.
   - If `label` is omitted, behavior remains unchanged (legend defaults to `id`).
4. Update behavior:
   - If updating an existing `id` and `label` is provided, the plot label is updated.
   - If `label` is omitted on update, existing label is preserved.
5. Added tests covering label support on both create and update paths.
6. Updated `Toolkit_overview.ipynb` by removing the stale inline bug note in the example cell that now works with `label`.

## Summary of changes
- `Figure.plot(...)` now accepts `label` and applies it correctly during create/update.
- Module-level `plot(...)` now accepts and forwards `label`.
- Added regression tests:
  - create with `label` sets legend name,
  - update with same `id` and new `label` updates legend name.
- Notebook example remains the same API usage (`label=...`) and is now valid; removed obsolete "BUG" comment.
