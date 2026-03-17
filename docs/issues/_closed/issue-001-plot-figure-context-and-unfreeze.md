# Bug 001: `wave.figure()` context usage note and "parameter does not change" in frozen/unfrozen demo

## Description
The notebook flagged two issues in the `numeric_expression` freeze/unfreeze section:
1. `with wave.figure():` should be `with wave.figure`.
2. After `unfreeze()`, a parameter update appeared to be ignored.

## Root cause
- `Plot.figure` was implemented as a method returning the owning `Figure`, which made `with wave.figure` invalid and required `with wave.figure()`.
- The unfreeze demo read `a_val`, `b_val`, `c_val` only once before calling the unfrozen function. After slider/parameter changes, stale values were still passed, so output did not change.

## Solution implemented
1. Converted `Plot.figure` from a method to a read-only property so it can be used naturally as a context manager source: `with wave.figure:`.
2. Updated the toolkit overview notebook freeze/unfreeze section:
   - removed incorrect bug comments,
   - switched context usage to `with wave.figure:`,
   - clarified that `unfreeze()` restores explicit call-time arguments,
   - added a follow-up step that refreshes parameter values after a second parameter change and re-calls the unfrozen function.
3. Added a regression test that verifies `plot.figure` returns its owner `Figure` and can be used to establish parameter context.

## Summary of changes
- `Plot.figure` is now a property.
- Notebook demo now demonstrates correct context usage and correct unfrozen call behavior (refresh values, then call).
- Added test coverage for property/context behavior to prevent regressions.
