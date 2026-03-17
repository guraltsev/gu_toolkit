from __future__ import annotations

from unittest.mock import patch

from gu_toolkit.debouncing import QueuedDebouncer


class _FakeThreadTimer:
    created: list["_FakeThreadTimer"] = []

    def __init__(self, delay: float, callback):
        self.delay = delay
        self.callback = callback
        self.daemon = False
        _FakeThreadTimer.created.append(self)

    def start(self) -> None:
        return None


def test_debouncer_emits_drop_overflow_event() -> None:
    events: list[dict[str, object]] = []

    def _sink(*, event: str, source: str, phase: str, **fields):
        payload = {"event": event, "source": source, "phase": phase}
        payload.update(fields)
        events.append(payload)

    with patch("gu_toolkit.debouncing.threading.Timer", _FakeThreadTimer):
        debouncer = QueuedDebouncer(
            lambda *_args, **_kwargs: None,
            execute_every_ms=1,
            drop_overflow=True,
            name="test-debouncer",
            event_sink=_sink,
        )
        debouncer("a")
        debouncer("b")
        debouncer("c")
        _FakeThreadTimer.created[0].callback()

    assert any(event["event"] == "debounce_drop_overflow" for event in events)
    assert any(event["event"] == "debounce_tick_completed" for event in events)
