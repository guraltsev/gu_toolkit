"""General-purpose queued debouncing helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Optional, Tuple
import asyncio
import threading
import warnings


@dataclass
class _QueuedCall:
    args: Tuple[Any, ...]
    kwargs: dict[str, Any]


class QueuedDebouncer:
    """Queue callback invocations and execute at a fixed cadence.

    Parameters
    ----------
    callback:
        Callable to execute from queued events.
    execute_every_ms:
        Execution cadence in milliseconds.
    drop_overflow:
        If ``True``, each tick keeps only the last queued event before executing.
    """

    def __init__(
        self,
        callback: Callable[..., Any],
        *,
        execute_every_ms: int,
        drop_overflow: bool = True,
    ) -> None:
        if execute_every_ms <= 0:
            raise ValueError("execute_every_ms must be > 0")
        self._callback = callback
        self._execute_every_s = execute_every_ms / 1000.0
        self._drop_overflow = bool(drop_overflow)

        self._queue: Deque[_QueuedCall] = deque()
        self._lock = threading.Lock()
        self._timer: Optional[Any] = None

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self._queue.append(_QueuedCall(args=args, kwargs=dict(kwargs)))
            if self._timer is None:
                self._schedule_next_locked()

    def _schedule_next_locked(self) -> None:
        delay_s = self._execute_every_s
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
        call: Optional[_QueuedCall] = None

        with self._lock:
            self._timer = None
            if not self._queue:
                return

            if self._drop_overflow and len(self._queue) > 1:
                last = self._queue[-1]
                self._queue.clear()
                self._queue.append(last)

            call = self._queue.popleft()
            if self._queue:
                self._schedule_next_locked()

        try:
            self._callback(*call.args, **call.kwargs)
        except Exception as exc:  # pragma: no cover - defensive callback boundary
            warnings.warn(f"QueuedDebouncer callback failed: {exc}")
