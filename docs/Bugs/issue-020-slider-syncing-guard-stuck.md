# Issue 020: Slider `_syncing` guard can remain set after exceptional paths

## Status
Open

## Summary
`FloatSlider` uses `_syncing` to prevent recursive updates. Any path that exits early without resetting this flag can suppress future legitimate updates.

## Evidence
- `Slider.py` has multiple `_syncing` toggles across UI synchronization paths.
- The guard is relied upon in value/text/limits handlers.

## TODO checklist
- [ ] Audit all `_syncing` write paths for guaranteed reset behavior.
- [ ] Convert vulnerable paths to `try/finally` patterns where missing.
- [ ] Add regression tests that simulate parse/update errors during sync.

## Exit Criteria
- [ ] `_syncing` always returns to `False` after failed or successful sync attempts.
- [ ] Slider remains interactive after malformed input and callback errors.
