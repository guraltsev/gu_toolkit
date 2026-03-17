from __future__ import annotations

from gu_toolkit.layout_logging import LayoutEventBuffer, emit_layout_event, make_event_emitter, new_request_id


def test_request_id_generation_is_stable_and_prefixed() -> None:
    first = new_request_id()
    second = new_request_id()

    assert first.startswith("req-")
    assert second.startswith("req-")
    assert first != second


def test_buffer_insertion_and_truncation() -> None:
    buffer = LayoutEventBuffer(maxlen=2)
    emitter = make_event_emitter(__import__("logging").getLogger("gu_toolkit.layout.test"), buffer=buffer)

    emitter(event="one", source="test", phase="completed")
    emitter(event="two", source="test", phase="completed")
    emitter(event="three", source="test", phase="completed")

    events = buffer.snapshot()
    assert [event["event"] for event in events] == ["two", "three"]


def test_emit_layout_event_flattens_nested_size_fields() -> None:
    payload = emit_layout_event(
        __import__("logging").getLogger("gu_toolkit.layout.test"),
        event="geometry_measured",
        source="test",
        phase="measured",
        sizes={"host_w": 100, "host_h": 200},
        view_id="main",
    )

    assert payload["sizes_host_w"] == 100
    assert payload["sizes_host_h"] == 200
    assert payload["view_id"] == "main"
