import ipywidgets as widgets
import traitlets

from .InputConvert import InputConvert


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

        self._limit_style = widgets.HTML(
            "<style>"
            ".smart-slider-limit input{font-size:10px;color:#666;height:20px;}"
            "</style>"
        )

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

        # --- Settings panel ---------------------------------------------------
        style_args = {"style": {"description_width": "50px"}, "layout": widgets.Layout(width="100px")}
        self.set_min = widgets.Text(
            value=f"{min:.4g}",
            continuous_update=False,
            layout=widgets.Layout(width="52px"),
        )
        self.set_min.add_class("smart-slider-limit")
        self.set_max = widgets.Text(
            value=f"{max:.4g}",
            continuous_update=False,
            layout=widgets.Layout(width="52px"),
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
            ],
            layout=widgets.Layout(align_items="center", gap="4px"),
        )
        super().__init__([top_row, self.settings_panel], **kwargs)

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

        # Settings -> slider traits
        widgets.link((self.set_step, "value"), (self.slider, "step"))
        widgets.link((self.set_live, "value"), (self.slider, "continuous_update"))

        # Initialize trait (and normalize displayed text)
        self.value = value
        self._sync_number_text(self.value)
        self._sync_limit_texts(None)

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
        self.value = self._defaults["value"]  # slider sync + slider observer updates text

    def _toggle_settings(self, _) -> None:
        self.settings_panel.layout.display = (
            "none" if self.settings_panel.layout.display == "flex" else "flex"
        )
