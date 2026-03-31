from __future__ import annotations

from unittest.mock import patch

import gu_toolkit.runtime_support as runtime_support


class _FakeThreadTimer:
    created: list["_FakeThreadTimer"] = []

    def __init__(self, delay: float, callback):
        self.delay = float(delay)
        self.callback = callback
        self.started = False
        self.cancelled = False
        _FakeThreadTimer.created.append(self)

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


class _FakeProxy:
    def __init__(self, callback) -> None:
        self._callback = callback
        self.destroyed = False

    def __call__(self):
        self._callback()

    def destroy(self) -> None:
        self.destroyed = True


class _FakeJS:
    def __init__(self) -> None:
        self.calls: list[tuple[object, int]] = []
        self.cleared: list[object] = []

    def setTimeout(self, callback, delay_ms: int):
        timer_id = len(self.calls) + 1
        self.calls.append((callback, int(delay_ms)))
        return timer_id

    def clearTimeout(self, timer_id) -> None:
        self.cleared.append(timer_id)


class _FakeTornadoLoop:
    def __init__(self) -> None:
        self.calls: list[tuple[float, object, object]] = []
        self.removed: list[object] = []

    def call_later(self, delay: float, callback):
        handle = object()
        self.calls.append((float(delay), callback, handle))
        return handle

    def remove_timeout(self, handle) -> None:
        self.removed.append(handle)


def test_schedule_later_prefers_browser_timeout_over_threading_timer() -> None:
    _FakeThreadTimer.created.clear()
    fake_js = _FakeJS()
    proxies: list[_FakeProxy] = []

    def _create_proxy(callback):
        proxy = _FakeProxy(callback)
        proxies.append(proxy)
        return proxy

    with patch.object(runtime_support, "_resolve_running_loop", return_value=(None, None)), patch.object(
        runtime_support,
        "_resolve_browser_timeout_primitives",
        return_value=(fake_js, _create_proxy),
    ), patch.object(runtime_support, "_resolve_tornado_ioloop", return_value=(None, None)):
        scheduled = runtime_support.schedule_later(
            0.05,
            lambda: None,
            owner="browser-test",
            thread_timer_factory=_FakeThreadTimer,
        )

    assert scheduled.backend == "browser_set_timeout"
    assert len(_FakeThreadTimer.created) == 0
    assert fake_js.calls[0][1] == 50

    scheduled.handle.cancel()
    assert fake_js.cleared == [1]
    assert proxies[0].destroyed is True


def test_schedule_later_uses_tornado_ioloop_before_threading_timer() -> None:
    _FakeThreadTimer.created.clear()
    fake_loop = _FakeTornadoLoop()

    with patch.object(runtime_support, "_resolve_running_loop", return_value=(None, None)), patch.object(
        runtime_support,
        "_resolve_browser_timeout_primitives",
        return_value=(None, None),
    ), patch.object(
        runtime_support,
        "_resolve_tornado_ioloop",
        return_value=(fake_loop, "tornado_ioloop"),
    ):
        scheduled = runtime_support.schedule_later(
            0.02,
            lambda: None,
            owner="tornado-test",
            thread_timer_factory=_FakeThreadTimer,
        )

    assert scheduled.backend == "tornado_ioloop"
    assert len(_FakeThreadTimer.created) == 0
    assert fake_loop.calls[0][0] == 0.02

    scheduled.handle.cancel()
    assert fake_loop.removed == [fake_loop.calls[0][2]]


def test_runtime_diagnostics_exposes_schedule_later_details() -> None:
    diagnostics = runtime_support.runtime_diagnostics()

    assert "schedule_later" in diagnostics
    assert "state" in diagnostics["schedule_later"]
    assert "counters" in diagnostics["schedule_later"]
