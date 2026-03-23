"""Responsive Plotly pane primitives.

This module contains two layers:

- :class:`PlotlyResizeDriver`, an ``anywidget`` frontend driver that measures the
  DOM host, tracks visibility/size transitions, and triggers Plotly resize.
- :class:`PlotlyPane`, a small Python wrapper that exposes the driver plus the
  host/wrapper widgets used by the rest of the toolkit.

The updated implementation makes geometry state explicit and synced back to
Python so notebook diagnostics can show actual browser measurements rather than
only ipywidgets layout traits.
"""

from __future__ import annotations


import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from ._widget_stubs import anywidget, widgets as W
import traitlets


from .layout_logging import LOGGER_NAME, new_debug_id, new_request_id

__all__ = [
    "PlotlyResizeDriver",
    "PlotlyPaneStyle",
    "PlotlyPaneGeometry",
    "PlotlyPane",
]

logger = logging.getLogger(f"{LOGGER_NAME}.plotly_pane")
driver_logger = logging.getLogger(f"{LOGGER_NAME}.plotly_driver")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())
if not driver_logger.handlers:
    driver_logger.addHandler(logging.NullHandler())


def _uid(n: int = 8) -> str:
    """Return a short random hex identifier."""
    return uuid.uuid4().hex[:n]


def _widget_layout_or_none(widget: Any) -> W.Layout | None:
    """Return the ipywidgets layout object for ``widget`` when available.

    Plotly ``FigureWidget`` exposes ``layout`` as the figure's graph layout, not
    the surrounding ipywidgets ``Layout``. This helper keeps the pane from
    treating graph layout objects like widget shell layout objects.
    """

    layout_obj = getattr(widget, "layout", None)
    return layout_obj if isinstance(layout_obj, W.Layout) else None


def _apply_default_fill_hints(widget: Any) -> None:
    """Apply default flex-fill hints to widgets that expose ``ipywidgets.Layout``."""

    widget_layout = _widget_layout_or_none(widget)
    if widget_layout is None:
        return
    if getattr(widget_layout, "width", "") in (None, ""):
        widget_layout.width = "100%"
    if getattr(widget_layout, "height", "") in (None, ""):
        widget_layout.height = "100%"
    if getattr(widget_layout, "min_width", "") in (None, ""):
        widget_layout.min_width = "0"
    if getattr(widget_layout, "min_height", "") in (None, ""):
        widget_layout.min_height = "0"


@dataclass(frozen=True)
class PlotlyPaneGeometry:
    """Browser-side geometry snapshot mirrored from the frontend driver."""

    state: str = "created"
    frontend_ready: bool = False
    host_connected: bool = False
    host_visible: bool = False
    plot_found: bool = False
    last_reason: str = ""
    last_request_id: str | None = None
    last_completed_reason: str = ""
    last_completed_request_id: str | None = None
    last_outcome: str = "created"
    last_error: str = ""
    pending_reason: str = ""
    pending_request_id: str | None = None
    reflow_token: int = 0
    host_width: int = 0
    host_height: int = 0
    clip_width: int = 0
    clip_height: int = 0
    measured_width: int = 0
    measured_height: int = 0
    resize_count: int = 0
    failure_count: int = 0

    @classmethod
    def from_driver(cls, driver: "PlotlyResizeDriver") -> "PlotlyPaneGeometry":
        def _none_if_empty(value: str) -> str | None:
            return value or None

        return cls(
            state=driver.frontend_state,
            frontend_ready=bool(driver.frontend_ready),
            host_connected=bool(driver.host_connected),
            host_visible=bool(driver.host_visible),
            plot_found=bool(driver.plot_found),
            last_reason=driver.last_reason,
            last_request_id=_none_if_empty(driver.last_request_id),
            last_completed_reason=driver.last_completed_reason,
            last_completed_request_id=_none_if_empty(driver.last_completed_request_id),
            last_outcome=driver.last_outcome,
            last_error=driver.last_error,
            pending_reason=driver.pending_reason,
            pending_request_id=_none_if_empty(driver.pending_request_id),
            reflow_token=int(driver.reflow_token),
            host_width=int(driver.host_width),
            host_height=int(driver.host_height),
            clip_width=int(driver.clip_width),
            clip_height=int(driver.clip_height),
            measured_width=int(driver.measured_width),
            measured_height=int(driver.measured_height),
            resize_count=int(driver.resize_count),
            failure_count=int(driver.failure_count),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlotlyResizeDriver(anywidget.AnyWidget):
    """Frontend resize driver for a Plotly DOM subtree."""

    host_selector = traitlets.Unicode("").tag(sync=True)
    autorange_mode = traitlets.Unicode("none").tag(sync=True)
    defer_reveal = traitlets.Bool(True).tag(sync=True)

    debounce_ms = traitlets.Int(60).tag(sync=True)
    min_delta_px = traitlets.Int(2).tag(sync=True)
    followup_ms_1 = traitlets.Int(80).tag(sync=True)
    followup_ms_2 = traitlets.Int(250).tag(sync=True)

    debug_js = traitlets.Bool(False).tag(sync=True)
    emit_layout_events = traitlets.Bool(False).tag(sync=True)
    figure_id = traitlets.Unicode("").tag(sync=True)
    view_id = traitlets.Unicode("").tag(sync=True)
    pane_id = traitlets.Unicode("").tag(sync=True)

    frontend_ready = traitlets.Bool(False).tag(sync=True)
    frontend_state = traitlets.Unicode("created").tag(sync=True)
    host_connected = traitlets.Bool(False).tag(sync=True)
    host_visible = traitlets.Bool(False).tag(sync=True)
    plot_found = traitlets.Bool(False).tag(sync=True)
    last_reason = traitlets.Unicode("").tag(sync=True)
    last_request_id = traitlets.Unicode("").tag(sync=True)
    last_completed_reason = traitlets.Unicode("").tag(sync=True)
    last_completed_request_id = traitlets.Unicode("").tag(sync=True)
    last_outcome = traitlets.Unicode("created").tag(sync=True)
    last_error = traitlets.Unicode("").tag(sync=True)
    pending_reason = traitlets.Unicode("").tag(sync=True)
    pending_request_id = traitlets.Unicode("").tag(sync=True)
    reflow_token = traitlets.Int(0).tag(sync=True)
    host_width = traitlets.Int(0).tag(sync=True)
    host_height = traitlets.Int(0).tag(sync=True)
    clip_width = traitlets.Int(0).tag(sync=True)
    clip_height = traitlets.Int(0).tag(sync=True)
    measured_width = traitlets.Int(0).tag(sync=True)
    measured_height = traitlets.Int(0).tag(sync=True)
    resize_count = traitlets.Int(0).tag(sync=True)
    failure_count = traitlets.Int(0).tag(sync=True)

    _esm = r"""
    function clampInt(x, dflt) {
      const n = Number(x);
      return Number.isFinite(n) ? Math.trunc(n) : dflt;
    }

    function sameScalar(a, b) {
      return a === b || (Number.isNaN(a) && Number.isNaN(b));
    }

    function safeLog(enabled, ...args) {
      if (enabled) console.log("[PlotlyResizeDriver]", ...args);
    }

    function emit(model, enabled, event, phase, fields) {
      const payload = Object.assign({ event, phase, source: "PlotlyResizeDriver" }, fields || {});
      safeLog(enabled, payload);
      if (!model.get("emit_layout_events")) return;
      try { model.send({ type: "layout_event", payload }); } catch (e) {}
    }

    function syncTraits(model, fields) {
      let changed = false;
      for (const [key, value] of Object.entries(fields || {})) {
        if (!sameScalar(model.get(key), value)) {
          model.set(key, value);
          changed = true;
        }
      }
      if (changed) {
        try { model.save_changes(); } catch (e) {}
      }
    }

    function pxSizeOf(el) {
      if (!el) return { w: 0, h: 0 };
      const r = el.getBoundingClientRect();
      return {
        w: Math.max(0, Math.round(r.width || 0)),
        h: Math.max(0, Math.round(r.height || 0)),
      };
    }

    function findPlotEl(host) {
      if (!host) return null;
      return host.querySelector(".js-plotly-plot");
    }

    function findClipAncestor(startEl) {
      let el = startEl;
      while (el && el.parentElement) {
        el = el.parentElement;
        const cs = getComputedStyle(el);
        const ox = cs.overflowX || cs.overflow || "visible";
        if (ox !== "visible") return el;
      }
      return null;
    }

    function effectiveSize(host, clip) {
      const hs = pxSizeOf(host);
      if (!clip) return hs;
      const cs = pxSizeOf(clip);
      return {
        w: cs.w > 0 ? Math.min(hs.w, cs.w) : hs.w,
        h: hs.h,
      };
    }

    function hostVisibility(host, intersectionState) {
      if (!host) {
        return { connected: false, visible: false, hiddenByStyle: true };
      }
      const connected = !!host.isConnected;
      if (!connected) {
        return { connected: false, visible: false, hiddenByStyle: true };
      }
      const cs = getComputedStyle(host);
      const hiddenByStyle = cs.display === "none" || cs.visibility === "hidden";
      const hasClientRects = host.getClientRects().length > 0;
      const visible = connected && !hiddenByStyle && hasClientRects && intersectionState !== false;
      return { connected, visible, hiddenByStyle };
    }

    function setPlotHeights(plotEl, hPx) {
      plotEl.style.height = `${hPx}px`;
      const pc = plotEl.querySelector(".plot-container");
      if (pc) pc.style.height = `${hPx}px`;
    }

    function applyWidthClamp(plotEl, wPx) {
      plotEl.style.width = "100%";
      plotEl.style.minWidth = "0";
      plotEl.style.maxWidth = `${wPx}px`;
      plotEl.style.boxSizing = "border-box";
      plotEl.style.overflowX = "hidden";
      plotEl.style.overflowY = "hidden";

      const pc = plotEl.querySelector(".plot-container");
      if (pc) {
        pc.style.width = "100%";
        pc.style.minWidth = "0";
        pc.style.maxWidth = `${wPx}px`;
        pc.style.boxSizing = "border-box";
        pc.style.overflowX = "hidden";
        pc.style.overflowY = "hidden";
      }

      const svgContainer = plotEl.querySelector(".svg-container");
      if (svgContainer) {
        svgContainer.style.maxWidth = `${wPx}px`;
        svgContainer.style.boxSizing = "border-box";
        svgContainer.style.overflowX = "hidden";
        svgContainer.style.overflowY = "hidden";
      }
    }

    async function plotlyResize(plotEl) {
      try {
        const P = window.Plotly;
        if (P && P.Plots && typeof P.Plots.resize === "function") {
          return await P.Plots.resize(plotEl);
        }
      } catch (e) {}
      window.dispatchEvent(new Event("resize"));
      return null;
    }

    function buildAutorangeUpdate(plotEl) {
      const fl = plotEl && plotEl._fullLayout;
      if (!fl) return null;

      const upd = {};
      for (const k of Object.keys(fl)) {
        if (/^xaxis(\d+)?$/.test(k)) upd[`${k}.autorange`] = true;
        if (/^yaxis(\d+)?$/.test(k)) upd[`${k}.autorange`] = true;
      }
      return Object.keys(upd).length ? upd : null;
    }

    async function maybeAutorange(plotEl, mode, alreadyDidOnce, debug) {
      if (mode === "none") return alreadyDidOnce;
      if (mode === "once" && alreadyDidOnce) return alreadyDidOnce;

      const P = window.Plotly;
      if (!P || typeof P.relayout !== "function") {
        safeLog(debug, "autorange requested but window.Plotly.relayout unavailable");
        return alreadyDidOnce;
      }

      const upd = buildAutorangeUpdate(plotEl);
      if (!upd) return alreadyDidOnce;

      try {
        await P.relayout(plotEl, upd);
        return true;
      } catch (e) {
        safeLog(debug, "autorange relayout failed:", e);
        return alreadyDidOnce;
      }
    }

    export default {
      render({ model, el }) {
        el.style.display = "none";

        let debug = !!model.get("debug_js");
        let host = null;
        let clip = null;
        let roHost = null;
        let roClip = null;
        let ioHost = null;
        let debounceTimer = null;
        let retryTimer = null;
        let settleTimer = null;
        let revealed = false;
        let didAutorangeOnce = false;
        let resizeCount = 0;
        let failureCount = 0;
        let lastIntersection = null;
        let destroyed = false;
        let handledReflowToken = 0;
        let requestSeq = 0;
        let activeRequest = null;
        let lastApplied = { w: 0, h: 0 };

        function identity() {
          return {
            figure_id: model.get("figure_id") || "",
            view_id: model.get("view_id") || "",
            pane_id: model.get("pane_id") || "",
          };
        }

        function waitRetryDelays() {
          return [
            40,
            Math.max(40, clampInt(model.get("followup_ms_1"), 80)),
            Math.max(80, clampInt(model.get("followup_ms_2"), 250)),
          ];
        }

        function resolveHost() {
          const sel = model.get("host_selector");
          if (sel && typeof sel === "string" && sel.trim()) {
            return document.querySelector(sel.trim());
          }
          return el.parentElement;
        }

        function setHostHidden(hidden) {
          if (!host) return;
          if (!model.get("defer_reveal")) hidden = false;
          if (hidden) {
            host.style.opacity = "0";
            host.style.pointerEvents = "none";
          } else {
            host.style.opacity = "";
            host.style.pointerEvents = "";
          }
        }

        function disconnectObservers() {
          try { if (roHost) roHost.disconnect(); } catch (e) {}
          try { if (roClip) roClip.disconnect(); } catch (e) {}
          try { if (ioHost) ioHost.disconnect(); } catch (e) {}
          roHost = null;
          roClip = null;
          ioHost = null;
        }

        function clearTimers() {
          if (debounceTimer) clearTimeout(debounceTimer);
          if (retryTimer) clearTimeout(retryTimer);
          if (settleTimer) clearTimeout(settleTimer);
          debounceTimer = null;
          retryTimer = null;
          settleTimer = null;
        }

        function isActiveToken(token) {
          return !destroyed && !!activeRequest && activeRequest.token === token;
        }

        function refreshObservers() {
          const nextHost = resolveHost();
          const nextClip = nextHost ? findClipAncestor(nextHost) : null;
          if (nextHost === host && nextClip === clip) {
            return;
          }

          disconnectObservers();
          host = nextHost;
          clip = nextClip;
          lastIntersection = null;

          if (!host) return;

          roHost = new ResizeObserver(() => schedule("ResizeObserver:host", null, false));
          roHost.observe(host);

          if (clip && clip !== host) {
            roClip = new ResizeObserver(() => schedule("ResizeObserver:clip", null, false));
            roClip.observe(clip);
          }

          if (typeof IntersectionObserver === "function") {
            ioHost = new IntersectionObserver((entries) => {
              const entry = entries && entries[0] ? entries[0] : null;
              lastIntersection = entry ? !!entry.isIntersecting : lastIntersection;
              schedule("IntersectionObserver", null, true);
            }, { root: null, threshold: [0, 0.01, 0.5, 1] });
            ioHost.observe(host);
          }

          if (model.get("defer_reveal") && !revealed) {
            setHostHidden(true);
          } else {
            setHostHidden(false);
          }
        }

        function publishState(state, fields) {
          syncTraits(model, Object.assign({ frontend_ready: true, frontend_state: state }, fields || {}));
        }

        function currentGeometry(reason, requestId, plotEl) {
          const hostSize = pxSizeOf(host);
          const clipSize = clip ? pxSizeOf(clip) : { w: 0, h: 0 };
          const effective = effectiveSize(host, clip);
          const visibility = hostVisibility(host, lastIntersection);
          return {
            state: "ready",
            host_connected: visibility.connected,
            host_visible: visibility.visible,
            plot_found: !!plotEl,
            last_reason: reason || "",
            last_request_id: requestId || "",
            host_width: hostSize.w,
            host_height: hostSize.h,
            clip_width: clipSize.w,
            clip_height: clipSize.h,
            measured_width: effective.w,
            measured_height: effective.h,
          };
        }

        function markWaiting(state, outcome, reason, requestId, plotEl, extra) {
          failureCount += 1;
          const geometry = currentGeometry(reason, requestId, plotEl);
          publishState(state, Object.assign({}, geometry, {
            frontend_state: state,
            last_outcome: outcome,
            last_error: (extra && extra.last_error) || "",
            failure_count: failureCount,
            resize_count: resizeCount,
          }, extra || {}));
          emit(model, debug, "resize_waiting", "waiting", Object.assign(identity(), {
            state,
            outcome,
            reason: reason || "",
            request_id: requestId || null,
            host_w: geometry.host_width,
            host_h: geometry.host_height,
            clip_w: geometry.clip_width,
            clip_h: geometry.clip_height,
            effective_w: geometry.measured_width,
            effective_h: geometry.measured_height,
            failure_count: failureCount,
          }));
          return "waiting";
        }

        async function doResize(reason, requestId, force, token) {
          if (!isActiveToken(token)) return "cancelled";

          emit(model, debug, "resize_attempt_started", "started", Object.assign(identity(), {
            reason: reason || "",
            request_id: requestId || null,
            force: !!force,
          }));

          refreshObservers();
          if (!host) {
            failureCount += 1;
            publishState("waiting_for_host", {
              frontend_ready: true,
              host_connected: false,
              host_visible: false,
              plot_found: false,
              last_reason: reason || "",
              last_request_id: requestId || "",
              last_outcome: "waiting_for_host",
              last_error: "",
              failure_count: failureCount,
              resize_count: resizeCount,
            });
            emit(model, debug, "resize_waiting", "waiting", Object.assign(identity(), {
              state: "waiting_for_host",
              outcome: "waiting_for_host",
              reason: reason || "",
              request_id: requestId || null,
            }));
            return "waiting";
          }

          clip = findClipAncestor(host);
          const plotEl = findPlotEl(host);
          const visibility = hostVisibility(host, lastIntersection);
          const geometry = currentGeometry(reason, requestId, plotEl);

          if (!plotEl) {
            return markWaiting("waiting_for_plot", "waiting_for_plot", reason, requestId, plotEl, null);
          }
          if (!visibility.connected || !visibility.visible) {
            return markWaiting("waiting_for_visibility", "waiting_for_visibility", reason, requestId, plotEl, null);
          }
          if (!(geometry.measured_width > 0 && geometry.measured_height > 0)) {
            return markWaiting("waiting_for_measurement", "waiting_for_measurement", reason, requestId, plotEl, null);
          }

          const minDelta = clampInt(model.get("min_delta_px"), 2);
          const dw = Math.abs(geometry.measured_width - lastApplied.w);
          const dh = Math.abs(geometry.measured_height - lastApplied.h);
          if (!force && revealed && dw < minDelta && dh < minDelta) {
            publishState("ready", Object.assign({}, geometry, {
              last_completed_reason: reason || model.get("last_completed_reason") || "",
              last_completed_request_id: requestId || model.get("last_completed_request_id") || "",
              last_outcome: "skipped_min_delta",
              last_error: "",
              pending_reason: "",
              pending_request_id: "",
              failure_count: failureCount,
              resize_count: resizeCount,
            }));
            emit(model, debug, "resize_skipped", "completed", Object.assign(identity(), {
              outcome: "skipped_min_delta",
              reason: reason || "",
              request_id: requestId || null,
              host_w: geometry.host_width,
              host_h: geometry.host_height,
              effective_w: geometry.measured_width,
              effective_h: geometry.measured_height,
            }));
            return "skipped";
          }

          lastApplied = { w: geometry.measured_width, h: geometry.measured_height };
          applyWidthClamp(plotEl, geometry.measured_width);
          setPlotHeights(plotEl, geometry.measured_height);

          try {
            await plotlyResize(plotEl);
          } catch (error) {
            return markWaiting(
              "waiting_for_plotly",
              "plotly_resize_failed",
              reason,
              requestId,
              plotEl,
              { last_error: String(error || "Plotly resize failed") },
            );
          }

          if (!isActiveToken(token)) return "cancelled";

          const mode = model.get("autorange_mode") || "none";
          didAutorangeOnce = await maybeAutorange(plotEl, mode, didAutorangeOnce, debug);

          if (!isActiveToken(token)) return "cancelled";

          if (!revealed) {
            setHostHidden(false);
            revealed = true;
          }
          resizeCount += 1;
          const finalGeometry = currentGeometry(reason, requestId, plotEl);
          lastApplied = { w: finalGeometry.measured_width, h: finalGeometry.measured_height };
          publishState("ready", Object.assign({}, finalGeometry, {
            last_completed_reason: reason || model.get("last_completed_reason") || "",
            last_completed_request_id: requestId || model.get("last_completed_request_id") || "",
            last_outcome: "resized",
            last_error: "",
            pending_reason: "",
            pending_request_id: "",
            failure_count: failureCount,
            resize_count: resizeCount,
          }));
          emit(model, debug, "resize_applied", "completed", Object.assign(identity(), {
            outcome: "resized",
            reason: reason || "",
            request_id: requestId || null,
            force: !!force,
            host_w: finalGeometry.host_width,
            host_h: finalGeometry.host_height,
            clip_w: finalGeometry.clip_width,
            clip_h: finalGeometry.clip_height,
            effective_w: finalGeometry.measured_width,
            effective_h: finalGeometry.measured_height,
            resize_count: resizeCount,
          }));
          return "resized";
        }

        async function runRequest(token) {
          if (!isActiveToken(token)) return;
          debounceTimer = null;
          retryTimer = null;
          settleTimer = null;

          const req = activeRequest;
          const outcome = await doResize(req.reason, req.requestId, !!req.force, token);
          if (!isActiveToken(token)) return;

          if (outcome === "waiting") {
            const delays = waitRetryDelays();
            if (req.retryIndex < delays.length) {
              const delay = delays[req.retryIndex];
              req.retryIndex += 1;
              retryTimer = setTimeout(() => runRequest(token), delay);
            } else {
              activeRequest = null;
            }
            return;
          }

          if (outcome === "resized" && !!req.force && !req.settleDone) {
            req.force = false;
            req.settleDone = true;
            const delay = Math.max(0, clampInt(model.get("followup_ms_1"), 80));
            settleTimer = setTimeout(() => runRequest(token), delay);
            return;
          }

          activeRequest = null;
        }

        function schedule(reason, requestId, force) {
          const nextReason = reason || "reflow";
          const nextRequestId = requestId || null;
          clearTimers();
          requestSeq += 1;
          activeRequest = {
            token: requestSeq,
            reason: nextReason,
            requestId: nextRequestId,
            force: !!force,
            retryIndex: 0,
            settleDone: false,
          };
          syncTraits(model, {
            pending_reason: nextReason,
            pending_request_id: nextRequestId || "",
            last_reason: nextReason,
            last_request_id: nextRequestId || "",
            last_outcome: "queued",
            last_error: "",
          });
          const wait = Math.max(0, clampInt(model.get("debounce_ms"), 60));
          debounceTimer = setTimeout(() => runRequest(activeRequest.token), wait);
        }

        const onAutorangeChange = () => schedule("change:autorange_mode", null, true);
        const onRevealChange = () => {
          if (!model.get("defer_reveal")) {
            setHostHidden(false);
            revealed = true;
          } else if (!revealed) {
            setHostHidden(true);
          }
          schedule("change:defer_reveal", null, true);
        };
        const onDebugChange = () => {
          debug = !!model.get("debug_js");
        };
        const onHostSelectorChange = () => {
          refreshObservers();
          schedule("change:host_selector", null, true);
        };
        const onReflowTokenChange = () => {
          const token = clampInt(model.get("reflow_token"), 0);
          if (token <= handledReflowToken) return;
          handledReflowToken = token;
          schedule(model.get("pending_reason") || "trait:reflow_token", model.get("pending_request_id") || null, true);
        };
        const onWindowResize = () => schedule("window:resize", null, false);
        const onVisibilityChange = () => schedule("document:visibilitychange", null, true);

        model.on("change:autorange_mode", onAutorangeChange);
        model.on("change:defer_reveal", onRevealChange);
        model.on("change:debug_js", onDebugChange);
        model.on("change:host_selector", onHostSelectorChange);
        model.on("change:reflow_token", onReflowTokenChange);
        window.addEventListener("resize", onWindowResize);
        document.addEventListener("visibilitychange", onVisibilityChange);

        refreshObservers();
        if (model.get("defer_reveal") && !revealed) {
          setHostHidden(true);
        } else {
          setHostHidden(false);
        }
        publishState("frontend_mounted", {
          host_connected: !!(host && host.isConnected),
          host_visible: false,
          plot_found: false,
          last_reason: "render",
          last_request_id: "",
          last_outcome: "mounted",
          last_error: "",
          resize_count: resizeCount,
          failure_count: failureCount,
        });
        emit(model, debug, "driver_mounted", "completed", Object.assign(identity(), { reason: "render" }));
        schedule("init", null, true);
        onReflowTokenChange();

        return () => {
          destroyed = true;
          clearTimers();
          disconnectObservers();
          try { model.off("change:autorange_mode", onAutorangeChange); } catch (e) {}
          try { model.off("change:defer_reveal", onRevealChange); } catch (e) {}
          try { model.off("change:debug_js", onDebugChange); } catch (e) {}
          try { model.off("change:host_selector", onHostSelectorChange); } catch (e) {}
          try { model.off("change:reflow_token", onReflowTokenChange); } catch (e) {}
          try { window.removeEventListener("resize", onWindowResize); } catch (e) {}
          try { document.removeEventListener("visibilitychange", onVisibilityChange); } catch (e) {}
          try { setHostHidden(false); } catch (e) {}
          emit(model, debug, "driver_disposed", "completed", Object.assign(identity(), {}));
        };
      }
    };
    """
    def geometry_snapshot(self) -> PlotlyPaneGeometry:
        """Return the latest browser-side geometry snapshot."""
        return PlotlyPaneGeometry.from_driver(self)

    def geometry_snapshot_dict(self) -> dict[str, Any]:
        """Return the latest browser-side geometry snapshot as a dictionary."""
        return self.geometry_snapshot().as_dict()

    def queue_reflow(self, *, reason: str = "manual", request_id: str | None = None) -> str:
        """Persist one reflow request so it survives frontend mount timing."""
        resolved_request_id = str(request_id or new_request_id())
        reason_text = str(reason)
        if (
            self.pending_reason == reason_text
            and self.pending_request_id == resolved_request_id
            and self.last_outcome == "queued"
        ):
            return resolved_request_id
        self.pending_reason = reason_text
        self.pending_request_id = resolved_request_id
        self.last_reason = reason_text
        self.last_request_id = resolved_request_id
        self.last_outcome = "queued"
        self.last_error = ""
        self.reflow_token = int(self.reflow_token or 0) + 1
        return resolved_request_id


    def reflow(
        self,
        *,
        reason: str = "manual",
        request_id: str | None = None,
        view_id: str | None = None,
        figure_id: str | None = None,
        pane_id: str | None = None,
        force: bool = True,
        persist: bool = True,
    ) -> str:
        """Request a resize/reflow from the frontend and return the request id.

        The request is carried entirely by synced traits. This keeps the reflow
        path simple, survives frontend mount timing, and avoids the duplicate
        scheduling that happens when a custom message and a trait change both
        describe the same request.
        """
        del force, persist
        if view_id is not None:
            self.view_id = str(view_id)
        if figure_id is not None:
            self.figure_id = str(figure_id)
        if pane_id is not None:
            self.pane_id = str(pane_id)
        resolved_request_id = str(request_id or new_request_id())
        return self.queue_reflow(reason=reason, request_id=resolved_request_id)


@dataclass(frozen=True)
class PlotlyPaneStyle:
    """Visual styling options for :class:`PlotlyPane`."""

    padding_px: int = 0
    border: str = "1px solid #ddd"
    border_radius_px: int = 8
    overflow: str = "hidden"


class PlotlyPane:
    """Styled, responsive plot area for a Plotly ``FigureWidget``."""

    _STYLE_HTML = (
        "<style>"
        ".gu-plotly-pane-wrap,"
        ".gu-plotly-pane-host,"
        ".gu-plotly-pane-slot {"
        "box-sizing: border-box !important;"
        "min-width: 0 !important;"
        "min-height: 0 !important;"
        "overflow: hidden !important;"
        "}"
        ".gu-plotly-pane-slot > * {"
        "width: 100% !important;"
        "height: 100% !important;"
        "min-width: 0 !important;"
        "min-height: 0 !important;"
        "box-sizing: border-box !important;"
        "}"
        ".gu-plotly-pane-wrap .js-plotly-plot,"
        ".gu-plotly-pane-wrap .plot-container,"
        ".gu-plotly-pane-wrap .svg-container {"
        "max-width: 100% !important;"
        "box-sizing: border-box !important;"
        "overflow-x: hidden !important;"
        "}"
        ".gu-plotly-pane-wrap .plot-container,"
        ".gu-plotly-pane-wrap .svg-container {"
        "overflow-y: hidden !important;"
        "}"
        "</style>"
    )

    def __init__(
        self,
        figw: W.Widget,
        *,
        style: PlotlyPaneStyle = PlotlyPaneStyle(),  # noqa: B008
        autorange_mode: str = "none",
        defer_reveal: bool = True,
        debounce_ms: int = 60,
        min_delta_px: int = 2,
        debug_js: bool = False,
    ):
        self.debug_pane_id = new_debug_id("pane")
        self._layout_event_emitter = None
        self._layout_debug_context: dict[str, Any] = {"pane_id": self.debug_pane_id}

        self._style_widget = W.HTML(
            self._STYLE_HTML,
            layout=W.Layout(width="0px", height="0px", margin="0px"),
        )

        _apply_default_fill_hints(figw)

        self.driver = PlotlyResizeDriver(
            autorange_mode=autorange_mode,
            defer_reveal=defer_reveal,
            debounce_ms=debounce_ms,
            min_delta_px=min_delta_px,
            debug_js=debug_js,
            pane_id=self.debug_pane_id,
        )
        try:
            self.driver.layout.display = "none"
            self.driver.layout.width = "0px"
            self.driver.layout.height = "0px"
        except Exception:  # pragma: no cover - defensive widget boundary
            pass

        self._plot_slot = W.Box(
            [figw],
            layout=W.Layout(
                width="100%",
                height="100%",
                min_width="0",
                min_height="0",
                display="flex",
                flex_flow="column",
                overflow="hidden",
                flex="1 1 auto",
                align_self="stretch",
            ),
        )
        self._plot_slot.add_class("gu-plotly-pane-slot")

        self._host = W.Box(
            [self._style_widget, self._plot_slot, self.driver],
            layout=W.Layout(
                width="100%",
                height="100%",
                min_width="0",
                min_height="0",
                display="flex",
                flex_flow="column",
                overflow="hidden",
            ),
        )
        self._host.add_class("gu-plotly-pane-host")

        self.driver.on_msg(self._handle_driver_message)

        self._wrap = W.Box(
            [self._host],
            layout=W.Layout(
                width="100%",
                height="100%",
                min_width="0",
                min_height="0",
                padding=f"{int(style.padding_px)}px",
                border=style.border,
                border_radius=f"{int(style.border_radius_px)}px",
                overflow=style.overflow,
                box_sizing="border-box",
            ),
        )
        self._wrap.add_class("gu-plotly-pane-wrap")

    def bind_layout_debug(self, emitter: Any, **context: Any) -> None:
        self._layout_event_emitter = emitter
        self._layout_debug_context = {
            **self._layout_debug_context,
            **context,
            "pane_id": self.debug_pane_id,
        }
        self.driver.emit_layout_events = True
        self.driver.figure_id = str(self._layout_debug_context.get("figure_id", ""))
        self.driver.view_id = str(self._layout_debug_context.get("view_id", ""))
        self.driver.pane_id = self.debug_pane_id

    def _emit_layout_event(
        self,
        event: str,
        *,
        source: str,
        phase: str,
        level: int = logging.DEBUG,
        **fields: Any,
    ) -> None:
        if self._layout_event_emitter is None:
            return
        payload = dict(self._layout_debug_context)
        payload.update(fields)
        self._layout_event_emitter(
            event=event,
            source=source,
            phase=phase,
            level=level,
            **payload,
        )

    def _handle_driver_message(self, _widget: Any, content: Any, _buffers: Any) -> None:
        if not isinstance(content, dict) or content.get("type") != "layout_event":
            return
        payload = dict(content.get("payload") or {})
        event = str(payload.pop("event", "driver_event"))
        phase = str(payload.pop("phase", "completed"))
        source = str(payload.pop("source", "PlotlyResizeDriver"))
        self._emit_layout_event(event, source=source, phase=phase, **payload)

    @property
    def widget(self) -> W.Widget:
        """Return the widget that should be embedded into outer layouts."""
        return self._wrap

    @property
    def geometry(self) -> PlotlyPaneGeometry:
        """Return the latest frontend geometry snapshot."""
        return self.driver.geometry_snapshot()

    def geometry_snapshot(self) -> PlotlyPaneGeometry:
        """Return the latest frontend geometry snapshot."""
        return self.geometry

    def debug_snapshot(self) -> dict[str, Any]:
        """Return a combined widget-tree and frontend-geometry snapshot."""
        snap = {
            "pane_id": self.debug_pane_id,
            "wrap_children": len(self._wrap.children),
            "host_children": len(self._host.children),
            "pane_widget_width": self._wrap.layout.width,
            "pane_widget_height": self._wrap.layout.height,
            "host_display": self._host.layout.display,
            "host_width": self._host.layout.width,
            "host_height": self._host.layout.height,
            "host_flex_flow": self._host.layout.flex_flow,
            "plot_slot_width": self._plot_slot.layout.width,
            "plot_slot_height": self._plot_slot.layout.height,
            "driver_autorange_mode": self.driver.autorange_mode,
            "driver_defer_reveal": self.driver.defer_reveal,
            "driver_debounce_ms": self.driver.debounce_ms,
            "driver_min_delta_px": self.driver.min_delta_px,
        }
        for key, value in self.geometry.as_dict().items():
            snap[f"geometry_{key}"] = value
        return snap

    def layout_snapshot(self) -> dict[str, Any]:
        """Alias for :meth:`debug_snapshot` used by notebook diagnostics."""
        return self.debug_snapshot()

    def reflow(
        self,
        *,
        reason: str = "manual",
        request_id: str | None = None,
        view_id: str | None = None,
        figure_id: str | None = None,
        pane_id: str | None = None,
        force: bool = True,
    ) -> str:
        """Trigger a programmatic resize/reflow and return the request id."""
        resolved_request_id = request_id or new_request_id()
        self._emit_layout_event(
            "reflow_message_sent",
            source="PlotlyPane",
            phase="sent",
            reason=reason,
            request_id=resolved_request_id,
            view_id=view_id,
            figure_id=figure_id,
            force=force,
        )
        return str(
            self.driver.reflow(
                reason=reason,
                request_id=resolved_request_id,
                view_id=view_id,
                figure_id=figure_id,
                pane_id=(pane_id or self.debug_pane_id),
                force=force,
            )
        )
