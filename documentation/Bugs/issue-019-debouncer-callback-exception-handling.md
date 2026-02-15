# Issue 019: Debouncer callback exceptions are not handled explicitly

## Status
Open

## Summary
`QueuedDebouncer` executes the callback without a guard, so callback exceptions can terminate/disable update behavior depending on runtime mode.

## Evidence
- `debouncing.py` executes `self._callback(*call.args, **call.kwargs)` directly inside the delayed runner.

## TODO
- [ ] Wrap callback invocation with explicit error handling and logging.
- [ ] Ensure both threading and asyncio modes keep debouncer state consistent after errors.
- [ ] Add regression tests for callback failures.

## Exit Criteria
- [ ] Callback exceptions are observable (logged/raised intentionally) and do not silently wedge updates.
