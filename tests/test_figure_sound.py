from __future__ import annotations

import base64
from typing import Any

import numpy as np
import pytest
import sympy as sp

from gu_toolkit import Figure


def _capture_bridge_messages(sound_manager: Any) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    def _record(payload: dict[str, Any], *_args: Any, **_kwargs: Any) -> None:
        messages.append(dict(payload))

    sound_manager._bridge.send = _record  # type: ignore[method-assign]
    return messages


def _decode_pcm16_base64(payload: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(payload.encode("ascii")), dtype=np.int16)


def _constant_expr(value: float | sp.Expr) -> sp.Expr:
    x = sp.symbols("x")
    return sp.Add(
        sp.sympify(value),
        sp.Mul(sp.Integer(0), x, evaluate=False),
        evaluate=False,
    )


def _make_single_plot_figure(expr: Any, *, plot_id: str = "wave") -> tuple[Figure, Any, Any]:
    x = sp.symbols("x")
    fig = Figure()
    plot = fig.plot(expr, x, id=plot_id, label=plot_id)
    row = fig._legend._rows[plot_id]
    return fig, plot, row


def test_sound_generation_is_enabled_by_default_and_row_button_is_visible() -> None:
    fig, _plot, row = _make_single_plot_figure(sp.sin(sp.symbols("x")))

    assert fig.sound_generation_enabled() is True
    assert row.sound_button.layout.display == "inline-flex"
    assert fig._legend._context_bridge.sound_enabled is True


def test_context_menu_sound_toggle_updates_figure_state_and_row_visibility() -> None:
    fig, _plot, row = _make_single_plot_figure(sp.sin(sp.symbols("x")))

    assert fig.sound_generation_enabled() is True
    assert row.sound_button.layout.display == "inline-flex"

    fig._legend._context_bridge._emit_msg(
        {
            "type": "legend_context_request",
            "action": "set_sound_enabled",
            "enabled": False,
        }
    )

    assert fig.sound_generation_enabled() is False
    assert row.sound_button.layout.display == "none"

    fig._legend._context_bridge._emit_msg(
        {
            "type": "legend_context_request",
            "action": "set_sound_enabled",
            "enabled": True,
        }
    )

    assert fig.sound_generation_enabled() is True
    assert row.sound_button.layout.display == "inline-flex"
    assert row.sound_button.tooltip == "Play sound for plot wave"


def test_plot_sound_start_restart_and_stop_update_manager_and_legend_state() -> None:
    fig, plot, row = _make_single_plot_figure(_constant_expr(0.25))
    messages = _capture_bridge_messages(fig._sound)

    plot.sound(run=True)

    assert fig._sound.active_plot_id == plot.id
    assert messages[-1]["action"] == "start"
    first_token = messages[-1]["token"]
    assert first_token >= 1
    assert "mod-playing" in row.sound_button._dom_classes

    plot.sound(run=True)

    assert fig._sound.active_plot_id == plot.id
    assert messages[-1]["action"] == "start"
    assert messages[-1]["token"] == first_token + 1
    assert messages[-1]["cursor_seconds"] == 0.0

    plot.sound(run=False)

    assert fig._sound.active_plot_id is None
    assert messages[-1]["action"] == "stop"
    assert "mod-muted" in row.sound_button._dom_classes


def test_starting_a_second_plot_switches_the_active_sound_row() -> None:
    x = sp.symbols("x")
    fig = Figure()
    first = fig.plot(_constant_expr(0.1), x, id="first", label="first")
    second = fig.plot(_constant_expr(0.2), x, id="second", label="second")
    messages = _capture_bridge_messages(fig._sound)

    first.sound(run=True)
    second.sound(run=True)

    assert fig._sound.active_plot_id == "second"
    assert messages[-1]["action"] == "start"
    assert messages[-1]["plot_id"] == "second"
    assert "mod-muted" in fig._legend._rows["first"].sound_button._dom_classes
    assert "mod-playing" in fig._legend._rows["second"].sound_button._dom_classes


def test_chunk_request_uses_one_second_pcm_chunks_and_advances_cursor() -> None:
    fig, plot, _row = _make_single_plot_figure(_constant_expr(0.25))
    messages = _capture_bridge_messages(fig._sound)

    plot.sound(run=True)
    start_message = messages[-1]
    token = start_message["token"]

    fig._sound._bridge._emit_msg(
        {
            "type": "sound_stream_request",
            "action": "request_chunk",
            "token": token,
            "cursor_seconds": 0.0,
        }
    )

    chunk_message = messages[-1]
    pcm = _decode_pcm16_base64(chunk_message["pcm_base64"])

    assert chunk_message["action"] == "chunk"
    assert chunk_message["frame_count"] == 44100
    assert chunk_message["chunk_start_seconds"] == 0.0
    assert pcm.shape == (44100,)
    assert int(pcm[0]) == pytest.approx(int(0.25 * 32767), abs=1)
    assert np.all(pcm == pcm[0])
    assert fig._sound._cursor_seconds == pytest.approx(1.0)


def test_parameter_change_requests_audio_refresh_and_new_chunks_use_latest_value() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    fig.parameter(a, value=0.25, min=-1, max=1)
    plot = fig.plot(a + sp.Integer(0) * x, x, id="parametric", label="parametric", parameters=[a])
    messages = _capture_bridge_messages(fig._sound)

    plot.sound(run=True)
    start_token = messages[-1]["token"]

    fig._sound._bridge._emit_msg(
        {
            "type": "sound_stream_request",
            "action": "request_chunk",
            "token": start_token,
            "cursor_seconds": 10.0,
        }
    )
    first_pcm = _decode_pcm16_base64(messages[-1]["pcm_base64"])
    assert int(first_pcm[0]) == pytest.approx(int(0.25 * 32767), abs=1)

    fig.parameters[a].value = 0.5
    fig.flush_render_queue()

    refresh_message = messages[-1]
    assert refresh_message["action"] == "refresh"
    refresh_token = refresh_message["token"]
    assert refresh_token > start_token

    fig._sound._bridge._emit_msg(
        {
            "type": "sound_stream_request",
            "action": "request_chunk",
            "token": refresh_token,
            "cursor_seconds": 10.0,
        }
    )
    second_pcm = _decode_pcm16_base64(messages[-1]["pcm_base64"])
    assert int(second_pcm[0]) == pytest.approx(int(0.5 * 32767), abs=1)


def test_out_of_range_sound_expression_raises_without_auto_normalization() -> None:
    fig, plot, row = _make_single_plot_figure(_constant_expr(2.0), plot_id="too_loud")
    _capture_bridge_messages(fig._sound)

    with pytest.raises(ValueError, match=r"within \[-1, 1\]"):
        plot.sound(run=True)

    assert fig._sound.active_plot_id is None
    assert "mod-muted" in row.sound_button._dom_classes


def test_autonormalization_scales_loud_chunks_automatically() -> None:
    fig, plot, _row = _make_single_plot_figure(_constant_expr(2.0), plot_id="too_loud")
    messages = _capture_bridge_messages(fig._sound)

    assert plot.autonormalization() is False
    plot.autonormalization(True)
    assert plot.autonormalization() is True

    plot.sound(run=True)
    token = messages[-1]["token"]

    fig._sound._bridge._emit_msg(
        {
            "type": "sound_stream_request",
            "action": "request_chunk",
            "token": token,
            "cursor_seconds": 0.0,
        }
    )

    chunk_message = messages[-1]
    pcm = _decode_pcm16_base64(chunk_message["pcm_base64"])

    assert chunk_message["action"] == "chunk"
    assert np.max(np.abs(pcm)) == pytest.approx(32767, abs=1)
    assert fig._sound.active_plot_id == "too_loud"


def test_row_sound_button_click_uses_plot_sound_semantics() -> None:
    fig, _plot, row = _make_single_plot_figure(_constant_expr(0.125))
    messages = _capture_bridge_messages(fig._sound)

    row.sound_button.click()
    assert messages[-1]["action"] == "start"
    assert fig._sound.active_plot_id == "wave"

    row.sound_button.click()
    assert messages[-1]["action"] == "stop"
    assert fig._sound.active_plot_id is None
