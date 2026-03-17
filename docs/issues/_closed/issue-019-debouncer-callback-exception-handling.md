# Issue 019: Debouncer callback exceptions are not handled explicitly

## Status
Closed (Resolved 2026-02-15)

## Summary
`QueuedDebouncer` now executes callbacks behind an explicit exception boundary and logs failures. Callback errors no longer prevent subsequent queued events from being processed.

## Evidence
- `debouncing.py` wraps callback execution in `try/except` and logs with module logger context.
- Regression tests verify this behavior in both threading-timer and asyncio-loop scheduling modes: a failing first callback is logged and a subsequent callback still executes.

## TODO
- [x] Wrap callback invocation with explicit error handling and logging.
- [x] Ensure both threading and asyncio modes keep debouncer state consistent after errors.
- [x] Add regression tests for callback failures.

## Exit Criteria
- [x] Callback exceptions are observable (logged/raised intentionally) and do not silently wedge updates.
