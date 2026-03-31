from __future__ import annotations

from unittest.mock import patch

from gu_toolkit.animation import AnimationClock


class _FakeThreadTimer:
    created: list["_FakeThreadTimer"] = []

    def __init__(self, delay: float, callback):
        self.delay = float(delay)
        self.callback = callback
        self.started = False
        self.cancelled = False
        self.daemon = False
        _FakeThreadTimer.created.append(self)

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


def test_animation_clock_cancels_pending_timer_when_last_subscriber_unsubscribes() -> None:
    _FakeThreadTimer.created.clear()
    clock = AnimationClock(frequency_hz=20.0, time_source=lambda: 0.0)

    def _callback(_now: float) -> None:
        return None

    with patch("gu_toolkit.runtime_support._resolve_running_loop", return_value=(None, None)), patch(
        "gu_toolkit.runtime_support._resolve_browser_timeout_primitives",
        return_value=(None, None),
    ), patch(
        "gu_toolkit.runtime_support._resolve_tornado_ioloop",
        return_value=(None, None),
    ), patch("gu_toolkit.animation.threading.Timer", _FakeThreadTimer):
        clock.subscribe(_callback)
        assert len(_FakeThreadTimer.created) == 1
        clock.unsubscribe(_callback)

    assert _FakeThreadTimer.created[0].cancelled is True
    snapshot = clock.performance_snapshot()
    assert snapshot["counters"].get("cancelled_timers", 0) >= 1
