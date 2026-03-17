# Issue 008: Signature tracking test blocked by module shadowing

## Summary
`tests/test_numpify_refactor.py::test_signature_tracks_freeze_and_unfreeze` fails with `AttributeError: 'function' object has no attribute 'numpify'`.

## Analysis
- Same import shadowing issue as Issue 002.
- Signature assertions are currently not being executed.

## Proposed solution
- Fix Issue 002.
- Preserve this test to guard callable signature contracts across freeze/unfreeze operations.

## Disposition
**Duplicate root cause of Issue 002 (real bug).**


## Closure note (2026-02-14)
Closed because signature tracking behavior now passes (`tests/test_numpify_refactor.py::test_signature_tracks_freeze_and_unfreeze` did not fail).
