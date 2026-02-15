from __future__ import annotations

import logging

from gu_toolkit.debouncing import QueuedDebouncer


def test_debouncer_logs_and_keeps_processing_after_callback_error(caplog) -> None:
    state = {"n": 0}

    def _callback(_payload):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("boom")

    debouncer = QueuedDebouncer(_callback, execute_every_ms=1, drop_overflow=False)

    with caplog.at_level(logging.ERROR, logger="gu_toolkit.debouncing"):
        debouncer("first")
        debouncer("second")
        debouncer._on_tick()
        debouncer._on_tick()

    assert state["n"] == 2
    assert "QueuedDebouncer callback failed" in caplog.text
