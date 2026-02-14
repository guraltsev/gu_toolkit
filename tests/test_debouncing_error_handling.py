from __future__ import annotations

import warnings

from gu_toolkit.debouncing import QueuedDebouncer


def test_debouncer_warns_and_keeps_processing_after_callback_error() -> None:
    state = {"n": 0}

    def _callback(_payload):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("boom")

    debouncer = QueuedDebouncer(_callback, execute_every_ms=1, drop_overflow=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        debouncer("first")
        debouncer("second")
        debouncer._on_tick()
        debouncer._on_tick()

    assert state["n"] == 2
    assert any("QueuedDebouncer callback failed" in str(w.message) for w in caught)
