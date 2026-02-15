from __future__ import annotations

import logging
from unittest.mock import patch

from gu_toolkit.debouncing import QueuedDebouncer


class _FakeThreadTimer:
    created: list["_FakeThreadTimer"] = []

    def __init__(self, delay: float, callback):
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.started = False
        _FakeThreadTimer.created.append(self)

    def start(self) -> None:
        self.started = True


class _FakeLoopHandle:
    def __init__(self, callback):
        self._callback = callback

    def fire(self) -> None:
        self._callback()


class _FakeAsyncLoop:
    def __init__(self) -> None:
        self.handles: list[_FakeLoopHandle] = []

    def call_later(self, _delay: float, callback):
        handle = _FakeLoopHandle(callback)
        self.handles.append(handle)
        return handle


def test_debouncer_logs_and_keeps_processing_after_callback_error_threading(caplog) -> None:
    state = {"n": 0}

    def _callback(_payload):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("boom")

    _FakeThreadTimer.created.clear()

    with patch("gu_toolkit.debouncing.threading.Timer", _FakeThreadTimer):
        debouncer = QueuedDebouncer(_callback, execute_every_ms=1, drop_overflow=False)
        with caplog.at_level(logging.ERROR, logger="gu_toolkit.debouncing"):
            debouncer("first")
            debouncer("second")
            assert len(_FakeThreadTimer.created) == 1

            _FakeThreadTimer.created[0].callback()
            assert len(_FakeThreadTimer.created) == 2
            _FakeThreadTimer.created[1].callback()

    assert state["n"] == 2
    assert "QueuedDebouncer callback failed" in caplog.text


def test_debouncer_logs_and_keeps_processing_after_callback_error_asyncio(caplog) -> None:
    state = {"n": 0}

    def _callback(_payload):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("boom")

    fake_loop = _FakeAsyncLoop()

    with patch("gu_toolkit.debouncing.asyncio.get_running_loop", return_value=fake_loop):
        debouncer = QueuedDebouncer(_callback, execute_every_ms=1, drop_overflow=False)
        with caplog.at_level(logging.ERROR, logger="gu_toolkit.debouncing"):
            debouncer("first")
            debouncer("second")
            assert len(fake_loop.handles) == 1

            fake_loop.handles[0].fire()
            assert len(fake_loop.handles) == 2
            fake_loop.handles[1].fire()

    assert state["n"] == 2
    assert "QueuedDebouncer callback failed" in caplog.text
