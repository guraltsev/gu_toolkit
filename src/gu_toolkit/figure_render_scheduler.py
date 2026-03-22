"""Figure-level render scheduling and request coalescing.

Purpose
-------
Owns the figure-level policy that batches hot render triggers to roughly one
render per animation frame (~60 Hz). The scheduler is intentionally small and
transport-neutral so :class:`gu_toolkit.Figure.Figure` can keep orchestration
logic focused on plotting concerns rather than timer bookkeeping.

Design contract
---------------
- ``request(..., force=False)`` stores or merges a pending render request and
  schedules one debounced dispatch.
- ``request(..., force=True)`` merges the request and attempts to dispatch the
  newest pending state synchronously.
- Coalescing preserves the *latest* ``reason`` / ``trigger`` for observability
  while also remembering whether any queued request represented a parameter
  change. This lets the figure keep hook and stale-view semantics intact even
  when multiple requests collapse into one actual render.
- The callback boundary is resilient: dispatch exceptions are logged, pending
  requests remain schedulable, and later requests can still execute.

Why a dedicated module?
-----------------------
Historically ``Figure.render()`` executed synchronously and directly. With a
60 Hz batching target the render path now has enough policy (coalescing,
forced flushes, re-entrancy handling, logging) to justify a focused helper.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable

from .debouncing import QueuedDebouncer
from .layout_logging import (
    LOGGER_NAME,
    emit_layout_event,
    is_layout_logger_explicitly_enabled,
)


@dataclass(frozen=True)
class RenderRequest:
    """Immutable description of one dispatched figure render.

    Parameters
    ----------
    reason : str
        Most recent render reason merged into the dispatched request.
    trigger : Any, optional
        Payload associated with the most recent render reason.
    queued_count : int, default=1
        Number of requests coalesced into this dispatch.
    includes_param_change : bool, default=False
        Whether any queued request had ``reason == 'param_change'``.
    latest_param_change_trigger : Any, optional
        Trigger payload from the most recent parameter-change request in the
        batch. This is the payload forwarded to parameter hooks.
    """

    reason: str
    trigger: Any = None
    queued_count: int = 1
    includes_param_change: bool = False
    latest_param_change_trigger: Any = None


@dataclass
class _PendingRenderRequest:
    """Mutable coalescing state used internally by the scheduler."""

    reason: str
    trigger: Any = None
    queued_count: int = 1
    includes_param_change: bool = False
    latest_param_change_trigger: Any = None

    @classmethod
    def from_request(cls, *, reason: str, trigger: Any = None) -> _PendingRenderRequest:
        includes_param_change = str(reason) == "param_change"
        return cls(
            reason=str(reason),
            trigger=trigger,
            queued_count=1,
            includes_param_change=includes_param_change,
            latest_param_change_trigger=(trigger if includes_param_change else None),
        )

    def merge(self, *, reason: str, trigger: Any = None) -> None:
        """Merge a newly requested render into the pending dispatch state."""
        self.reason = str(reason)
        self.trigger = trigger
        self.queued_count += 1
        if str(reason) == "param_change":
            self.includes_param_change = True
            self.latest_param_change_trigger = trigger

    def freeze(self) -> RenderRequest:
        """Return an immutable snapshot of the pending dispatch state."""
        return RenderRequest(
            reason=self.reason,
            trigger=self.trigger,
            queued_count=self.queued_count,
            includes_param_change=self.includes_param_change,
            latest_param_change_trigger=self.latest_param_change_trigger,
        )


class FigureRenderScheduler:
    """Coalesce figure render requests and dispatch them on a fixed cadence.

    Parameters
    ----------
    dispatch_callback : callable
        Synchronous callback receiving one :class:`RenderRequest` whenever a
        queued render should be executed.
    execute_every_ms : int, default=16
        Dispatch cadence in milliseconds. ``16`` targets roughly 60 Hz.
    name : str, default="Figure.render"
        Human-readable owner name used in debug logging.
    event_sink : callable, optional
        Optional structured layout-log sink matching the signature used by
        :class:`gu_toolkit.debouncing.QueuedDebouncer`.
    """

    def __init__(
        self,
        dispatch_callback: Callable[[RenderRequest], Any],
        *,
        execute_every_ms: int = 16,
        name: str = "Figure.render",
        event_sink: Callable[..., Any] | None = None,
    ) -> None:
        if execute_every_ms <= 0:
            raise ValueError("execute_every_ms must be > 0")
        self._dispatch_callback = dispatch_callback
        self._name = str(name)
        self._event_sink = event_sink
        self._lock = threading.Lock()
        self._pending: _PendingRenderRequest | None = None
        self._dispatching = False
        self._debouncer = QueuedDebouncer(
            self._dispatch_from_tick,
            execute_every_ms=execute_every_ms,
            drop_overflow=True,
            name=self._name,
            event_sink=event_sink,
        )

    def _emit(
        self,
        event: str,
        *,
        phase: str,
        level: int = logging.DEBUG,
        **fields: Any,
    ) -> None:
        if self._event_sink is not None:
            self._event_sink(
                event=event,
                source="FigureRenderScheduler",
                phase=phase,
                level=level,
                owner=self._name,
                **fields,
            )
            return
        scheduler_logger = logging.getLogger(f"{LOGGER_NAME}.render")
        if not is_layout_logger_explicitly_enabled(scheduler_logger):
            return
        emit_layout_event(
            scheduler_logger,
            event=event,
            source="FigureRenderScheduler",
            phase=phase,
            level=level,
            owner=self._name,
            **fields,
        )

    @property
    def has_pending(self) -> bool:
        """Whether a render request is currently waiting to be dispatched."""
        with self._lock:
            return self._pending is not None

    def request(self, reason: str, trigger: Any = None, *, force: bool = False) -> None:
        """Queue or immediately flush a render request.

        Parameters
        ----------
        reason : str
            Render reason string.
        trigger : Any, optional
            Associated event payload.
        force : bool, default=False
            If ``True``, attempt to dispatch the coalesced pending request
            synchronously after merging this request. If a dispatch is already
            in progress, the request is preserved and will run on the next tick.
        """
        with self._lock:
            if self._pending is None:
                self._pending = _PendingRenderRequest.from_request(
                    reason=reason,
                    trigger=trigger,
                )
            else:
                self._pending.merge(reason=reason, trigger=trigger)
            snapshot = self._pending.freeze()
            dispatching = self._dispatching

        self._emit(
            "render_request_queued",
            phase="queued",
            level=logging.INFO,
            reason=snapshot.reason,
            queued_count=snapshot.queued_count,
            includes_param_change=snapshot.includes_param_change,
            force=bool(force),
            trigger_type=(type(snapshot.trigger).__name__ if snapshot.trigger is not None else None),
        )

        if not dispatching:
            self._debouncer()

        if force:
            self.flush()

    def flush(self) -> None:
        """Synchronously dispatch the newest pending request, if any."""
        self._dispatch_once(origin="flush")

    def _dispatch_from_tick(self) -> None:
        """Dispatch the newest pending request from the debounced tick."""
        self._dispatch_once(origin="tick")

    def _dispatch_once(self, *, origin: str) -> None:
        request: RenderRequest | None = None
        with self._lock:
            if self._dispatching:
                self._emit(
                    "render_request_dispatch_skipped",
                    phase="skipped",
                    origin=origin,
                    outcome="already_dispatching",
                )
                return
            if self._pending is None:
                self._emit(
                    "render_request_dispatch_skipped",
                    phase="skipped",
                    origin=origin,
                    outcome="no_pending_request",
                )
                return
            request = self._pending.freeze()
            self._pending = None
            self._dispatching = True

        self._emit(
            "render_request_dispatch_started",
            phase="started",
            level=logging.INFO,
            origin=origin,
            reason=request.reason,
            queued_count=request.queued_count,
            includes_param_change=request.includes_param_change,
            trigger_type=(type(request.trigger).__name__ if request.trigger is not None else None),
        )

        failed = False
        try:
            self._dispatch_callback(request)
        except Exception:  # pragma: no cover - defensive callback boundary
            failed = True
            self._emit(
                "render_request_dispatch_failed",
                phase="failed",
                origin=origin,
                level=logging.ERROR,
            )
            logging.getLogger(__name__).exception(
                "FigureRenderScheduler dispatch failed"
            )
        finally:
            with self._lock:
                self._dispatching = False
                needs_reschedule = self._pending is not None

        if not failed:
            self._emit(
                "render_request_dispatch_completed",
                phase="completed",
                level=logging.INFO,
                origin=origin,
                reason=request.reason,
                queued_count=request.queued_count,
                includes_param_change=request.includes_param_change,
            )

        if needs_reschedule:
            self._emit(
                "render_request_rescheduled",
                phase="scheduled",
                origin=origin,
            )
            self._debouncer()


__all__ = ["FigureRenderScheduler", "RenderRequest"]
