from __future__ import annotations

import logging
from contextlib import contextmanager

from gu_toolkit import Figure


@contextmanager
def _enabled_layout_logging():
    layout_logger = logging.getLogger("gu_toolkit.layout")
    old_level = layout_logger.level
    try:
        layout_logger.setLevel(logging.DEBUG)
        yield
    finally:
        layout_logger.setLevel(old_level)




def test_figure_layout_debug_is_disabled_by_default() -> None:
    fig = Figure()

    assert fig._layout_debug_enabled is False
    assert fig._layout_event_buffer.snapshot() == []

def test_request_active_view_reflow_emits_reason_and_request_id() -> None:
    with _enabled_layout_logging():
        fig = Figure()
    calls: list[dict[str, object]] = []

    def _fake_reflow(**kwargs):
        calls.append(dict(kwargs))

    fig.views.current.pane.reflow = _fake_reflow  # type: ignore[method-assign]

    fig._request_active_view_reflow("sidebar_visibility")

    assert calls
    assert calls[0]["reason"] == "sidebar_visibility"
    assert isinstance(calls[0]["request_id"], str)
    assert calls[0]["request_id"].startswith("req-")

    events = fig._layout_event_buffer.snapshot()
    reflow_events = [event for event in events if event["event"] == "reflow_requested"]
    assert reflow_events
    assert reflow_events[-1]["reason"] == "sidebar_visibility"
    assert reflow_events[-1]["request_id"] == calls[0]["request_id"]


def test_sidebar_visibility_logging_changed_vs_unchanged() -> None:
    with _enabled_layout_logging():
        fig = Figure()

    changed = fig._layout.update_sidebar_visibility(False, False, True)
    unchanged = fig._layout.update_sidebar_visibility(False, False, True)
    changed_again = fig._layout.update_sidebar_visibility(True, False, True)

    assert changed is False
    assert unchanged is False
    assert changed_again is True

    events = fig._layout_event_buffer.snapshot()
    names = [event["event"] for event in events]
    assert "sidebar_visibility_unchanged" in names
    assert "sidebar_visibility_changed" in names


def test_public_reflow_layout_routes_to_named_view() -> None:
    with _enabled_layout_logging():
        fig = Figure()
    detail = fig.add_view("detail")
    calls: list[dict[str, object]] = []

    def _fake_reflow(**kwargs):
        calls.append(dict(kwargs))

    detail.pane.reflow = _fake_reflow  # type: ignore[method-assign]

    request_id = fig.reflow_layout(reason="manual_check", view_id="detail")

    assert isinstance(request_id, str)
    assert request_id.startswith("req-")
    assert calls
    assert calls[0]["reason"] == "manual_check"
    assert calls[0]["view_id"] == "detail"
    assert calls[0]["request_id"] == request_id

    events = fig._layout_event_buffer.snapshot()
    reflow_events = [event for event in events if event["event"] == "reflow_requested"]
    assert reflow_events
    assert reflow_events[-1]["view_id"] == "detail"
    assert reflow_events[-1]["request_id"] == request_id
