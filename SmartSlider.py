import anywidget
import ipywidgets as widgets
import traitlets
from ipywidgets import widget_serialization

from .InputConvert import InputConvert


class SliderAnimationDriver(anywidget.AnyWidget):
    """
    Frontend-only animation driver for a FloatSlider.

    This widget is intended to be hidden in the widget tree. It listens to a
    play/pause toggle and updates the slider value on a fixed interval entirely
    in the browser, avoiding integer-only `ipywidgets.Play` constraints.
    """

    slider = traitlets.Any().tag(sync=True, **widget_serialization)
    play_button = traitlets.Any().tag(sync=True, **widget_serialization)
    interval_ms = traitlets.Int(100).tag(sync=True)
    debug_js = traitlets.Bool(False).tag(sync=True)

    _esm = r"""
    function safeNumber(v, fallback) {
      const n = Number(v);
      return Number.isFinite(n) ? n : fallback;
    }

    export default {
      render({ model, el }) {
        el.style.display = "none";

        const sliderModel = model.get("slider");
        const playModel = model.get("play_button");

        if (!sliderModel || !playModel) {
          return;
        }

        let direction = 1;
        let timer = null;
        let listenerRoots = new Set();
        let viewObserver = null;

        function log(...args) {
          if (model.get("debug_js")) {
            console.log("[SliderAnimationDriver]", ...args);
          }
        }

        function computeNext() {
          const min = safeNumber(sliderModel.get("min"), 0);
          const max = safeNumber(sliderModel.get("max"), 1);
          const step = safeNumber(sliderModel.get("step"), 0);
          const value = safeNumber(sliderModel.get("value"), min);

          if (!Number.isFinite(min) || !Number.isFinite(max) || !Number.isFinite(step) || step === 0) {
            return null;
          }

          const span = max - min;
          if (!Number.isFinite(span) || span <= 0) {
            return null;
          }

          const maxIndex = Math.round(span / step);
          if (!Number.isFinite(maxIndex) || maxIndex <= 0) {
            return null;
          }

          let idx = Math.round((value - min) / step);
          if (!Number.isFinite(idx)) {
            idx = 0;
          }

          let nextIndex = idx + direction;
          if (nextIndex > maxIndex) {
            nextIndex = maxIndex;
            direction = -1;
          } else if (nextIndex < 0) {
            nextIndex = 0;
            direction = 1;
          }

          let next = min + nextIndex * step;
          if (next > max) next = max;
          if (next < min) next = min;

          return next;
        }

        function tick() {
          const next = computeNext();
          if (next === null) return;
          sliderModel.set("value", next);
          sliderModel.save_changes();
        }

        function getInterval() {
          const ms = safeNumber(model.get("interval_ms"), 100);
          return ms > 0 ? ms : 100;
        }

        function startLoop() {
          stopLoop();
          direction = 1;
          const interval = getInterval();
          timer = setInterval(tick, interval);
          log("start", interval);
        }

        function stopLoop() {
          if (timer !== null) {
            clearInterval(timer);
            timer = null;
            log("stop");
          }
        }

        function stopFromUser() {
          if (!playModel.get("value")) return;
          playModel.set("value", false);
          playModel.save_changes();
        }

        function addListenerRoot(root) {
          if (!root || listenerRoots.has(root)) return;
          listenerRoots.add(root);
          root.addEventListener("pointerdown", stopFromUser, { passive: true });
          root.addEventListener("keydown", stopFromUser);
        }

        function attachListeners() {
          const views = sliderModel.views;
          if (views && typeof views.forEach === "function") {
            views.forEach((view) => {
              if (view && view.el) addListenerRoot(view.el);
            });
          }

          const selector = `[data-model-id="${sliderModel.model_id}"]`;
          const dom = document.querySelector(selector);
          if (dom) addListenerRoot(dom);
        }

        function syncPlayState() {
          if (playModel.get("value")) {
            startLoop();
          } else {
            stopLoop();
          }
        }

        const onIntervalChange = () => {
          if (playModel.get("value")) {
            startLoop();
          }
        };

        playModel.on("change:value", syncPlayState);
        model.on("change:interval_ms", onIntervalChange);

        attachListeners();
        viewObserver = new MutationObserver(() => attachListeners());
        viewObserver.observe(document.body, { childList: true, subtree: true });

        if (playModel.get("value")) {
          startLoop();
        }

        return () => {
          stopLoop();
          playModel.off("change:value", syncPlayState);
          model.off("change:interval_ms", onIntervalChange);
          if (viewObserver) viewObserver.disconnect();
          listenerRoots.forEach((root) => {
            root.removeEventListener("pointerdown", stopFromUser);
            root.removeEventListener("keydown", stopFromUser);
          });
          listenerRoots.clear();
        };
      }
    }
    """


class SmartFloatSlider(widgets.VBox):
    """
    A FloatSlider with:
      - a *single editable numeric field* (Text) that accepts expressions via InputConvert,
      - reset + settings buttons,
      - a small settings panel (min/max/step + live update toggle).

    Design notes
    ------------
    - The slider's built-in readout is disabled, so there is only one number field.
    - The Text field commits on Enter (continuous_update=False). This avoids fighting the
      user while they type partial expressions like "pi/2".
    - If parsing fails, the Text field reverts to the previous committed value.
    """

    value = traitlets.Float(0.0)

    def __init__(
        self,
        value=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        description="Value:",
        play_interval_ms=100,
        **kwargs,
    ):
        # Remember defaults for reset
        self._defaults = {"value": value, "min": min, "max": max, "step": step}

        # Internal guard to prevent circular updates (slider -> text -> slider -> ...)
        self._syncing = False

        # --- Main controls ----------------------------------------------------
        self.slider = widgets.FloatSlider(
            value=value,
            min=min,
            max=max,
            step=step,
            description="",
            continuous_update=True,
            readout=False,  # IMPORTANT: no built-in numeric field
            style={"description_width": "initial"},
            layout=widgets.Layout(width="50%"),
        )

        self.description_label = widgets.HTMLMath(
            value=description,
            layout=widgets.Layout(width="60px"),
        )

        #self._limit_style = widgets.HTML(
        #    "<style>"
        #    ".smart-slider-limit input{"
        #    "font-size:10px;"
        #    "color:#666;"
        #    "height:18px;"
        #    "border:none;"
        #    "box-shadow:none;"
        #    "background:transparent;"
        #    "padding:0px;"
        #   "text-align:center;"
        #    "}"
        #    "</style>"
        #)

        self._limit_style = widgets.HTML(r"""
<style>
/* ============================================================
   Min/Max look like small non-editable text until focus,
   but remain fully editable on click.
   Works without relying on a specific wrapper DOM.
   ============================================================ */

/* Shrink any wrapper(s) JupyterLab/ipywidgets might impose. */
.smart-slider-limit,
.smart-slider-limit * {
  min-height: 0 !important;
}

/* The actual editable element(s): handle both input + textarea. */
.smart-slider-limit :is(input, textarea) {
  /* Make it small */
  font-size: 10px !important;
  line-height: 1.1 !important;

  /* Force compact geometry despite JupyterLab theme defaults */
  height: 16px !important;
  min-height: 0 !important;
  padding: 0 2px !important;
  margin: 0 !important;

  /* Make it look like static text */
  background: transparent !important;
  border: 1px solid transparent !important;
  box-shadow: none !important;
  border-radius: 3px !important;

  color: var(--jp-ui-font-color2, #666) !important;
  text-align: center !important;
  box-sizing: border-box !important;
}

/* Optional: subtle “this is clickable” affordance on hover */
.smart-slider-limit :is(input, textarea):hover {
  border-bottom-color: rgba(0,0,0,0.20) !important;
}

/* On focus: show edit chrome so users realize they can type */
.smart-slider-limit :is(input, textarea):focus {
  outline: none !important;
  border-color: rgba(0,0,0,0.28) !important;
  background: rgba(0,0,0,0.04) !important;
}
</style>
""")
        # The *only* numeric field (editable; accepts expressions)
        self.number = widgets.Text(
            value=str(value),
            continuous_update=False,  # commit on Enter (and typically blur)
            layout=widgets.Layout(width="70px"),
        )

        self.btn_reset = widgets.Button(
            description="↺",
            tooltip="Reset",
            layout=widgets.Layout(width="22px", height="22px", padding="0px"),
        )
        self.btn_settings = widgets.Button(
            description="⚙",
            tooltip="Settings",
            layout=widgets.Layout(width="22px", height="22px", padding="0px"),
        )
        self.btn_play = widgets.ToggleButton(
            value=False,
            description="▶",
            tooltip="Play",
            layout=widgets.Layout(width="22px", height="22px", padding="0px"),
        )

        # --- Settings panel ---------------------------------------------------
        style_args = {"style": {"description_width": "50px"}, "layout": widgets.Layout(width="100px")}
        self.set_min = widgets.Text(
    value=f"{min:.4g}",
    continuous_update=False,
    layout=widgets.Layout(width="40px", height="16px"),
)
        self.set_min.add_class("smart-slider-limit")
        self.set_max = widgets.Text(
    value=f"{max:.4g}",
    continuous_update=False,
    layout=widgets.Layout(width="40px", height="16px"),
)
        self.set_max.add_class("smart-slider-limit")
        self.set_step = widgets.FloatText(value=step, description="Step:", **style_args)
        self.set_live = widgets.Checkbox(
            value=True,
            description="Live Update",
            indent=False,
            layout=widgets.Layout(width="120px"),
        )

        self.settings_panel = widgets.VBox(
            [widgets.HBox([self.set_step]), widgets.HBox([self.set_live])],
            layout=widgets.Layout(
                display="none", border="1px solid #eee", padding="5px", margin="5px 0"
            ),
        )

        # --- Layout -----------------------------------------------------------
        top_row = widgets.HBox(
            [
                self._limit_style,
                self.description_label,
                self.set_min,
                self.slider,
                self.set_max,
                self.number,
                self.btn_reset,
                self.btn_settings,
                self.btn_play,
            ],
            layout=widgets.Layout(align_items="center", gap="4px"),
        )
        self._animation_driver = SliderAnimationDriver(
            slider=self.slider,
            play_button=self.btn_play,
            interval_ms=int(play_interval_ms),
        )
        super().__init__([top_row, self.settings_panel, self._animation_driver], **kwargs)

        # --- Wiring -----------------------------------------------------------
        # Keep self.value and slider.value in sync
        traitlets.link((self, "value"), (self.slider, "value"))

        # Slider -> Text (display)
        self.slider.observe(self._sync_number_from_slider, names="value")
        self.slider.observe(self._sync_limit_texts, names=["min", "max"])
        # Text -> Slider (parse + clamp)
        self.number.observe(self._commit_text_value, names="value")
        self.set_min.observe(self._commit_min_value, names="value")
        self.set_max.observe(self._commit_max_value, names="value")

        # Buttons
        self.btn_reset.on_click(self._reset)
        self.btn_settings.on_click(self._toggle_settings)
        self.btn_play.observe(self._sync_play_button, names="value")

        # Settings -> slider traits
        widgets.link((self.set_step, "value"), (self.slider, "step"))
        widgets.link((self.set_live, "value"), (self.slider, "continuous_update"))
        self.set_step.observe(self._stop_playback_on_change, names="value")
        self.set_live.observe(self._stop_playback_on_change, names="value")

        # Initialize trait (and normalize displayed text)
        self.value = value
        self._sync_number_text(self.value)
        self._sync_limit_texts(None)
        self._sync_play_button(None)

    # --- Helpers --------------------------------------------------------------

    def _sync_number_text(self, val: float) -> None:
        """Set the text field from a numeric value, without triggering parse logic."""
        self._syncing = True
        try:
            self.number.value = f"{val:.4g}"
        finally:
            self._syncing = False

    def _sync_number_from_slider(self, change) -> None:
        """When the slider moves, update the single numeric field."""
        if self._syncing:
            return
        self._sync_number_text(change.new)

    def _sync_limit_texts(self, change) -> None:
        """Update the min/max limit text fields from the slider limits."""
        if self._syncing:
            return
        self._syncing = True
        try:
            self.set_min.value = f"{self.slider.min:.4g}"
            self.set_max.value = f"{self.slider.max:.4g}"
        finally:
            self._syncing = False

    def _commit_limit_value(self, change, *, limit: str) -> None:
        """Parse and apply min/max limits from text inputs."""
        if self._syncing:
            return
        self._stop_playback()
        raw = (change.new or "").strip()
        old_min = float(self.slider.min)
        old_max = float(self.slider.max)

        try:
            new_val = float(InputConvert(raw, dest_type=float, truncate=True))
            if limit == "min":
                new_min = min(new_val, old_max)
                self.slider.min = new_min
            else:
                new_max = max(new_val, old_min)
                self.slider.max = new_max
            self._sync_limit_texts(None)
        except (ValueError, TypeError, SyntaxError):
            self._syncing = True
            try:
                self.set_min.value = f"{old_min:.4g}"
                self.set_max.value = f"{old_max:.4g}"
            finally:
                self._syncing = False

    def _commit_min_value(self, change) -> None:
        self._commit_limit_value(change, limit="min")

    def _commit_max_value(self, change) -> None:
        self._commit_limit_value(change, limit="max")

    def _commit_text_value(self, change) -> None:
        """
        When the user commits text (Enter / blur):
          - parse via InputConvert,
          - clamp to [min, max],
          - update self.value,
          - normalize the displayed text.

        On any error, revert to the value *before* this edit.
        """
        if self._syncing:
            return
        self._stop_playback()

        raw = (change.new or "").strip()
        old_val = float(self.value)

        try:
            new_val = InputConvert(raw, dest_type=float, truncate=True)
            new_val = max(self.slider.min, min(float(new_val), self.slider.max))
            self.value = new_val
            self._sync_number_text(self.value)  # normalize formatting
        except (ValueError, TypeError, SyntaxError):
            # Revert to the value before the edit
            self._sync_number_text(old_val)

    # --- Button handlers ------------------------------------------------------

    def _reset(self, _) -> None:
        self._stop_playback()
        self.value = self._defaults["value"]  # slider sync + slider observer updates text

    def _toggle_settings(self, _) -> None:
        self.settings_panel.layout.display = (
            "none" if self.settings_panel.layout.display == "flex" else "flex"
        )

    def _stop_playback_on_change(self, _) -> None:
        self._stop_playback()

    def _stop_playback(self) -> None:
        if self.btn_play.value:
            self.btn_play.value = False

    def _sync_play_button(self, change) -> None:
        self.btn_play.description = "⏸" if self.btn_play.value else "▶"
        self.btn_play.tooltip = "Pause" if self.btn_play.value else "Play"
