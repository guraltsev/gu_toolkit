# Issue 020: Slider `_syncing` guard can remain set after exceptional paths

## Status
Open

## Summary
Assessment (2026-02-17): implementation is partially complete; coverage and/or documentation gaps listed below keep this issue open.

State-of-completion checklist:
- [x] `_syncing` writes in `FloatSlider` sync helpers are guarded with `try/finally` reset paths (`_sync_number_text`, `_sync_limit_texts`, and invalid-limit rollback branch).
- [x] User-facing slider docs/docstrings were expanded and now describe parse/revert behavior for text commits.
- [x] Regression coverage exists for expression parsing and invalid text reverts (`tests/test_slider_parsing.py`).
- [ ] No targeted tests simulate exceptions during synchronization callbacks and verify `_syncing` is cleared.
- [ ] No tests verify slider interactivity after observer/callback exceptions during sync events.

## Evidence
- `Slider.py` contains `try/finally` protections around key `_syncing` toggles.
- `tests/test_slider_parsing.py` verifies expression parsing and invalid-text rollback.
- No test currently asserts `_syncing` returns to `False` after raised exceptions in sync callbacks.

## TODO
- [x] Audit all `_syncing` write paths for guaranteed reset behavior.
- [x] Convert vulnerable paths to `try/finally` patterns where missing.
- [ ] Add regression tests that inject failures during `_sync_number_text` / `_sync_limit_texts` and assert `_syncing` is reset.
- [ ] Add regression tests that simulate observer/callback exceptions and verify slider interactions continue to work.

## Exit criteria
- [ ] `_syncing` always returns to `False` after failed or successful sync attempts, validated by tests.
- [ ] Slider remains interactive after malformed input and callback errors, validated by tests.
