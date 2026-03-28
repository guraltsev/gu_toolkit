from __future__ import annotations

"""Figure-level streaming sound playback.

This module owns the figure's sound-generation subsystem:

- single-active-plot playback policy,
- 0.1-second PCM chunk generation,
- phase-aware chunk refresh when parameters change,
- a thin browser bridge that queues PCM chunks in Web Audio,
- a hosted modal error dialog for playback failures.

The Python side renders 0.1 seconds of mono PCM at a time. The browser side
requests chunks on demand and schedules them into a small playback queue.
Parameter changes keep the currently playing chunk, discard only the buffered
future chunks, and request a fused replacement chunk whose phase is aligned to
what is already audible.
"""

import base64
import html
import uuid
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import traitlets

from ._widget_stubs import anywidget, widgets
from .widget_chrome import (
    ModalDialogBridge,
    attach_host_children,
    build_action_bar,
    build_dialog_header,
    build_modal_overlay,
    build_modal_panel,
    configure_action_button,
    configure_icon_button,
    hosted_modal_dimensions,
)

if TYPE_CHECKING:
    from .Figure import Figure
    from .figure_legend import LegendPanelManager
    from .figure_plot import Plot


@dataclass(slots=True)
class _SoundChunkRecord:
    """Recently generated PCM chunk kept for continuity matching."""

    plot_id: str
    token: int
    sample_rate: int
    start_seconds: float
    start_frame: int
    end_frame: int
    frame_count: int
    samples: np.ndarray


class _SoundStreamBridge(anywidget.AnyWidget):
    """Hidden frontend bridge that turns PCM chunks into browser audio."""

    root_class = traitlets.Unicode("").tag(sync=True)

    _esm = r"""
    function safeNumber(value, fallback) {
      const num = Number(value);
      return Number.isFinite(num) ? num : fallback;
    }

    function clamp(value, minValue, maxValue) {
      return Math.min(maxValue, Math.max(minValue, value));
    }

    function decodePcm16Base64(payload) {
      const text = String(payload || "");
      const binary = atob(text);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i) & 0xff;
      }
      return new Int16Array(bytes.buffer.slice(0));
    }

    function modulo(value, period) {
      if (!(period > 0)) return 0;
      const out = value % period;
      return out < 0 ? out + period : out;
    }

    export default {
      render({ model, el }) {
        el.style.display = "none";

        const state = {
          audioContext: null,
          masterGain: null,
          isPlaying: false,
          activeToken: null,
          activePlotId: "",
          sourceEntries: [],
          nextStartTime: 0,
          requestInFlight: 0,
          lowBufferedSeconds: 0.22,
          targetBufferedSeconds: 0.48,
          batchChunks: 5,
          loopSeconds: 60.0,
          attackReleaseSeconds: 0.02,
          pendingAttack: false,
          stopTimer: null,
          pendingRefresh: null,
        };

        function rootEl() {
          const rootClass = model.get("root_class") || "";
          return rootClass ? document.querySelector(`.${rootClass}`) : null;
        }

        function clearStopTimer() {
          if (state.stopTimer !== null) {
            try {
              window.clearTimeout(state.stopTimer);
            } catch (e) {}
            state.stopTimer = null;
          }
        }

        function ensureAudioContext() {
          if (state.audioContext) return state.audioContext;
          const Ctor = window.AudioContext || window.webkitAudioContext;
          if (!Ctor) return null;
          try {
            state.audioContext = new Ctor();
          } catch (e) {
            state.audioContext = null;
          }
          return state.audioContext;
        }

        function playbackSampleRate() {
          const ctx = ensureAudioContext();
          if (!ctx) return 44100;
          return Math.max(8000, Math.trunc(safeNumber(ctx.sampleRate, 44100)));
        }

        function ensureOutputGain() {
          const ctx = ensureAudioContext();
          if (!ctx) return null;
          if (state.masterGain) return state.masterGain;
          try {
            state.masterGain = ctx.createGain();
            state.masterGain.gain.setValueAtTime(1.0, ctx.currentTime);
            state.masterGain.connect(ctx.destination);
          } catch (e) {
            state.masterGain = null;
          }
          return state.masterGain;
        }

        function primeAudioContext() {
          const ctx = ensureAudioContext();
          if (!ctx) return;
          ensureOutputGain();
          if (ctx.state === "suspended") {
            try {
              ctx.resume();
            } catch (e) {}
          }
        }

        function setMasterGain(value, when) {
          const ctx = ensureAudioContext();
          const gainNode = ensureOutputGain();
          if (!ctx || !gainNode) return;
          const at = Number.isFinite(when) ? when : ctx.currentTime;
          try {
            gainNode.gain.cancelScheduledValues(at);
            gainNode.gain.setValueAtTime(clamp(value, 0.0, 1.0), at);
          } catch (e) {}
        }

        function scheduleMasterGainRamp(fromValue, targetValue, seconds, when) {
          const ctx = ensureAudioContext();
          const gainNode = ensureOutputGain();
          if (!ctx || !gainNode) return;
          const startAt = Number.isFinite(when) ? when : ctx.currentTime;
          const duration = Math.max(0.0, safeNumber(seconds, 0.0));
          const initial = clamp(safeNumber(fromValue, gainNode.gain.value), 0.0, 1.0);
          try {
            gainNode.gain.cancelScheduledValues(startAt);
            gainNode.gain.setValueAtTime(initial, startAt);
            gainNode.gain.linearRampToValueAtTime(
              clamp(targetValue, 0.0, 1.0),
              startAt + duration,
            );
          } catch (e) {}
        }

        function clearEndedEntries() {
          const ctx = state.audioContext;
          if (!ctx) {
            state.sourceEntries = [];
            return;
          }
          const now = ctx.currentTime - 0.01;
          state.sourceEntries = state.sourceEntries.filter((entry) => entry.endAt > now);
        }

        function currentEntry() {
          const ctx = state.audioContext;
          if (!ctx) return null;
          clearEndedEntries();
          const now = ctx.currentTime;
          for (const entry of state.sourceEntries) {
            if (now >= entry.startAt && now < entry.endAt) {
              return entry;
            }
          }
          return null;
        }

        function bufferedSeconds() {
          const ctx = state.audioContext;
          if (!ctx) return 0;
          clearEndedEntries();
          if (!state.sourceEntries.length) return 0;
          const tail = state.sourceEntries.reduce((best, entry) => (
            entry.endAt > best.endAt ? entry : best
          ));
          return Math.max(0, tail.endAt - ctx.currentTime);
        }

        function nextBoundaryCursor() {
          const active = currentEntry();
          if (active) {
            return modulo(active.chunkStartSeconds + active.durationSeconds, state.loopSeconds);
          }
          if (state.sourceEntries.length) {
            const first = state.sourceEntries.reduce((best, entry) => (
              entry.startAt < best.startAt ? entry : best
            ));
            return modulo(first.chunkStartSeconds, state.loopSeconds);
          }
          return 0;
        }

        function nextBoundaryStartTime() {
          const active = currentEntry();
          if (active) {
            return active.endAt;
          }
          if (state.sourceEntries.length) {
            const first = state.sourceEntries.reduce((best, entry) => (
              entry.startAt < best.startAt ? entry : best
            ));
            return first.startAt;
          }
          const ctx = state.audioContext;
          return ctx ? ctx.currentTime : 0;
        }

        function stopEntry(entry) {
          if (!entry) return;
          try {
            entry.source.onended = null;
          } catch (e) {}
          try {
            entry.source.stop();
          } catch (e) {}
          try {
            entry.source.disconnect();
          } catch (e) {}
        }

        function dropEntriesStartingAtOrAfter(startAt) {
          if (!Number.isFinite(startAt)) return;
          const keptEntries = [];
          for (const entry of state.sourceEntries) {
            if (entry.startAt + 1.0e-6 < startAt) {
              keptEntries.push(entry);
              continue;
            }
            stopEntry(entry);
          }
          state.sourceEntries = keptEntries;
          state.nextStartTime = startAt;
        }

        function hardStopAllSources() {
          for (const entry of state.sourceEntries) {
            stopEntry(entry);
          }
          state.sourceEntries = [];
          state.nextStartTime = 0;
          state.requestInFlight = 0;
          state.pendingRefresh = null;
        }

        function stopAllSourcesImmediately() {
          clearStopTimer();
          hardStopAllSources();
          state.isPlaying = false;
          state.activePlotId = "";
          state.pendingAttack = false;
        }

        function fadeOutAndStop() {
          const ctx = ensureAudioContext();
          if (!ctx) {
            stopAllSourcesImmediately();
            state.activeToken = null;
            return;
          }
          clearStopTimer();
          scheduleMasterGainRamp(1.0, 0.0, state.attackReleaseSeconds, ctx.currentTime);
          state.stopTimer = window.setTimeout(() => {
            stopAllSourcesImmediately();
            state.activeToken = null;
            setMasterGain(0.0, ctx.currentTime);
          }, Math.max(30, Math.ceil(state.attackReleaseSeconds * 1000) + 20));
        }

        function requestChunk(cursorSeconds) {
          if (!state.isPlaying || state.activeToken === null || state.activeToken === undefined) {
            return;
          }
          if (state.requestInFlight > 0) return;
          state.requestInFlight += 1;
          const payload = {
            type: "sound_stream_request",
            action: "request_chunk",
            token: state.activeToken,
            sample_rate: playbackSampleRate(),
            batch_chunks: state.batchChunks,
          };
          if (Number.isFinite(cursorSeconds)) {
            payload.cursor_seconds = cursorSeconds;
          }
          try {
            model.send(payload);
          } catch (e) {
            state.requestInFlight = Math.max(0, state.requestInFlight - 1);
          }
        }

        function maybeRequestChunk() {
          if (!state.isPlaying) return;
          if (state.pendingRefresh !== null) return;
          if (bufferedSeconds() >= state.lowBufferedSeconds) return;
          requestChunk(undefined);
        }

        function scheduleSingleChunk(chunk, startAtOverride) {
          const ctx = ensureAudioContext();
          const outputGain = ensureOutputGain();
          if (!ctx || !outputGain || !state.isPlaying) return null;

          const sampleRate = Math.max(1, Math.trunc(safeNumber(chunk.sample_rate, playbackSampleRate())));
          const frameCount = Math.max(0, Math.trunc(safeNumber(chunk.frame_count, 0)));
          const chunkStartSeconds = modulo(
            safeNumber(chunk.chunk_start_seconds, 0),
            state.loopSeconds,
          );
          const pcm = decodePcm16Base64(chunk.pcm_base64 || "");
          const usableFrames = Math.max(1, frameCount || pcm.length || 1);
          const buffer = ctx.createBuffer(1, usableFrames, sampleRate);
          const channel = buffer.getChannelData(0);
          const usable = Math.min(channel.length, pcm.length);
          for (let i = 0; i < usable; i += 1) {
            channel[i] = clamp(pcm[i] / 32767.0, -1.0, 1.0);
          }
          for (let i = usable; i < channel.length; i += 1) {
            channel[i] = 0.0;
          }

          const source = ctx.createBufferSource();
          source.buffer = buffer;
          source.connect(outputGain);

          const duration = buffer.duration || (usableFrames / sampleRate);
          const leadTime = 0.015;
          const now = ctx.currentTime + leadTime;
          const requestedStartAt = Number.isFinite(startAtOverride) ? startAtOverride : state.nextStartTime;
          const startAt = Math.max(now, requestedStartAt || now);
          const entry = {
            source,
            startAt,
            endAt: startAt + duration,
            chunkStartSeconds,
            durationSeconds: duration,
          };

          if (state.pendingAttack) {
            const attack = Math.min(state.attackReleaseSeconds, Math.max(0.001, duration));
            setMasterGain(0.0, startAt);
            scheduleMasterGainRamp(0.0, 1.0, attack, startAt);
            state.pendingAttack = false;
          }

          source.onended = () => {
            state.sourceEntries = state.sourceEntries.filter((candidate) => candidate !== entry);
            maybeRequestChunk();
          };

          state.sourceEntries.push(entry);
          state.sourceEntries.sort((left, right) => left.startAt - right.startAt);
          state.nextStartTime = entry.endAt;

          try {
            source.start(startAt);
          } catch (e) {
            state.sourceEntries = state.sourceEntries.filter((candidate) => candidate !== entry);
            try {
              source.disconnect();
            } catch (err) {}
            return null;
          }

          return entry;
        }

        function scheduleChunkMessage(message) {
          scheduleChunkBatchMessage({
            token: message.token,
            chunks: [message],
          });
        }

        function scheduleChunkBatchMessage(message) {
          const ctx = ensureAudioContext();
          const outputGain = ensureOutputGain();
          state.requestInFlight = Math.max(0, state.requestInFlight - 1);
          if (!ctx || !outputGain || !state.isPlaying) return;
          if (message.token !== state.activeToken) return;

          const chunkList = Array.isArray(message.chunks) ? message.chunks : [];
          if (!chunkList.length) {
            maybeRequestChunk();
            return;
          }

          let firstStartOverride = undefined;
          if (state.pendingRefresh && state.pendingRefresh.token === message.token) {
            const refresh = state.pendingRefresh;
            const refreshStartAt = Number.isFinite(refresh.startAt)
              ? refresh.startAt
              : nextBoundaryStartTime();
            const deadline = refreshStartAt - 0.004;
            if (ctx.currentTime > deadline && state.sourceEntries.length) {
              state.pendingRefresh = {
                token: message.token,
                cursorSeconds: nextBoundaryCursor(),
                startAt: nextBoundaryStartTime(),
              };
              requestChunk(state.pendingRefresh.cursorSeconds);
              return;
            }
            dropEntriesStartingAtOrAfter(refreshStartAt);
            firstStartOverride = refreshStartAt;
            state.pendingRefresh = null;
          }

          for (let i = 0; i < chunkList.length; i += 1) {
            const chunk = chunkList[i] || {};
            const startAtOverride = (i === 0 && Number.isFinite(firstStartOverride))
              ? firstStartOverride
              : undefined;
            const entry = scheduleSingleChunk(chunk, startAtOverride);
            if (!entry) return;
          }

          if (bufferedSeconds() < state.targetBufferedSeconds) {
            requestChunk(undefined);
            return;
          }
          maybeRequestChunk();
        }

        function handleStart(message) {
          clearStopTimer();
          primeAudioContext();
          hardStopAllSources();
          const ctx = state.audioContext;
          if (ctx) {
            setMasterGain(0.0, ctx.currentTime);
          }
          state.pendingAttack = true;
          state.isPlaying = true;
          state.activeToken = message.token;
          state.activePlotId = String(message.plot_id || "");
          state.pendingRefresh = null;
          requestChunk(safeNumber(message.cursor_seconds, 0));
        }

        function handleStop(message) {
          state.activeToken = message.token;
          state.isPlaying = false;
          state.activePlotId = "";
          state.pendingRefresh = null;
          fadeOutAndStop();
        }

        function handleRefresh(message) {
          clearStopTimer();
          primeAudioContext();
          state.isPlaying = true;
          state.activeToken = message.token;
          state.activePlotId = String(message.plot_id || "");
          state.pendingRefresh = {
            token: message.token,
            cursorSeconds: nextBoundaryCursor(),
            startAt: nextBoundaryStartTime(),
          };
          state.requestInFlight = 0;
          requestChunk(state.pendingRefresh.cursorSeconds);
        }

        function onCustomMessage(message) {
          if (!message || message.type !== "sound_stream") return;
          const action = message.action;
          if (action === "start") {
            handleStart(message);
            return;
          }
          if (action === "stop") {
            handleStop(message);
            return;
          }
          if (action === "refresh") {
            handleRefresh(message);
            return;
          }
          if (action === "chunk") {
            scheduleChunkMessage(message);
            return;
          }
          if (action === "chunk_batch") {
            scheduleChunkBatchMessage(message);
            return;
          }
          if (action === "error") {
            handleStop(message);
          }
        }

        function onPointerIntent(event) {
          const target = event && event.target;
          const root = rootEl();
          if (!(target instanceof HTMLElement) || !(root instanceof HTMLElement)) return;
          if (!root.contains(target)) return;
          primeAudioContext();
        }

        function onKeydownIntent(event) {
          const root = rootEl();
          const active = document.activeElement;
          if (!(root instanceof HTMLElement) || !(active instanceof HTMLElement)) return;
          if (!root.contains(active)) return;
          primeAudioContext();
        }

        model.on("msg:custom", onCustomMessage);
        document.addEventListener("pointerdown", onPointerIntent, true);
        document.addEventListener("keydown", onKeydownIntent, true);

        return () => {
          try { model.off("msg:custom", onCustomMessage); } catch (e) {}
          try { document.removeEventListener("pointerdown", onPointerIntent, true); } catch (e) {}
          try { document.removeEventListener("keydown", onKeydownIntent, true); } catch (e) {}
          clearStopTimer();
          stopAllSourcesImmediately();
          const gainNode = state.masterGain;
          if (gainNode) {
            try { gainNode.disconnect(); } catch (e) {}
          }
          const ctx = state.audioContext;
          if (ctx && typeof ctx.close === "function") {
            try { ctx.close(); } catch (e) {}
          }
          state.masterGain = null;
          state.audioContext = null;
        };
      },
    };
    """



class FigureSoundManager:
    """Own the figure's single-active streaming playback state."""

    sample_rate = 44100
    chunk_seconds = 0.1
    loop_seconds = 60.0
    attack_release_seconds = 0.02
    prefetch_chunks = 5
    _value_tolerance = 1.0e-9
    _phase_search_seconds = 0.05
    _phase_search_candidates = 129
    _phase_refine_candidates = 41
    _phase_match_seconds = 0.01
    _chunk_history_limit = 64
    _continuity_fit_points = 8

    def __init__(
        self,
        figure: Figure,
        legend: LegendPanelManager,
        *,
        root_widget: widgets.Box | None = None,
    ) -> None:
        self._figure = figure
        self._legend = legend
        self._root_widget = root_widget
        self._enabled = True
        self._active_plot_id: str | None = None
        self._generation_token = 0
        self._cursor_seconds = 0.0
        self._stream_sample_rate = int(self.sample_rate)
        self._phase_offset_seconds = 0.0
        self._pending_transition_token: int | None = None
        self._chunk_history: deque[_SoundChunkRecord] = deque(maxlen=self._chunk_history_limit)
        self._error_open = False

        self._root_css_class = f"gu-figure-sound-root-{uuid.uuid4().hex[:8]}"
        self._error_modal_class = f"{self._root_css_class}-sound-error-modal"
        if self._root_widget is not None:
            add_class = getattr(self._root_widget, "add_class", None)
            if callable(add_class):
                add_class(self._root_css_class)

        self._bridge = _SoundStreamBridge(
            root_class=self._root_css_class,
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._bridge.on_msg(self._handle_bridge_message)

        self._error_title = widgets.HTML(
            "Sound playback error",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self._error_title.add_class("gu-modal-title-text")
        self._error_title.add_class("gu-sound-error-title-text")
        self._error_message = widgets.HTML("", layout=widgets.Layout(margin="0", width="100%"))
        self._error_message.add_class("gu-sound-error-message")
        self._error_close_button = widgets.Button(
            description="Close sound error dialog",
            tooltip="Close sound error dialog",
        )
        configure_icon_button(
            self._error_close_button,
            role="close",
            size_px=24,
            extra_classes=("gu-sound-error-close-button",),
        )
        self._error_close_button.on_click(lambda _button: self._hide_error_dialog(clear_message=False))
        self._error_ok_button = widgets.Button(
            description="OK",
            tooltip="Close sound error dialog",
        )
        configure_action_button(self._error_ok_button, variant="primary", min_width_px=72)
        self._error_ok_button.on_click(lambda _button: self._hide_error_dialog(clear_message=False))
        error_header = build_dialog_header(self._error_title, self._error_close_button)
        error_actions = build_action_bar([self._error_ok_button])
        error_width, error_min_width, error_max_width = hosted_modal_dimensions(
            preferred_width_px=420,
            minimum_width_px=300,
        )
        self._error_panel = build_modal_panel(
            [error_header, self._error_message, error_actions],
            width=error_width,
            min_width=error_min_width,
            max_width=error_max_width,
            padding="14px",
            gap="12px",
            display="none",
            extra_classes=("gu-sound-error-panel",),
        )
        self._error_modal = build_modal_overlay(
            self._error_panel,
            hosted=True,
            z_index="1002",
            background_color="rgba(15, 23, 42, 0.22)",
            modal_class=self._error_modal_class,
        )
        self._error_bridge = ModalDialogBridge(
            modal_class=self._error_modal_class,
            panel_selector=".gu-sound-error-panel",
            close_selector=".gu-sound-error-close-button",
            title_selector=".gu-sound-error-title-text",
            dialog_open=False,
            dialog_label="Sound playback error",
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._error_bridge.on_msg(self._handle_error_dialog_message)
        self._sync_error_state()

        attach_host_children(
            self._root_widget,
            self._bridge,
            self._error_modal,
            self._error_bridge,
        )

        bind_handler = getattr(self._legend, "bind_sound_enabled_handler", None)
        if callable(bind_handler):
            bind_handler(self.sound_generation_enabled)
        self._legend.set_sound_generation_enabled(True)
        self._legend.set_sound_playing_plot(None)

    @property
    def enabled(self) -> bool:
        """Return whether sound controls are available for the figure."""
        return True

    @property
    def active_plot_id(self) -> str | None:
        """Return the currently playing plot id, if any."""
        return self._active_plot_id

    def sound_generation_enabled(self, enabled: bool | None = None) -> bool:
        """Legacy compatibility shim for always-available sound controls.

        Sound playback controls are now always available. Passing ``False`` stops
        any active playback but no longer hides the speaker buttons.
        """

        self._enabled = True
        if enabled is not None and not bool(enabled) and self._active_plot_id is not None:
            self._stop_playback()
        self._legend.set_sound_generation_enabled(True)
        return True

    def sound(self, plot_id: str, *, run: bool = True) -> None:
        """Start, stop, or restart playback for ``plot_id``."""
        normalized_plot_id = str(plot_id)
        if not run:
            if self._active_plot_id == normalized_plot_id:
                self._stop_playback()
            return

        plot = self._figure.plots.get(normalized_plot_id)
        if plot is None:
            raise KeyError(f"Unknown plot id: {normalized_plot_id!r}")

        previous_token = self._generation_token
        previous_plot_id = self._active_plot_id
        previous_cursor = self._cursor_seconds
        previous_stream_sample_rate = self._stream_sample_rate
        previous_phase_offset = self._phase_offset_seconds
        previous_pending_transition = self._pending_transition_token
        next_token = previous_token + 1

        self._hide_error_dialog(clear_message=True)
        self._phase_offset_seconds = 0.0
        self._pending_transition_token = None

        try:
            self._build_chunk(
                plot,
                start_seconds=0.0,
                token=next_token,
                sample_rate=self._stream_sample_rate,
                store_history=False,
            )
        except Exception as exc:
            self._generation_token = previous_token
            self._active_plot_id = previous_plot_id
            self._cursor_seconds = previous_cursor
            self._stream_sample_rate = previous_stream_sample_rate
            self._phase_offset_seconds = previous_phase_offset
            self._pending_transition_token = previous_pending_transition
            self._legend.set_sound_playing_plot(previous_plot_id)
            self._show_error_dialog(str(exc))
            return

        self._chunk_history.clear()
        self._generation_token = next_token
        self._active_plot_id = normalized_plot_id
        self._cursor_seconds = 0.0
        self._legend.set_sound_playing_plot(normalized_plot_id)
        self._send_message(
            {
                "type": "sound_stream",
                "action": "start",
                "plot_id": normalized_plot_id,
                "token": self._generation_token,
                "cursor_seconds": 0.0,
            }
        )

    def on_parameter_change(self, _event: Any) -> None:
        """Refresh queued audio so future chunks use the latest parameter values."""
        if self._active_plot_id is None:
            return
        plot = self._figure.plots.get(self._active_plot_id)
        if plot is None:
            self._stop_playback()
            return
        self._generation_token += 1
        self._pending_transition_token = self._generation_token
        self._send_message(
            {
                "type": "sound_stream",
                "action": "refresh",
                "plot_id": self._active_plot_id,
                "token": self._generation_token,
            }
        )

    def _stop_playback(self) -> None:
        self._generation_token += 1
        token = self._generation_token
        self._active_plot_id = None
        self._cursor_seconds = 0.0
        self._phase_offset_seconds = 0.0
        self._pending_transition_token = None
        self._chunk_history.clear()
        self._legend.set_sound_playing_plot(None)
        self._send_message(
            {
                "type": "sound_stream",
                "action": "stop",
                "token": token,
            }
        )

    def _handle_bridge_message(self, _widget: Any, content: Any, _buffers: Any) -> None:
        if not isinstance(content, dict):
            return
        if content.get("type") != "sound_stream_request":
            return
        if content.get("action") != "request_chunk":
            return

        token = self._safe_int(content.get("token"), default=-1)
        if token != self._generation_token:
            return
        if self._active_plot_id is None:
            return

        plot = self._figure.plots.get(self._active_plot_id)
        if plot is None:
            self._stop_playback()
            return

        request_sample_rate = self._coerce_sample_rate(content.get("sample_rate"))
        self._set_stream_sample_rate(request_sample_rate)
        batch_chunks = self._safe_int(content.get("batch_chunks"), default=self.prefetch_chunks)
        batch_chunks = max(1, min(batch_chunks, self.prefetch_chunks))

        cursor_override = content.get("cursor_seconds")
        if cursor_override is not None:
            self._cursor_seconds = self._normalize_cursor(
                self._safe_float(cursor_override, default=self._cursor_seconds)
            )

        try:
            payload = self._next_chunk_payload(
                plot,
                sample_rate=request_sample_rate,
                batch_chunks=batch_chunks,
            )
        except Exception as exc:
            self._fail_playback(plot_id=self._active_plot_id, error=exc, raise_error=False)
            return

        self._send_message(payload)

    def _next_chunk_payload(
        self,
        plot: Plot,
        *,
        sample_rate: int,
        batch_chunks: int,
    ) -> dict[str, Any]:
        batch_count = max(1, int(batch_chunks))
        next_cursor = self._cursor_seconds
        chunk_payloads: list[dict[str, Any]] = []

        for _index in range(batch_count):
            token, chunk_start_seconds, pcm_base64, frame_count = self._build_chunk(
                plot,
                start_seconds=next_cursor,
                token=self._generation_token,
                sample_rate=sample_rate,
            )
            chunk_payloads.append(
                {
                    "plot_id": self._active_plot_id or "",
                    "token": token,
                    "sample_rate": sample_rate,
                    "frame_count": frame_count,
                    "chunk_start_seconds": chunk_start_seconds,
                    "pcm_base64": pcm_base64,
                }
            )
            next_cursor = self._normalize_cursor(chunk_start_seconds + self.chunk_seconds)

        self._cursor_seconds = next_cursor
        if len(chunk_payloads) == 1:
            payload = dict(chunk_payloads[0])
            payload.update(
                {
                    "type": "sound_stream",
                    "action": "chunk",
                }
            )
            return payload

        return {
            "type": "sound_stream",
            "action": "chunk_batch",
            "plot_id": self._active_plot_id or "",
            "token": self._generation_token,
            "sample_rate": sample_rate,
            "chunks": chunk_payloads,
        }

    def _build_chunk(
        self,
        plot: Plot,
        *,
        start_seconds: float,
        token: int,
        sample_rate: int,
        store_history: bool = True,
    ) -> tuple[int, float, str, int]:
        chunk_start = self._normalize_cursor(start_seconds)
        frame_count = self._chunk_frame_count(sample_rate=sample_rate)
        plot_id = str(getattr(plot, "id", ""))

        pending_transition = self._pending_transition_token == token
        reference_record: _SoundChunkRecord | None = None
        phase_offset = self._phase_offset_seconds
        if pending_transition:
            reference_record = self._find_reference_chunk(
                plot_id=plot_id,
                next_chunk_start_seconds=chunk_start,
                sample_rate=sample_rate,
                exclude_token=token,
            )
            if reference_record is not None:
                phase_offset = self._choose_phase_offset(
                    plot,
                    chunk_start_seconds=chunk_start,
                    frame_count=frame_count,
                    sample_rate=sample_rate,
                    reference_record=reference_record,
                )

        y_values = self._render_chunk_samples(
            plot,
            chunk_start_seconds=chunk_start,
            frame_count=frame_count,
            sample_rate=sample_rate,
            phase_offset_seconds=phase_offset,
        )

        if reference_record is not None:
            y_values = self._blend_with_reference_continuation(
                y_values,
                sample_rate=sample_rate,
                reference_record=reference_record,
            )

        self._phase_offset_seconds = self._normalize_cursor(phase_offset)
        if pending_transition:
            self._pending_transition_token = None

        pcm_base64 = self._encode_pcm(y_values)
        if store_history:
            self._store_chunk_record(
                plot_id=plot_id,
                token=token,
                sample_rate=sample_rate,
                chunk_start_seconds=chunk_start,
                samples=y_values,
            )
        return token, chunk_start, pcm_base64, frame_count

    def _render_chunk_samples(
        self,
        plot: Plot,
        *,
        chunk_start_seconds: float,
        frame_count: int,
        sample_rate: int,
        phase_offset_seconds: float,
    ) -> np.ndarray:
        offsets = np.arange(frame_count, dtype=float) / float(sample_rate)
        x_values = np.mod(chunk_start_seconds + phase_offset_seconds + offsets, self.loop_seconds)
        return self._evaluate_samples(plot, x_values, expected_count=frame_count)

    def _evaluate_samples(
        self,
        plot: Plot,
        x_values: np.ndarray,
        *,
        expected_count: int,
    ) -> np.ndarray:
        try:
            raw_values = plot.numeric_expression(x_values)
            y_values = np.asarray(raw_values, dtype=float)
        except Exception as exc:
            raise ValueError(
                f"Failed to evaluate sound for plot {plot.id!r}: {exc}"
            ) from exc

        if y_values.ndim == 0:
            y_values = np.full(expected_count, float(y_values), dtype=float)
        else:
            y_values = np.ravel(y_values)
            if y_values.shape[0] != expected_count:
                raise ValueError(
                    "Sound expression must evaluate to exactly one sample per time point."
                )

        if not np.all(np.isfinite(y_values)):
            raise ValueError("Sound expression must be finite and stay within [-1, 1].")

        peak = float(np.max(np.abs(y_values))) if y_values.size else 0.0
        if peak > 1.0 + self._value_tolerance:
            raise ValueError(
                "Sound expression must stay within [-1, 1]; auto-normalization is disabled."
            )

        return np.clip(np.asarray(y_values, dtype=float), -1.0, 1.0)

    @staticmethod
    def _encode_pcm(samples: np.ndarray) -> str:
        pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
        return base64.b64encode(pcm.tobytes()).decode("ascii")

    def _store_chunk_record(
        self,
        *,
        plot_id: str,
        token: int,
        sample_rate: int,
        chunk_start_seconds: float,
        samples: np.ndarray,
    ) -> None:
        sample_copy = np.asarray(samples, dtype=float).copy()
        start_frame = self._cursor_to_frame(chunk_start_seconds, sample_rate=sample_rate)
        end_frame = (start_frame + int(sample_copy.size)) % self._loop_frame_count(
            sample_rate=sample_rate
        )
        self._chunk_history.append(
            _SoundChunkRecord(
                plot_id=str(plot_id),
                token=int(token),
                sample_rate=int(sample_rate),
                start_seconds=float(chunk_start_seconds),
                start_frame=start_frame,
                end_frame=end_frame,
                frame_count=int(sample_copy.size),
                samples=sample_copy,
            )
        )

    def _find_reference_chunk(
        self,
        *,
        plot_id: str,
        next_chunk_start_seconds: float,
        sample_rate: int,
        exclude_token: int | None = None,
    ) -> _SoundChunkRecord | None:
        boundary_frame = self._cursor_to_frame(next_chunk_start_seconds, sample_rate=sample_rate)
        for record in reversed(self._chunk_history):
            if record.plot_id != plot_id:
                continue
            if int(record.sample_rate) != int(sample_rate):
                continue
            if exclude_token is not None and record.token == exclude_token:
                continue
            if record.end_frame == boundary_frame:
                return record
        return None

    def _predict_continuation(
        self,
        source_samples: np.ndarray,
        frame_count: int,
        *,
        sample_rate: int,
    ) -> np.ndarray:
        count = min(max(2, self._continuity_fit_points), int(source_samples.size))
        tail = np.asarray(source_samples[-count:], dtype=float)
        dt = 1.0 / float(sample_rate)
        sample_positions = np.arange(-count, 0, dtype=float) * dt
        target_positions = np.arange(frame_count, dtype=float) * dt
        degree = min(3, count - 1)
        try:
            coeffs = np.polyfit(sample_positions, tail, degree)
            predicted = np.polyval(coeffs, target_positions)
        except Exception:
            if count == 1:
                predicted = np.full(frame_count, float(tail[-1]), dtype=float)
            else:
                slope = float((tail[-1] - tail[-2]) / dt)
                predicted = float(tail[-1]) + slope * target_positions
        return np.clip(np.asarray(predicted, dtype=float), -1.0, 1.0)

    def _choose_phase_offset(
        self,
        plot: Plot,
        *,
        chunk_start_seconds: float,
        frame_count: int,
        sample_rate: int,
        reference_record: _SoundChunkRecord,
    ) -> float:
        analysis_frames = min(
            frame_count,
            max(8, int(round(self._phase_match_seconds * sample_rate))),
        )
        target_profile = self._predict_continuation(
            reference_record.samples,
            analysis_frames,
            sample_rate=sample_rate,
        )
        base_offset = self._phase_offset_seconds
        search_seconds = min(self._phase_search_seconds, self.loop_seconds / 4.0)
        if search_seconds <= 0.0:
            return self._normalize_cursor(base_offset)

        coarse_offsets = np.linspace(
            base_offset - search_seconds,
            base_offset + search_seconds,
            self._phase_search_candidates,
        )
        coarse_best = self._best_phase_offset_candidate(
            plot,
            chunk_start_seconds=chunk_start_seconds,
            candidate_offsets=coarse_offsets,
            analysis_frames=analysis_frames,
            sample_rate=sample_rate,
            target_profile=target_profile,
        )

        if self._phase_search_candidates > 1:
            coarse_step = float(coarse_offsets[1] - coarse_offsets[0])
        else:
            coarse_step = 1.0 / float(sample_rate)
        refine_span = max(coarse_step, 1.0 / float(sample_rate))
        refine_offsets = np.linspace(
            coarse_best - refine_span,
            coarse_best + refine_span,
            self._phase_refine_candidates,
        )
        refined_best = self._best_phase_offset_candidate(
            plot,
            chunk_start_seconds=chunk_start_seconds,
            candidate_offsets=refine_offsets,
            analysis_frames=analysis_frames,
            sample_rate=sample_rate,
            target_profile=target_profile,
        )
        return self._normalize_cursor(refined_best)

    def _best_phase_offset_candidate(
        self,
        plot: Plot,
        *,
        chunk_start_seconds: float,
        candidate_offsets: np.ndarray,
        analysis_frames: int,
        sample_rate: int,
        target_profile: np.ndarray,
    ) -> float:
        offsets = np.arange(analysis_frames, dtype=float) / float(sample_rate)
        evaluation_times = np.mod(
            chunk_start_seconds + candidate_offsets[:, None] + offsets[None, :],
            self.loop_seconds,
        )
        candidate_values = self._evaluate_samples(
            plot,
            np.ravel(evaluation_times),
            expected_count=int(evaluation_times.size),
        ).reshape(len(candidate_offsets), analysis_frames)
        errors = np.mean((candidate_values - target_profile[None, :]) ** 2, axis=1)
        best_index = int(np.argmin(errors)) if errors.size else 0
        return float(candidate_offsets[best_index])

    def _blend_with_reference_continuation(
        self,
        new_samples: np.ndarray,
        *,
        sample_rate: int,
        reference_record: _SoundChunkRecord,
    ) -> np.ndarray:
        bridge_frames = min(
            int(round(self.attack_release_seconds * sample_rate)),
            int(new_samples.size),
        )
        if bridge_frames <= 0:
            return np.asarray(new_samples, dtype=float)

        bridged = np.asarray(new_samples, dtype=float).copy()
        reference_continuation = self._predict_continuation(
            reference_record.samples,
            bridge_frames,
            sample_rate=sample_rate,
        )
        weights = self._smoothstep(np.linspace(0.0, 1.0, bridge_frames, endpoint=True))
        bridged[:bridge_frames] = (
            (1.0 - weights) * reference_continuation + weights * bridged[:bridge_frames]
        )
        return np.clip(bridged, -1.0, 1.0)

    def _fail_playback(
        self,
        *,
        plot_id: str | None,
        error: Exception,
        raise_error: bool = True,
    ) -> None:
        self._generation_token += 1
        token = self._generation_token
        self._active_plot_id = None
        self._cursor_seconds = 0.0
        self._phase_offset_seconds = 0.0
        self._pending_transition_token = None
        self._chunk_history.clear()
        self._legend.set_sound_playing_plot(None)
        self._show_error_dialog(str(error))
        self._send_message(
            {
                "type": "sound_stream",
                "action": "error",
                "plot_id": plot_id or "",
                "token": token,
                "message": str(error),
            }
        )
        if raise_error:
            raise error

    def _show_error_dialog(self, message: str) -> None:
        self._error_message.value = (
            "<div class='gu-sound-error-body'>" + html.escape(message) + "</div>"
        )
        self._error_open = True
        self._sync_error_state()

    def _hide_error_dialog(self, *, clear_message: bool = False) -> None:
        self._error_open = False
        if clear_message:
            self._error_message.value = ""
        self._sync_error_state()

    def _sync_error_state(self) -> None:
        self._error_panel.layout.display = "flex" if self._error_open else "none"
        self._error_modal.layout.display = "flex" if self._error_open else "none"
        self._error_bridge.dialog_open = self._error_open

    def _handle_error_dialog_message(self, _widget: Any, content: Any, _buffers: Any) -> None:
        if not isinstance(content, dict):
            return
        if content.get("type") != "dialog_request":
            return
        if content.get("action") == "close":
            self._hide_error_dialog(clear_message=False)

    def _send_message(self, payload: dict[str, Any]) -> None:
        try:
            self._bridge.send(payload)
        except TypeError:
            self._bridge.send(payload, None)

    def _coerce_sample_rate(self, value: Any) -> int:
        fallback = int(self._stream_sample_rate or self.sample_rate)
        sample_rate = self._safe_int(value, default=fallback)
        return max(8_000, min(sample_rate, 192_000))

    def _set_stream_sample_rate(self, sample_rate: int) -> None:
        normalized = self._coerce_sample_rate(sample_rate)
        if normalized == self._stream_sample_rate:
            return
        self._stream_sample_rate = normalized
        self._chunk_history.clear()
        self._phase_offset_seconds = 0.0
        self._pending_transition_token = None

    def _chunk_frame_count(self, *, sample_rate: int | None = None) -> int:
        rate = self._coerce_sample_rate(self.sample_rate if sample_rate is None else sample_rate)
        return max(1, int(round(rate * self.chunk_seconds)))

    def _loop_frame_count(self, *, sample_rate: int | None = None) -> int:
        rate = self._coerce_sample_rate(self.sample_rate if sample_rate is None else sample_rate)
        return max(1, int(round(rate * self.loop_seconds)))

    def _cursor_to_frame(self, value: float, *, sample_rate: int | None = None) -> int:
        rate = self._coerce_sample_rate(self.sample_rate if sample_rate is None else sample_rate)
        return int(round(self._normalize_cursor(value) * rate)) % self._loop_frame_count(
            sample_rate=rate
        )

    def _normalize_cursor(self, value: float) -> float:
        return float(value) % self.loop_seconds

    @staticmethod
    def _smoothstep(values: np.ndarray) -> np.ndarray:
        clipped = np.clip(np.asarray(values, dtype=float), 0.0, 1.0)
        return clipped * clipped * (3.0 - 2.0 * clipped)

    @staticmethod
    def _safe_float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _safe_int(value: Any, *, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return int(default)
