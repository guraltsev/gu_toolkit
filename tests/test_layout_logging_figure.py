from __future__ import annotations

from gu_toolkit import Figure


def test_request_active_view_reflow_emits_reason_and_request_id(monkeypatch) -> None:
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
    fig = Figure()

    changed = fig._layout.update_sidebar_visibility(False, False, False)
    unchanged = fig._layout.update_sidebar_visibility(False, False, False)
    changed_again = fig._layout.update_sidebar_visibility(True, False, False)

    assert changed is False
    assert unchanged is False
    assert changed_again is True

    events = fig._layout_event_buffer.snapshot()
    names = [event["event"] for event in events]
    assert "sidebar_visibility_unchanged" in names
    assert "sidebar_visibility_changed" in names
