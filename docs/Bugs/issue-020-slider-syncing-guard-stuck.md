# Issue 020: Slider `_syncing` guard can remain set after exceptional paths

## Status
Open

## Summary
State-of-completion checklist:
- [x] `_syncing` writes in `FloatSlider` sync helpers are guarded with `try/finally` reset paths (`_sync_number_text`, `_sync_limit_texts`, and invalid-limit rollback branch).
- [x] User-facing slider docs/docstrings were expanded and now describe parse/revert behavior for text commits.
- [~] Regression coverage exists for invalid text reverts, but it does **not** yet assert `_syncing` is cleared after exception paths.
- [ ] No targeted tests yet simulate exceptions during synchronization callbacks and verify the widget remains interactive afterward.

## Evidence
- `Slider.py` now uses explicit `try/finally` reset for key `_syncing` update paths.
- `tests/test_slider_parsing.py` validates expression parsing and invalid-text revert behavior.
- There is still no dedicated regression test that inspects `_syncing` state or post-exception interactivity guarantees.

## TODO
- [x] Audit all `_syncing` write paths for guaranteed reset behavior.
- [x] Convert vulnerable paths to `try/finally` patterns where missing.
- [ ] Add regression tests that simulate parse/update errors during sync and assert `_syncing` returns to `False`.
- [ ] Add regression tests that simulate observer/callback exceptions and verify slider interactions continue to work.

## Exit criteria
- [ ] `_syncing` always returns to `False` after failed or successful sync attempts, validated by tests.
- [ ] Slider remains interactive after malformed input and callback errors, validated by tests.
