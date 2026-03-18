"""Queued debouncing utilities for callback-driven UI updates.

Purpose
-------
Provides ``QueuedDebouncer``, a small utility that buffers callback invocations
and executes them on a fixed cadence.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .layout_logging import LOGGER_NAME, emit_layout_event, is_layout_logger_explicitly_enabled


@dataclass
class _QueuedCall:
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class QueuedDebouncer:
    """Queue callback invocations and execute at a fixed cadence."""

    def __init__(
        self,
        callback: Callable[..., Any],
        *,
        execute_every_ms: int,
        drop_overflow: bool = True,
        name: str = "QueuedDebouncer",
        event_sink: Callable[..., Any] | None = None,
    ) -> None:
        if execute_every_ms <= 0:
            raise ValueError("execute_every_ms must be > 0")
        self._callback = callback
        self._execute_every_s = execute_every_ms / 1000.0
        self._drop_overflow = bool(drop_overflow)
        self._name = str(name)
        self._event_sink = event_sink

        self._queue: deque[_QueuedCall] = deque()
        self._lock = threading.Lock()
        self._timer: Any | None = None

    def _emit(self, event: str, *, phase: str, level: int = logging.DEBUG, **fields: Any) -> None:
        if self._event_sink is not None:
            self._event_sink(event=event, source="QueuedDebouncer", phase=phase, level=level, owner=self._name, **fields)
            return
        debounce_logger = logging.getLogger(f"{LOGGER_NAME}.debounce")
        if not is_layout_logger_explicitly_enabled(debounce_logger):
            return
        emit_layout_event(
            debounce_logger,
            event=event,
            source="QueuedDebouncer",
            phase=phase,
            level=level,
            owner=self._name,
            **fields,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self._queue.append(_QueuedCall(args=args, kwargs=dict(kwargs)))
            self._emit("debounce_enqueued", phase="queued", queue_depth=len(self._queue))
            if self._timer is None:
                self._schedule_next_locked()

    def _schedule_next_locked(self) -> None:
        delay_s = self._execute_every_s
        self._emit("debounce_tick_scheduled", phase="scheduled", delay_ms=int(delay_s * 1000), queue_depth=len(self._queue))
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            timer = threading.Timer(delay_s, self._on_tick)
            timer.daemon = True
            self._timer = timer
            timer.start()
            return

        self._timer = loop.call_later(delay_s, self._on_tick)

    def _on_tick(self) -> None:
        call: _QueuedCall | None = None
        remaining = 0

        with self._lock:
            self._timer = None
            if not self._queue:
                return

            if self._drop_overflow and len(self._queue) > 1:
                dropped = len(self._queue) - 1
                last = self._queue[-1]
                self._queue.clear()
                self._queue.append(last)
                self._emit("debounce_drop_overflow", phase="queued", dropped_count=dropped)

            call = self._queue.popleft()
            remaining = len(self._queue)
            if self._queue:
                self._schedule_next_locked()

        self._emit("debounce_tick_started", phase="started", queue_depth=remaining + 1)
        try:
            self._callback(*call.args, **call.kwargs)
        except Exception:  # pragma: no cover - defensive callback boundary
            self._emit("debounce_tick_failed", phase="failed", level=logging.ERROR)
            logging.getLogger(__name__).exception("QueuedDebouncer callback failed")
        else:
            self._emit("debounce_tick_completed", phase="completed", queue_depth=remaining)
