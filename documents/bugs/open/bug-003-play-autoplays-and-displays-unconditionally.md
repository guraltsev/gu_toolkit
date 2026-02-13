# Bug 003: `play()` autoplays and displays audio widget unconditionally

## Description
Notebook reports that `play(...)` starts playback immediately without explicit display request, and should only autoplay when requested.

## Analysis
- Current implementation hardcodes `<audio controls autoplay ...>` and calls `display(widget)` inside `play`.
- This creates two behaviors coupled together:
  1. Side effect display on function call.
  2. Forced autoplay in rendered element.
- In notebooks, users generally expect either:
  - pure-return API (caller decides `display(...)`), or
  - explicit `autoplay` option defaulting to `False`.

## Summary of fix
- Add explicit `autoplay: bool = False` parameter.
- Remove unconditional display side-effect (or gate it behind a `display_now` flag with conservative default).
- Keep return value as displayable object.

## Detailed plan / blueprint
1. Update signature:
   - `def play(expr, var_and_limits, loop=True, autoplay=False, display_now=False):`
2. Build audio HTML with conditional attributes:
   - include `autoplay` only when `autoplay=True`.
3. Side-effect policy:
   - If `display_now` true: call `display(widget)`.
   - Else: return widget only.
4. Backward compatibility note:
   - Mention behavior change in docs/changelog, or keep temporary compatibility wrapper that warns once.
5. Add tests:
   - Returned HTML does not contain `autoplay` by default.
   - Contains `autoplay` when requested.
   - No implicit display call when `display_now=False` (mock display in test).


## Implemented solution
- Updated `play` signature to `play(expr, var_and_limits, loop=True, autoplay=False)`.
- Removed unconditional `display(widget)` side effect so the function now returns a widget only.
- Added conditional HTML attribute emission so `autoplay` appears only when requested.
- Added unit tests to verify:
  - no `autoplay` attribute by default,
  - `autoplay` appears when explicitly enabled.
- Updated `Toolkit_overview.ipynb` play section to demonstrate explicit `display(...)` and optional `autoplay=True`.

## Change summary
This bug is fixed by decoupling rendering from playback policy: `play` now behaves as a pure-return API and only autoplays when explicitly configured.
