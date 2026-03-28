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


def _decode_pcm16_samples(payload: str) -> np.ndarray:
    return _decode_pcm16_base64(payload).astype(np.float64) / 32767.0


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


def test_sound_generation_is_available_by_default_and_row_button_is_visible() -> None:
    fig, _plot, row = _make_single_plot_figure(sp.sin(sp.symbols("x")))

    assert fig.sound_generation_enabled() is True
    assert row.sound_button.layout.display == "inline-flex"
    assert row.sound_button.tooltip == "Play sound for plot wave"
    assert fig._legend._context_bridge.sound_enabled is True


def test_legacy_sound_generation_toggles_do_not_hide_controls_and_false_stops_playback() -> None:
    fig, plot, row = _make_single_plot_figure(_constant_expr(0.25))
    messages = _capture_bridge_messages(fig._sound)

    plot.sound(run=True)
    assert fig._sound.active_plot_id == plot.id

    assert fig.sound_generation_enabled(False) is True
    assert fig._sound.active_plot_id is None
    assert messages[-1]["action"] == "stop"
    assert row.sound_button.layout.display == "inline-flex"
    assert fig._legend._context_bridge.sound_enabled is True

    fig._legend._context_bridge._emit_msg(
        {
            "type": "legend_context_request",
            "action": "set_sound_enabled",
            "enabled": False,
        }
    )

    assert fig.sound_generation_enabled() is True
    assert row.sound_button.layout.display == "inline-flex"
    assert fig._legend._context_bridge.sound_enabled is True


def test_plot_sound_start_restart_and_stop_update_manager_and_legend_state() -> None:
    fig, plot, row = _make_single_plot_figure(_constant_expr(0.25))
    messages = _capture_bridge_messages(fig._sound)

    fig.sound_generation_enabled(True)
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

    fig.sound_generation_enabled(True)
    first.sound(run=True)
    second.sound(run=True)

    assert fig._sound.active_plot_id == "second"
    assert messages[-1]["action"] == "start"
    assert messages[-1]["plot_id"] == "second"
    assert "mod-muted" in fig._legend._rows["first"].sound_button._dom_classes
    assert "mod-playing" in fig._legend._rows["second"].sound_button._dom_classes


def test_chunk_request_uses_point_one_second_pcm_chunks_and_advances_cursor() -> None:
    fig, plot, _row = _make_single_plot_figure(_constant_expr(0.25))
    messages = _capture_bridge_messages(fig._sound)

    fig.sound_generation_enabled(True)
    plot.sound(run=True)
    start_message = messages[-1]
    token = start_message["token"]

    fig._sound._bridge._emit_msg(
        {
            "type": "sound_stream_request",
            "action": "request_chunk",
            "token": token,
            "cursor_seconds": 0.0,
            "sample_rate": 48_000,
            "batch_chunks": 1,
        }
    )

    chunk_message = messages[-1]
    pcm = _decode_pcm16_base64(chunk_message["pcm_base64"])

    assert chunk_message["action"] == "chunk"
    assert chunk_message["sample_rate"] == 48_000
    assert chunk_message["frame_count"] == 4800
    assert chunk_message["chunk_start_seconds"] == 0.0
    assert pcm.shape == (4800,)
    assert int(pcm[0]) == pytest.approx(int(0.25 * 32767), abs=1)
    assert np.all(pcm == pcm[0])
    assert fig._sound._cursor_seconds == pytest.approx(0.1)


def test_default_chunk_requests_return_a_prefetched_batch() -> None:
    fig, plot, _row = _make_single_plot_figure(_constant_expr(0.25))
    messages = _capture_bridge_messages(fig._sound)

    plot.sound(run=True)
    start_token = messages[-1]["token"]

    fig._sound._bridge._emit_msg(
        {
            "type": "sound_stream_request",
            "action": "request_chunk",
            "token": start_token,
            "cursor_seconds": 0.0,
            "sample_rate": 48_000,
        }
    )

    batch_message = messages[-1]
    assert batch_message["action"] == "chunk_batch"
    assert len(batch_message["chunks"]) == fig._sound.prefetch_chunks
    assert [chunk["frame_count"] for chunk in batch_message["chunks"]] == [4800] * 5
    assert [chunk["chunk_start_seconds"] for chunk in batch_message["chunks"]] == pytest.approx(
        [0.0, 0.1, 0.2, 0.3, 0.4]
    )
    assert fig._sound._cursor_seconds == pytest.approx(0.5)


def test_parameter_change_requests_audio_refresh_and_new_chunks_use_latest_value() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    fig.parameter(a, value=0.25, min=-1, max=1)
    plot = fig.plot(a + sp.Integer(0) * x, x, id="parametric", label="parametric", parameters=[a])
    messages = _capture_bridge_messages(fig._sound)

    fig.sound_generation_enabled(True)
    plot.sound(run=True)
    start_token = messages[-1]["token"]

    fig._sound._bridge._emit_msg(
        {
            "type": "sound_stream_request",
            "action": "request_chunk",
            "token": start_token,
            "cursor_seconds": 10.0,
            "sample_rate": 48_000,
            "batch_chunks": 1,
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
            "sample_rate": 48_000,
            "batch_chunks": 1,
        }
    )
    second_pcm = _decode_pcm16_base64(messages[-1]["pcm_base64"])
    assert int(second_pcm[0]) == pytest.approx(int(0.5 * 32767), abs=1)


def test_phase_continuity_fuses_first_chunk_after_parameter_change() -> None:
    x, phase = sp.symbols("x phase")
    fig = Figure()
    fig.parameter(phase, value=0.0, min=-10, max=10)
    plot = fig.plot(
        sp.sin(40 * sp.pi * x + phase),
        x,
        id="phase_wave",
        label="phase_wave",
        parameters=[phase],
    )
    messages = _capture_bridge_messages(fig._sound)

    plot.sound(run=True)
    start_token = messages[-1]["token"]

    fig._sound._bridge._emit_msg(
        {
            "type": "sound_stream_request",
            "action": "request_chunk",
            "token": start_token,
            "cursor_seconds": 0.0,
            "sample_rate": 48_000,
            "batch_chunks": 1,
        }
    )
    first_chunk = messages[-1]
    first_samples = _decode_pcm16_samples(first_chunk["pcm_base64"])

    fig.parameters[phase].value = float(sp.pi / 2)
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
            "cursor_seconds": 0.1,
            "sample_rate": 48_000,
            "batch_chunks": 1,
        }
    )
    transitioned_chunk = messages[-1]
    transitioned_samples = _decode_pcm16_samples(transitioned_chunk["pcm_base64"])

    boundary_jump = abs(float(transitioned_samples[0] - first_samples[-1]))
    naive_jump = abs(float(np.sin(40.0 * np.pi * 0.1 + np.pi / 2) - first_samples[-1]))

    assert boundary_jump < 0.05
    assert boundary_jump < naive_jump * 0.1
    assert transitioned_samples[1] > transitioned_samples[0]
    assert fig._sound._phase_offset_seconds != pytest.approx(0.0, abs=1.0e-6)


def test_out_of_range_sound_expression_opens_modal_error_dialog() -> None:
    fig, plot, row = _make_single_plot_figure(_constant_expr(2.0), plot_id="too_loud")
    messages = _capture_bridge_messages(fig._sound)
    fig.sound_generation_enabled(True)

    plot.sound(run=True)

    assert messages == []
    assert fig._sound.active_plot_id is None
    assert fig._sound._error_open is True
    assert fig._sound._error_panel.layout.display == "flex"
    assert fig._sound._error_modal.layout.display == "flex"
    assert fig._sound._error_bridge.dialog_open is True
    assert "within [-1, 1]" in fig._sound._error_message.value
    assert row.sound_button.layout.display == "inline-flex"
    assert "mod-muted" in row.sound_button._dom_classes


def test_runtime_refresh_error_stops_playback_and_opens_modal_error_dialog() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    fig.parameter(a, value=0.5, min=-2, max=2)
    plot = fig.plot(a + sp.Integer(0) * x, x, id="parametric", label="parametric", parameters=[a])
    messages = _capture_bridge_messages(fig._sound)

    plot.sound(run=True)
    start_token = messages[-1]["token"]
    fig._sound._bridge._emit_msg(
        {
            "type": "sound_stream_request",
            "action": "request_chunk",
            "token": start_token,
            "cursor_seconds": 0.0,
            "sample_rate": 48_000,
            "batch_chunks": 1,
        }
    )
    assert messages[-1]["action"] == "chunk"

    fig.parameters[a].value = 1.5
    fig.flush_render_queue()
    refresh_message = messages[-1]
    assert refresh_message["action"] == "refresh"

    fig._sound._bridge._emit_msg(
        {
            "type": "sound_stream_request",
            "action": "request_chunk",
            "token": refresh_message["token"],
            "cursor_seconds": 0.1,
            "sample_rate": 48_000,
            "batch_chunks": 1,
        }
    )

    error_message = messages[-1]
    assert error_message["action"] == "error"
    assert "within [-1, 1]" in error_message["message"]
    assert fig._sound.active_plot_id is None
    assert fig._sound._error_open is True
    assert "mod-muted" in fig._legend._rows["parametric"].sound_button._dom_classes


def test_row_sound_button_click_uses_plot_sound_semantics() -> None:
    fig, _plot, row = _make_single_plot_figure(_constant_expr(0.125))
    messages = _capture_bridge_messages(fig._sound)
    fig.sound_generation_enabled(True)

    row.sound_button.click()
    assert messages[-1]["action"] == "start"
    assert fig._sound.active_plot_id == "wave"

    row.sound_button.click()
    assert messages[-1]["action"] == "stop"
    assert fig._sound.active_plot_id is None
