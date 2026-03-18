from __future__ import annotations

import itertools
import logging
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

LOGGER_NAME = "gu_toolkit.layout"
logger = logging.getLogger(LOGGER_NAME)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

_layout_id_counter = itertools.count(1)
_request_counter = itertools.count(1)


@dataclass
class LayoutEventBuffer:
    maxlen: int = 500
    events: deque[dict[str, Any]] = field(default_factory=deque)

    def append(self, payload: dict[str, Any]) -> None:
        if self.events.maxlen != self.maxlen:
            self.events = deque(self.events, maxlen=self.maxlen)
        self.events.append(dict(payload))

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self.events)



def new_debug_id(prefix: str) -> str:
    return f"{prefix}-{next(_layout_id_counter):04d}-{uuid.uuid4().hex[:6]}"



def new_request_id() -> str:
    return f"req-{next(_request_counter):06d}"



def is_layout_logger_explicitly_enabled(logger_or_name: str | logging.Logger) -> bool:
    """Return whether layout instrumentation was explicitly enabled.

    Only logger levels configured on the ``gu_toolkit.layout`` hierarchy count.
    Inherited root-logger configuration is intentionally ignored so layout debug
    work stays off unless the caller opts in for this subsystem.
    """
    if isinstance(logger_or_name, logging.Logger):
        logger_obj = logger_or_name
    else:
        logger_obj = logging.getLogger(logger_or_name)

    while logger_obj is not None:
        name = logger_obj.name or ""
        if name in {"root", ""}:
            return False
        if name == LOGGER_NAME or name.startswith(f"{LOGGER_NAME}."):
            if logger_obj.level != logging.NOTSET:
                return logger_obj.level <= logging.INFO
            logger_obj = logger_obj.parent
            continue
        logger_obj = logger_obj.parent
    return False



def normalize_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, bool | int | float | str):
            payload[key] = value
        elif isinstance(value, Mapping):
            for sub_key, sub_val in value.items():
                payload[f"{key}_{sub_key}"] = sub_val
        elif isinstance(value, (list, tuple)):
            payload[key] = list(value)
        else:
            payload[key] = str(value)
    return payload



def emit_layout_event(
    logger: logging.Logger,
    *,
    event: str,
    source: str,
    phase: str,
    level: int = logging.DEBUG,
    buffer: LayoutEventBuffer | None = None,
    **fields: Any,
) -> dict[str, Any]:
    payload = {
        "ts": round(time.time(), 6),
        "event": event,
        "source": source,
        "phase": phase,
    }
    payload.update(normalize_fields(fields))
    if buffer is not None:
        buffer.append(payload)
    logger.log(level, "%s", payload)
    return payload



def make_event_emitter(
    logger: logging.Logger,
    *,
    buffer: LayoutEventBuffer | None = None,
    base_fields: Mapping[str, Any] | None = None,
    seq_factory: Callable[[], int] | None = None,
) -> Callable[..., dict[str, Any]]:
    base = dict(base_fields or {})

    def _emit(*, event: str, source: str, phase: str, level: int = logging.DEBUG, **fields: Any) -> dict[str, Any]:
        merged = dict(base)
        merged.update(fields)
        if seq_factory is not None and "seq" not in merged:
            merged["seq"] = seq_factory()
        return emit_layout_event(
            logger,
            event=event,
            source=source,
            phase=phase,
            level=level,
            buffer=buffer,
            **merged,
        )

    return _emit



def layout_value_snapshot(layout: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    snap: dict[str, Any] = {}
    if layout is None:
        return snap
    for field in fields:
        try:
            value = getattr(layout, field)
        except Exception:
            continue
        if value not in (None, ""):
            snap[field] = value
    return snap
