from __future__ import annotations

from typing import Any

import pytest

import gu_toolkit.figure_render_scheduler as scheduler_module
from gu_toolkit.figure_render_scheduler import FigureRenderScheduler, RenderRequest


class _ManualDebouncer:
    """Manual debouncer used to make scheduler tests deterministic."""

    instances: list["_ManualDebouncer"] = []

    def __init__(self, callback, *, execute_every_ms: int, drop_overflow: bool = True, **_: Any):
        self._callback = callback
        self.execute_every_ms = int(execute_every_ms)
        self.drop_overflow = bool(drop_overflow)
        self.call_count = 0
        _ManualDebouncer.instances.append(self)

    def __call__(self, *args, **kwargs):
        del args, kwargs
        self.call_count += 1

    def fire(self) -> None:
        self._callback()


@pytest.fixture(autouse=True)
def _manual_scheduler_debouncer(monkeypatch: pytest.MonkeyPatch):
    _ManualDebouncer.instances.clear()
    monkeypatch.setattr(scheduler_module, "QueuedDebouncer", _ManualDebouncer)
    yield
    _ManualDebouncer.instances.clear()


def test_scheduler_coalesces_requests_and_preserves_latest_param_trigger() -> None:
    seen: list[RenderRequest] = []
    scheduler = FigureRenderScheduler(seen.append, execute_every_ms=16)

    scheduler.request("manual")
    scheduler.request("param_change", trigger={"new": 2.0})
    scheduler.request("param_change", trigger={"new": 4.0})

    assert scheduler.has_pending is True
    scheduler.flush()

    assert len(seen) == 1
    request = seen[0]
    assert request.reason == "param_change"
    assert request.trigger == {"new": 4.0}
    assert request.queued_count == 3
    assert request.includes_param_change is True
    assert request.latest_param_change_trigger == {"new": 4.0}
    assert scheduler.has_pending is False


def test_scheduler_force_dispatches_immediately() -> None:
    seen: list[RenderRequest] = []
    scheduler = FigureRenderScheduler(seen.append, execute_every_ms=16)

    scheduler.request("manual", force=True)

    assert len(seen) == 1
    assert seen[0].reason == "manual"
    assert seen[0].queued_count == 1
    assert scheduler.has_pending is False


def test_scheduler_reschedules_request_added_during_dispatch() -> None:
    seen: list[str] = []
    scheduler: FigureRenderScheduler | None = None

    def _dispatch(request: RenderRequest) -> None:
        nonlocal scheduler
        seen.append(request.reason)
        if request.reason == "first":
            assert scheduler is not None
            scheduler.request("second")

    scheduler = FigureRenderScheduler(_dispatch, execute_every_ms=16)

    scheduler.request("first", force=True)

    assert seen == ["first"]
    assert scheduler.has_pending is True
    assert len(_ManualDebouncer.instances) == 1

    _ManualDebouncer.instances[0].fire()

    assert seen == ["first", "second"]
    assert scheduler.has_pending is False
