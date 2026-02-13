# Bug 001: `wave.figure()` context usage note and "parameter does not change" in frozen/unfrozen demo

## Description
The notebook flags two issues in the `numeric_expression` freeze/unfreeze section:
1. Comment says `with wave.figure():` is a bug and should be `with wave.figure`.
2. Comment says parameter changes are not reflected after `unfreeze()`.

## Analysis
- `Plot.figure` is implemented as a **method** that returns the owning `Figure` object, and examples in code explicitly use `plot.figure()`; therefore `with wave.figure():` is the correct usage for entering figure context.
- `with wave.figure` (without calling) would pass a method object to `with`, which is not a context manager.
- `numeric_expression.unfreeze()` is tested to require explicit positional arguments for previously frozen parameters when called with no keys (i.e., `f(x, a, b, c)`).
- In the notebook snippet, values are read once into `a_val`, `b_val`, `c_val` and then passed to the function; if users expect reactive linkage to sliders after unfreeze, this is a conceptual mismatch. `unfreeze()` returns a function that accepts arguments again; it does not magically read slider state unless dynamic placeholders are reintroduced.

## Summary of fix
- Fix notebook comments and explanatory text (documentation bug, not library bug).
- Keep `with wave.figure():` as-is.
- Clarify that `unfreeze()` restores function arguments; it does not auto-bind parameters unless explicitly frozen with dynamic placeholders/context.

## Detailed plan / blueprint
1. Edit the notebook section around freeze/unfreeze:
   - Remove the incorrect comment about `wave.figure()`.
   - Replace the second bug comment with guidance on expected `unfreeze()` semantics.
2. Add a short explanatory markdown note:
   - "`unfreeze()` without keys makes parameters callable inputs again. Pass updated values explicitly."
3. Optionally add a tiny verification cell:
   - Change `params[a]`, recompute `a_val`, rerun `f_unfrozen(1.0, a_val, b_val, c_val)` to show expected behavior.
4. If desired UX is "still auto-linked to sliders", document alternate pattern:
   - keep `f_live`, or re-freeze with `DYNAMIC_PARAMETER` placeholders using context utilities.
