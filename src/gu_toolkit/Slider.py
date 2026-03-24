"""Custom slider widget used by Figure parameters.

Provides a synchronized slider/text control with advanced settings (min/max/
step/default) and helper APIs for parameter-reference integration.
"""

import html
import re
import uuid
from collections.abc import Sequence
from typing import Any, cast

from ._widget_stubs import anywidget, widgets
import traitlets

from .InputConvert import InputConvert
from .animation import DEFAULT_ANIMATION_TIME, AnimationController


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _derive_accessibility_label(description: str, *, fallback: str = "parameter") -> str:
    """Return a plain-text label suitable for ARIA metadata.

    ``FloatSlider`` descriptions are often rich-text or LaTeX snippets. Screen
    readers need a compact plain-text fallback that stays meaningful even when
    the visible label is rendered via HTML/MathJax.
    """

    raw = html.unescape(str(description or ""))
    raw = _HTML_TAG_RE.sub(" ", raw)
    raw = raw.replace("$", " ")
    raw = raw.replace("\\", " ")
    raw = raw.replace("{", " ").replace("}", " ")
    raw = _WHITESPACE_RE.sub(" ", raw).strip(" :")
    return raw or fallback


class _SliderModalAccessibilityBridge(anywidget.AnyWidget):
    """Frontend bridge that adds dialog semantics and keyboard handling."""

    slider_root_class = traitlets.Unicode("").tag(sync=True)
    modal_class = traitlets.Unicode("").tag(sync=True)
    dialog_open = traitlets.Bool(False).tag(sync=True)
    dialog_label = traitlets.Unicode("Parameter settings").tag(sync=True)
    control_label = traitlets.Unicode("parameter").tag(sync=True)

    _esm = r"""
    function q(node, selector) {
      return node ? node.querySelector(selector) : null;
    }

    function qInput(node) {
      return q(node, "input, textarea, select") || node;
    }

    function qButton(node) {
      return q(node, "button, .widget-button, .jupyter-button") || node;
    }

    function focusables(root) {
      if (!root) return [];
      const selector = [
        "button:not([disabled])",
        "input:not([disabled])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "a[href]",
        "[tabindex]:not([tabindex='-1'])",
      ].join(",");
      return Array.from(root.querySelectorAll(selector)).filter((el) => {
        if (!(el instanceof HTMLElement)) return false;
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") return false;
        return !el.hasAttribute("disabled");
      });
    }

    export default {
      render({ model, el }) {
        el.style.display = "none";

        const dialogId = `smart-slider-dialog-${Math.random().toString(16).slice(2)}`;
        const titleId = `${dialogId}-title`;
        let returnFocusEl = null;

        function rootEl() {
          const className = model.get("slider_root_class") || "";
          return className ? document.querySelector(`.${className}`) : null;
        }

        function modalEl() {
          const className = model.get("modal_class") || "";
          return className ? document.querySelector(`.${className}`) : null;
        }

        function panelEl() {
          return q(modalEl(), ".smart-slider-settings-panel");
        }

        function settingsButtonEl() {
          return qButton(q(rootEl(), ".smart-slider-settings-button"));
        }

        function closeButtonEl() {
          return qButton(q(modalEl(), ".smart-slider-close-button"));
        }

        function sliderInputEl() {
          return qInput(q(rootEl(), ".smart-slider-track"));
        }

        function valueInputEl() {
          return qInput(q(rootEl(), ".smart-slider-value-input"));
        }

        function minInputEl() {
          const limits = rootEl() ? rootEl().querySelectorAll(".smart-slider-limit") : [];
          return qInput(limits && limits.length > 0 ? limits[0] : null);
        }

        function maxInputEl() {
          const limits = rootEl() ? rootEl().querySelectorAll(".smart-slider-limit") : [];
          return qInput(limits && limits.length > 1 ? limits[1] : null);
        }

        function titleEl() {
          return q(modalEl(), ".smart-slider-settings-title-text");
        }

        function sendClose(reason) {
          try {
            model.send({ type: "dialog_request", action: "close", reason: reason || "request" });
          } catch (e) {}
        }

        function applyLabels() {
          const controlLabel = model.get("control_label") || "parameter";
          const dialogLabel = model.get("dialog_label") || "Parameter settings";
          const modal = modalEl();
          const panel = panelEl();
          const settingsButton = settingsButtonEl();
          const closeButton = closeButtonEl();
          const sliderInput = sliderInputEl();
          const valueInput = valueInputEl();
          const minInput = minInputEl();
          const maxInput = maxInputEl();
          const title = titleEl();
          const isOpen = !!model.get("dialog_open");

          if (title) {
            title.id = titleId;
          }

          if (panel) {
            panel.id = dialogId;
            panel.setAttribute("role", "dialog");
            panel.setAttribute("aria-modal", "true");
            panel.setAttribute("tabindex", "-1");
            panel.setAttribute("aria-hidden", isOpen ? "false" : "true");
            if (title) {
              panel.setAttribute("aria-labelledby", titleId);
            } else {
              panel.setAttribute("aria-label", dialogLabel);
            }
          }

          if (modal) {
            modal.setAttribute("aria-hidden", isOpen ? "false" : "true");
          }

          if (settingsButton) {
            settingsButton.setAttribute("aria-haspopup", "dialog");
            settingsButton.setAttribute("aria-controls", dialogId);
            settingsButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
          }

          if (closeButton) {
            closeButton.setAttribute("aria-controls", dialogId);
          }

          if (sliderInput) {
            sliderInput.setAttribute("aria-label", `${controlLabel} slider`);
          }

          if (valueInput) {
            valueInput.setAttribute("aria-label", `${controlLabel} value`);
            valueInput.setAttribute("inputmode", "decimal");
          }

          if (minInput) {
            minInput.setAttribute("aria-label", `${controlLabel} minimum`);
            minInput.setAttribute("inputmode", "decimal");
          }

          if (maxInput) {
            maxInput.setAttribute("aria-label", `${controlLabel} maximum`);
            maxInput.setAttribute("inputmode", "decimal");
          }
        }

        function focusDialog() {
          const panel = panelEl();
          if (!panel || !model.get("dialog_open")) return;
          const items = focusables(panel);
          const target = items[0] || panel;
          try {
            target.focus({ preventScroll: true });
          } catch (e) {
            try { target.focus(); } catch (err) {}
          }
        }

        function syncFromModel() {
          applyLabels();
          const isOpen = !!model.get("dialog_open");
          const panel = panelEl();
          const settingsButton = settingsButtonEl();
          if (isOpen) {
            const active = document.activeElement;
            if (active instanceof HTMLElement) {
              returnFocusEl = active;
            } else if (settingsButton instanceof HTMLElement) {
              returnFocusEl = settingsButton;
            }
            requestAnimationFrame(() => focusDialog());
            return;
          }

          if (returnFocusEl instanceof HTMLElement && document.documentElement.contains(returnFocusEl)) {
            try {
              returnFocusEl.focus({ preventScroll: true });
            } catch (e) {
              try { returnFocusEl.focus(); } catch (err) {}
            }
          } else if (settingsButton instanceof HTMLElement) {
            try {
              settingsButton.focus({ preventScroll: true });
            } catch (e) {
              try { settingsButton.focus(); } catch (err) {}
            }
          }

          if (panel instanceof HTMLElement) {
            panel.blur();
          }
        }

        function onKeydown(event) {
          if (!model.get("dialog_open")) return;
          const panel = panelEl();
          if (!(panel instanceof HTMLElement)) return;

          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            sendClose("escape");
            return;
          }

          if (event.key !== "Tab") return;

          const items = focusables(panel);
          if (!items.length) {
            event.preventDefault();
            try { panel.focus({ preventScroll: true }); } catch (e) {}
            return;
          }

          const first = items[0];
          const last = items[items.length - 1];
          const active = document.activeElement;

          if (!panel.contains(active)) {
            event.preventDefault();
            try { first.focus({ preventScroll: true }); } catch (e) { try { first.focus(); } catch (err) {} }
            return;
          }

          if (event.shiftKey && active === first) {
            event.preventDefault();
            try { last.focus({ preventScroll: true }); } catch (e) { try { last.focus(); } catch (err) {} }
            return;
          }

          if (!event.shiftKey && active === last) {
            event.preventDefault();
            try { first.focus({ preventScroll: true }); } catch (e) { try { first.focus(); } catch (err) {} }
          }
        }

        function onDocumentClick(event) {
          if (!model.get("dialog_open")) return;
          const modal = modalEl();
          if (!modal) return;
          if (event.target === modal) {
            sendClose("backdrop");
          }
        }

        const onOpenChange = () => syncFromModel();
        const onLabelChange = () => applyLabels();

        model.on("change:dialog_open", onOpenChange);
        model.on("change:dialog_label", onLabelChange);
        model.on("change:control_label", onLabelChange);
        model.on("change:slider_root_class", onLabelChange);
        model.on("change:modal_class", onLabelChange);
        document.addEventListener("keydown", onKeydown, true);
        document.addEventListener("click", onDocumentClick, true);

        requestAnimationFrame(() => syncFromModel());

        return () => {
          try { model.off("change:dialog_open", onOpenChange); } catch (e) {}
          try { model.off("change:dialog_label", onLabelChange); } catch (e) {}
          try { model.off("change:control_label", onLabelChange); } catch (e) {}
          try { model.off("change:slider_root_class", onLabelChange); } catch (e) {}
          try { model.off("change:modal_class", onLabelChange); } catch (e) {}
          try { document.removeEventListener("keydown", onKeydown, true); } catch (e) {}
          try { document.removeEventListener("click", onDocumentClick, true); } catch (e) {}
        };
      },
    };
    """


class FloatSlider(widgets.VBox):
    """
    A FloatSlider with:
      - a *single editable numeric field* (Text) that accepts expressions via InputConvert,
      - play/pause, reset, and settings buttons,
      - a small settings panel (min/max/step + live update toggle + animation options).

    Design notes
    ------------
    - The slider's built-in readout is disabled, so there is only one number field.
    - The Text field commits on Enter (continuous_update=False). This avoids fighting the
      user while they type partial expressions like "pi/2".
    - If parsing fails, the Text field reverts to the previous committed value.

    Notes
    -----
    The slider exposes ``default_value``, ``min``, ``max``, and ``step`` so it
    can be wrapped by :class:`ParamRef` implementations and used with
    :class:`Figure` parameter management.

    Examples
    --------
    >>> slider = FloatSlider(value=1.0, min=-2.0, max=2.0, step=0.1)  # doctest: +SKIP
    >>> slider.value  # doctest: +SKIP
    1.0
    """

    value = traitlets.Float(0.0)

    def __init__(
        self,
        value: float = 0.0,
        min: float = 0.0,
        max: float = 1.0,
        step: float = 0.1,
        description: str = "Value:",
        **kwargs: Any,
    ) -> None:
        """Create a slider with a single editable numeric field, animation button, and settings panel.

        Parameters
        ----------
        value : float, optional
            Initial value for the slider and numeric text field.
        min : float, optional
            Lower bound for the slider.
        max : float, optional
            Upper bound for the slider.
        step : float, optional
            Increment for the slider and step control.
        description : str, optional
            Label displayed to the left of the control.
        **kwargs : Any
            Additional keyword arguments forwarded to ``widgets.VBox``.

        Returns
        -------
        None
            This constructor initializes the widget in place.

        Examples
        --------
        Create a slider and read its value::

            >>> slider = FloatSlider(value=0.25, min=0.0, max=1.0, step=0.05)
            >>> float(slider.value)
            0.25

        Notes
        -----
        Use :meth:`make_refs` to bind the slider to a SymPy symbol when working
        with :class:`Figure` or :class:`ParameterManager`.
        """
        # Remember defaults for reset
        self._defaults = {"value": value, "min": min, "max": max, "step": step}

        # Internal guards to prevent circular updates.
        self._syncing = False
        self._syncing_animation_settings = False
        self._settings_open = False

        accessibility_label = str(kwargs.pop("accessibility_label", "")).strip()
        self._accessible_label = accessibility_label or _derive_accessibility_label(
            description
        )
        self._slider_root_class = f"smart-slider-instance-{uuid.uuid4().hex[:8]}"
        self._settings_modal_class = f"{self._slider_root_class}-modal"

        root_layout = kwargs.pop("layout", None)
        if root_layout is None:
            root_layout = widgets.Layout(width="100%", min_width="0")

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
            layout=widgets.Layout(flex="1 1 auto", width="auto", min_width="0"),
        )
        self.slider.add_class("smart-slider-track")

        self.description_label = widgets.HTMLMath(
            value=description,
            layout=widgets.Layout(width="auto", min_width="0", margin="0 1px 0 0"),
        )
        self.description_label.add_class("smart-slider-label")

        # self._limit_style = widgets.HTML(
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
        # )

        self._limit_style = widgets.HTML(r"""
<style>
/* Root sizing keeps parameter rows inside the sidebar without phantom x-scroll. */
.smart-slider-root,
.smart-slider-top-row,
.smart-slider-track,
.smart-slider-label,
.smart-slider-value-input,
.smart-slider-settings-panel,
.smart-slider-settings-modal {
  box-sizing: border-box !important;
  min-width: 0 !important;
}

.smart-slider-root,
.smart-slider-top-row {
  width: 100% !important;
}

.smart-slider-top-row {
  align-items: center !important;
  column-gap: 2px !important;
}

.smart-slider-label {
  flex: 0 0 auto !important;
  width: auto !important;
  margin-right: 0 !important;
  white-space: nowrap !important;
}

.smart-slider-track {
  flex: 1 1 auto !important;
  width: auto !important;
  min-width: 0 !important;
  margin: 0 !important;
}

.smart-slider-value-input {
  width: 64px !important;
}

.smart-slider-value-input,
.smart-slider-value-input * {
  min-width: 0 !important;
  margin: 0 !important;
}

.smart-slider-value-input :is(input, textarea) {
  min-width: 0 !important;
}

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

.smart-slider-limit {
  width: 38px !important;
  flex: 0 0 38px !important;
  box-sizing: border-box !important;
  margin: 0 !important;
  padding: 0 !important;
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

/* Icon-only action buttons keep text for assistive tech but show symbols via CSS. */
.smart-slider-icon-button,
.smart-slider-icon-button:hover,
.smart-slider-icon-button:focus,
.smart-slider-icon-button:active,
.smart-slider-icon-button.mod-active,
.smart-slider-icon-button.mod-active:hover,
.smart-slider-icon-button.mod-active:focus,
.smart-slider-icon-button button,
.smart-slider-icon-button button:hover,
.smart-slider-icon-button button:focus,
.smart-slider-icon-button button:active,
.smart-slider-icon-button .widget-button,
.smart-slider-icon-button .widget-button:hover,
.smart-slider-icon-button .widget-button:focus,
.smart-slider-icon-button .jupyter-button,
.smart-slider-icon-button .jupyter-button:hover,
.smart-slider-icon-button .jupyter-button:focus {
  background: transparent !important;
  background-color: transparent !important;
  background-image: none !important;
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

.smart-slider-icon-button {
  position: relative !important;
  overflow: hidden !important;
  border-radius: 6px !important;
  color: var(--jp-ui-font-color1, #334155) !important;
  font-size: 0 !important;
  line-height: 0 !important;
}

.smart-slider-icon-button::before {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  width: 100% !important;
  height: 100% !important;
  font-size: 13px !important;
  line-height: 1 !important;
}

.smart-slider-icon-button:hover,
.smart-slider-icon-button:focus-visible {
  background-color: rgba(15, 23, 42, 0.06) !important;
}

.smart-slider-icon-button :is(button, .widget-button, .jupyter-button):focus-visible,
.smart-slider-value-input :is(input, textarea):focus-visible,
.smart-slider-limit :is(input, textarea):focus-visible,
.smart-slider-settings-panel :is(input, textarea, select, button):focus-visible {
  outline: 2px solid var(--jp-brand-color1, #0b76d1) !important;
  outline-offset: 1px !important;
}

.smart-slider-animate-button::before {
  content: "▶";
}

.smart-slider-animate-button.mod-running {
  color: var(--jp-brand-color1, #0b76d1) !important;
  background-color: rgba(11, 118, 209, 0.08) !important;
}

.smart-slider-animate-button.mod-running::before {
  content: "⏸";
}

.smart-slider-reset-button::before {
  content: "↺";
}

.smart-slider-settings-button::before {
  content: "⚙";
}

.smart-slider-close-button::before {
  content: "✕";
}

/* Modal overlay and panel styling */
.smart-slider-settings-modal {
  z-index: 99999 !important;
  box-sizing: border-box !important;
  align-items: center !important;
  justify-content: center !important;
  overflow-x: hidden !important;
  overflow-y: hidden !important;
  background: rgba(15, 23, 42, 0.12) !important;
}

.smart-slider-settings-modal > * {
  min-width: 0 !important;
  max-width: 100% !important;
}

.smart-slider-settings-modal-hosted {
  position: absolute !important;
  inset: 0 !important;
  width: 100% !important;
  height: 100% !important;
  padding: 12px !important;
}

.smart-slider-settings-modal-global {
  position: fixed !important;
  inset: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  padding: 12px !important;
}

.smart-slider-modal-host {
  position: relative !important;
}

.smart-slider-settings-panel {
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.32) !important;
  border-radius: 10px !important;
  opacity: 1 !important;
  background: #ffffff !important;
  box-sizing: border-box !important;
  width: min(440px, calc(100vw - 32px)) !important;
  min-width: min(380px, calc(100vw - 32px)) !important;
  max-width: min(calc(100% - 24px), calc(100vw - 32px)) !important;
  overflow-x: hidden !important;
  overflow-y: auto !important;
}

.smart-slider-settings-panel > * {
  min-width: 0 !important;
}

.smart-slider-settings-title {
  flex: 1 1 auto !important;
  min-width: 0 !important;
  flex-wrap: wrap !important;
}

.smart-slider-settings-title-text,
.smart-slider-settings-title-subject {
  min-width: 0 !important;
}

.smart-slider-settings-title-subject {
  overflow-wrap: anywhere !important;
}
</style>
""")
        self._limit_style.layout = widgets.Layout(width="0px", height="0px", margin="0px")
        # The *only* numeric field (editable; accepts expressions)
        self.number = widgets.Text(
            value=str(value),
            continuous_update=False,  # commit on Enter (and typically blur)
            layout=widgets.Layout(width="64px", min_width="0"),
        )
        self.number.add_class("smart-slider-value-input")

        self.btn_animate = widgets.Button(
            description="Start animation",
            tooltip="Start animation",
            layout=widgets.Layout(width="24px", min_width="24px", height="24px", padding="0px"),
        )
        self.btn_animate.add_class("smart-slider-icon-button")
        self.btn_animate.add_class("smart-slider-animate-button")
        self.btn_reset = widgets.Button(
            description="Reset parameter",
            tooltip="Reset parameter",
            layout=widgets.Layout(width="24px", min_width="24px", height="24px", padding="0px"),
        )
        self.btn_reset.add_class("smart-slider-icon-button")
        self.btn_reset.add_class("smart-slider-reset-button")
        self.btn_settings = widgets.Button(
            description="Open parameter settings",
            tooltip="Open parameter settings",
            layout=widgets.Layout(width="24px", min_width="24px", height="24px", padding="0px"),
        )
        self.btn_settings.add_class("smart-slider-icon-button")
        self.btn_settings.add_class("smart-slider-settings-button")

        # --- Settings panel ---------------------------------------------------
        style_args = {
            "style": {"description_width": "72px"},
            "layout": widgets.Layout(width="100%", min_width="0"),
        }
        self.set_min = widgets.Text(
            value=f"{min:.4g}",
            continuous_update=False,
            layout=widgets.Layout(width="38px", min_width="0", height="16px", margin="0px"),
        )
        self.set_min.add_class("smart-slider-limit")
        self.set_max = widgets.Text(
            value=f"{max:.4g}",
            continuous_update=False,
            layout=widgets.Layout(width="38px", min_width="0", height="16px", margin="0px"),
        )
        self.set_max.add_class("smart-slider-limit")
        for field, placeholder in (
            (self.number, "value"),
            (self.set_min, "min"),
            (self.set_max, "max"),
        ):
            if hasattr(field, "placeholder"):
                setattr(field, "placeholder", placeholder)
        self.set_step = widgets.FloatText(value=step, description="Step:", **style_args)
        self.set_live = widgets.Checkbox(
            value=True,
            description="Live Update",
            indent=False,
            layout=widgets.Layout(width="100%", min_width="0"),
        )
        self.set_animation_time = widgets.BoundedFloatText(
            value=DEFAULT_ANIMATION_TIME,
            min=0.001,
            step=0.1,
            description="Anim:",
            tooltip="Seconds to traverse the current range once.",
            **style_args,
        )
        self.set_animation_mode = widgets.Dropdown(
            options=(("Loop (>>)", ">>"), ("Once (>)", ">"), ("Bounce (<>)", "<>")),
            value=">>",
            description="Mode:",
            tooltip="Animation mode for this parameter.",
            **style_args,
        )

        self.btn_close_settings = widgets.Button(
            description="Close parameter settings",
            tooltip="Close parameter settings",
            layout=widgets.Layout(width="24px", height="24px", padding="0px"),
        )
        self.btn_close_settings.add_class("smart-slider-icon-button")
        self.btn_close_settings.add_class("smart-slider-close-button")
        self.settings_title_text = widgets.HTML("<b>Parameter settings</b>")
        self.settings_title_text.add_class("smart-slider-settings-title-text")
        self.settings_subject = widgets.HTMLMath(
            value=description,
            layout=widgets.Layout(min_width="0", margin="0px"),
        )
        self.settings_subject.add_class("smart-slider-settings-title-subject")
        self.settings_title = widgets.HBox(
            [
                self.settings_title_text,
                self.settings_subject,
            ],
            layout=widgets.Layout(
                align_items="center",
                gap="4px",
                flex="1 1 auto",
                min_width="0",
                flex_flow="row wrap",
            ),
        )
        self.settings_title.add_class("smart-slider-settings-title")
        settings_header = widgets.HBox(
            [self.settings_title, self.btn_close_settings],
            layout=widgets.Layout(
                justify_content="space-between",
                align_items="flex-start",
                gap="8px",
                width="100%",
                min_width="0",
            ),
        )

        self._settings_accessibility = _SliderModalAccessibilityBridge(
            slider_root_class=self._slider_root_class,
            modal_class=self._settings_modal_class,
            dialog_open=False,
            dialog_label=f"Parameter settings for {self._accessible_label}",
            control_label=self._accessible_label,
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._settings_accessibility.on_msg(self._handle_settings_accessibility_message)

        self.settings_panel = widgets.VBox(
            [
                settings_header,
                widgets.HBox([self.set_step], layout=widgets.Layout(width="100%", min_width="0")),
                widgets.HBox([self.set_live], layout=widgets.Layout(width="100%", min_width="0")),
                widgets.HBox([self.set_animation_time], layout=widgets.Layout(width="100%", min_width="0")),
                widgets.HBox([self.set_animation_mode], layout=widgets.Layout(width="100%", min_width="0")),
            ],
            layout=widgets.Layout(
                width="440px",
                min_width="380px",
                max_width="calc(100vw - 32px)",
                display="none",
                border="1px solid rgba(15, 23, 42, 0.12)",
                padding="12px",
                gap="8px",
                background_color="white",
                opacity="1",
                box_shadow="0 10px 28px rgba(15, 23, 42, 0.28)",
                align_items="stretch",
                overflow_x="hidden",
                overflow_y="auto",
            ),
        )
        self.settings_modal = widgets.Box(
            [self.settings_panel],
            layout=widgets.Layout(
                display="none",
                position="fixed",
                top="0",
                left="0",
                width="100vw",
                height="100vh",
                align_items="center",
                justify_content="center",
                background_color="rgba(15, 23, 42, 0.12)",
                z_index="1000",
                overflow_x="hidden",
                overflow_y="hidden",
            ),
        )
        self.settings_panel.add_class("smart-slider-settings-panel")
        self.settings_modal.add_class("smart-slider-settings-modal")
        self.settings_modal.add_class("smart-slider-settings-modal-global")
        self.settings_modal.add_class(self._settings_modal_class)
        self._top_row: widgets.HBox | None = None
        self._modal_host: widgets.Box | None = None

        # --- Layout -----------------------------------------------------------
        top_row = widgets.HBox(
            [
                self._limit_style,
                self.description_label,
                self.set_min,
                self.slider,
                self.set_max,
                self.number,
                self.btn_animate,
                self.btn_reset,
                self.btn_settings,
            ],
            layout=widgets.Layout(width="100%", min_width="0", align_items="center"),
        )
        top_row.add_class("smart-slider-top-row")
        self._top_row = top_row
        super().__init__(
            [top_row, self._settings_accessibility, self.settings_modal],
            layout=root_layout,
            **kwargs,
        )
        self.add_class("smart-slider-root")
        self.add_class(self._slider_root_class)

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
        self.btn_animate.on_click(self._toggle_animation)
        self.btn_reset.on_click(self._reset)
        self.btn_settings.on_click(self._toggle_settings)
        self.btn_close_settings.on_click(self._close_settings)

        # Settings -> slider traits
        widgets.link((self.set_step, "value"), (self.slider, "step"))
        widgets.link((self.set_live, "value"), (self.slider, "continuous_update"))

        # Initialize trait (and normalize displayed text)
        self.value = value
        self._sync_number_text(self.value)
        self._sync_limit_texts(None)

        self._animation = AnimationController(
            self,
            animation_time=float(self.set_animation_time.value),
            animation_mode=str(self.set_animation_mode.value),
            state_change_callback=self._sync_animation_button,
        )
        self.observe(self._handle_animation_value_change, names="value")
        self.slider.observe(
            self._handle_animation_domain_change,
            names=["min", "max", "step"],
        )
        self.set_animation_time.observe(self._commit_animation_time, names="value")
        self.set_animation_mode.observe(self._commit_animation_mode, names="value")
        self._sync_animation_button(self._animation.running)

    # --- Helpers --------------------------------------------------------------

    @staticmethod
    def _set_class_state(widget: Any, class_name: str, enabled: bool) -> None:
        """Add or remove a CSS class when the widget supports class helpers."""
        add_class = getattr(widget, "add_class", None)
        remove_class = getattr(widget, "remove_class", None)
        if enabled:
            if callable(add_class):
                add_class(class_name)
            return
        if callable(remove_class):
            remove_class(class_name)

    def _handle_settings_accessibility_message(
        self, _widget: Any, content: Any, _buffers: Any
    ) -> None:
        """Handle frontend accessibility requests such as Escape-to-close."""

        if not isinstance(content, dict):
            return
        if content.get("type") != "dialog_request":
            return
        if content.get("action") != "close":
            return
        self.close_settings()

    def _set_settings_open(self, is_open: bool) -> None:
        """Apply settings-dialog visibility and synchronized button state."""

        self._settings_open = bool(is_open)
        self.settings_modal.layout.display = "flex" if self._settings_open else "none"
        self.settings_panel.layout.display = "flex" if self._settings_open else "none"
        self._settings_accessibility.dialog_open = self._settings_open
        next_description = (
            "Close parameter settings"
            if self._settings_open
            else "Open parameter settings"
        )
        self.btn_settings.description = next_description
        self.btn_settings.tooltip = next_description

    def open_settings(self) -> None:
        """Open the parameter settings dialog."""

        self._set_settings_open(True)

    def close_settings(self) -> None:
        """Close the parameter settings dialog."""

        self._set_settings_open(False)

    def _sync_number_text(self, val: float) -> None:
        """Set the text field from a numeric value without triggering parse logic.

        Parameters
        ----------
        val : float
            The numeric value to format and display in the text field.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        self._syncing = True
        try:
            self.number.value = f"{val:.4g}"
        finally:
            self._syncing = False

    def _sync_number_from_slider(self, change: Any) -> None:
        """Update the numeric field when the slider moves.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch
            Traitlets change object that contains the new slider value.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        if self._syncing:
            return
        self._sync_number_text(change.new)

    def _sync_limit_texts(self, change: Any) -> None:
        """Refresh min/max limit text fields from the slider limits.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch or None
            Traitlets change object (unused) or ``None`` when called manually.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        if self._syncing:
            return
        self._syncing = True
        try:
            self.set_min.value = f"{self.slider.min:.4g}"
            self.set_max.value = f"{self.slider.max:.4g}"
        finally:
            self._syncing = False

    def _commit_limit_value(self, change: Any, *, limit: str) -> None:
        """Parse and apply min/max limits from text inputs.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch
            Traitlets change object carrying the new text value.
        limit : {"min", "max"}
            Selects which limit to update.

        Returns
        -------
        None
            This method updates widget state in place.
        """
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

    def _commit_min_value(self, change: Any) -> None:
        """Commit the minimum limit from the min text field.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch
            Traitlets change object carrying the new text value.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        self._commit_limit_value(change, limit="min")

    def _commit_max_value(self, change: Any) -> None:
        """Commit the maximum limit from the max text field.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch
            Traitlets change object carrying the new text value.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        self._commit_limit_value(change, limit="max")

    def _commit_text_value(self, change: Any) -> None:
        """
        Commit text input to the slider when the user finishes editing.

        When the user commits text (Enter / blur):
          - parse via InputConvert,
          - clamp to [min, max],
          - update self.value,
          - normalize the displayed text.

        On any error, revert to the value *before* this edit.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch
            Traitlets change object carrying the new text value.

        Returns
        -------
        None
            This method updates widget state in place.

        Examples
        --------
        Update the value by simulating a commit::

            >>> slider = FloatSlider(value=0.0, min=0.0, max=1.0)
            >>> slider.number.value = "0.5"
            >>> float(slider.value)
            0.5
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

    def _reset(self, _: Any) -> None:
        """Reset the slider value to its initial default.

        Parameters
        ----------
        _ : object
            Click event payload (unused).

        Returns
        -------
        None
            This method updates the value in place (limits are unchanged).

        Notes
        -----
        Public callers should prefer :meth:`reset`.
        """
        self.value = self._defaults[
            "value"
        ]  # slider sync + slider observer updates text

    def _toggle_animation(self, _: Any) -> None:
        """Toggle animation from the small play/pause button."""
        self.toggle_animation()

    def _sync_animation_button(self, running: bool) -> None:
        """Refresh the animation button state from the controller."""
        self.btn_animate.description = (
            "Pause animation" if running else "Start animation"
        )
        self.btn_animate.tooltip = (
            "Pause animation" if running else "Start animation"
        )
        self.btn_animate.button_style = ""
        self._set_class_state(self.btn_animate, "mod-running", running)

    def _handle_animation_value_change(self, change: Any) -> None:
        """Forward external value changes to the animation controller."""
        self._animation.handle_value_change(float(change.new))

    def _handle_animation_domain_change(self, change: Any) -> None:
        """Forward range/step edits to the animation controller."""
        self._animation.handle_domain_change()

    def _commit_animation_time(self, change: Any) -> None:
        """Commit the animation duration from the settings panel."""
        if self._syncing_animation_settings:
            return
        self._animation.animation_time = float(change.new)

    def _commit_animation_mode(self, change: Any) -> None:
        """Commit the animation mode from the settings panel."""
        if self._syncing_animation_settings:
            return
        self._animation.animation_mode = str(change.new)

    @property
    def default_value(self) -> float:
        """Return the stored default value used by reset.

        Returns
        -------
        float
            Default value for the slider reset.

        Notes
        -----
        Setting ``default_value`` does not change the current slider value.
        """
        return float(self._defaults["value"])

    @default_value.setter
    def default_value(self, value: float) -> None:
        """Set the stored default value used by reset.

        Parameters
        ----------
        value : float
            New default value (does not change the current value).

        Returns
        -------
        None

        See Also
        --------
        reset : Apply the stored default value to the slider.
        """
        self._defaults["value"] = float(value)

    @property
    def min(self) -> float:
        """Return the current minimum slider limit.

        Returns
        -------
        float
            Minimum slider value.

        Examples
        --------
        >>> slider = FloatSlider(min=-1.0, max=1.0)  # doctest: +SKIP
        >>> slider.min  # doctest: +SKIP
        -1.0

        Notes
        -----
        Updating the minimum may clamp the current value if it falls below the
        new bound.
        """
        return float(self.slider.min)

    @min.setter
    def min(self, value: float) -> None:
        """Set the minimum slider limit.

        Parameters
        ----------
        value : float
            New minimum value.

        Returns
        -------
        None

        See Also
        --------
        max : Update the upper bound.
        """
        new_min = float(value)
        if new_min > float(self.slider.max):
            self.slider.max = new_min
        self.slider.min = new_min
        self._sync_limit_texts(None)

    @property
    def max(self) -> float:
        """Return the current maximum slider limit.

        Returns
        -------
        float
            Maximum slider value.

        Examples
        --------
        >>> slider = FloatSlider(min=-1.0, max=1.0)  # doctest: +SKIP
        >>> slider.max  # doctest: +SKIP
        1.0

        Notes
        -----
        Updating the maximum may clamp the current value if it exceeds the
        new bound.
        """
        return float(self.slider.max)

    @max.setter
    def max(self, value: float) -> None:
        """Set the maximum slider limit.

        Parameters
        ----------
        value : float
            New maximum value.

        Returns
        -------
        None

        See Also
        --------
        min : Update the lower bound.
        """
        new_max = float(value)
        if new_max < float(self.slider.min):
            self.slider.min = new_max
        self.slider.max = new_max
        self._sync_limit_texts(None)

    @property
    def step(self) -> float:
        """Return the current slider step.

        Returns
        -------
        float
            Step size for the slider.

        Examples
        --------
        >>> slider = FloatSlider(step=0.25)  # doctest: +SKIP
        >>> slider.step  # doctest: +SKIP
        0.25

        Notes
        -----
        The step size affects both the slider and the settings panel control.
        """
        return float(self.slider.step)

    @step.setter
    def step(self, value: float) -> None:
        """Set the slider step size.

        Parameters
        ----------
        value : float
            New step size.

        Returns
        -------
        None

        See Also
        --------
        default_value : Set the reset target without changing the current value.
        """
        self.slider.step = float(value)

    def reset(self) -> None:
        """Reset the slider value to its initial default.

        Returns
        -------
        None

        Examples
        --------
        >>> slider = FloatSlider(value=2.0)  # doctest: +SKIP
        >>> slider.reset()  # doctest: +SKIP

        Notes
        -----
        This uses the stored ``default_value``.
        """
        self._reset(None)

    @property
    def animation_time(self) -> float:
        """Seconds needed to traverse the current numeric range once."""
        return float(self._animation.animation_time)

    @animation_time.setter
    def animation_time(self, value: float) -> None:
        self._animation.animation_time = float(value)
        self._syncing_animation_settings = True
        try:
            self.set_animation_time.value = float(self._animation.animation_time)
        finally:
            self._syncing_animation_settings = False

    @property
    def animation_mode(self) -> str:
        """Animation mode token for this slider."""
        return str(self._animation.animation_mode)

    @animation_mode.setter
    def animation_mode(self, value: str) -> None:
        self._animation.animation_mode = str(value)
        self._syncing_animation_settings = True
        try:
            self.set_animation_mode.value = str(self._animation.animation_mode)
        finally:
            self._syncing_animation_settings = False

    @property
    def animation_running(self) -> bool:
        """Whether the slider is currently animating."""
        return bool(self._animation.running)

    def start_animation(self) -> None:
        """Start animating the slider value."""
        self._animation.start()

    def stop_animation(self) -> None:
        """Stop animating the slider value."""
        self._animation.stop()

    def toggle_animation(self) -> None:
        """Toggle the slider animation state."""
        self._animation.toggle()

    def make_refs(self, symbols: Sequence[Any]) -> dict[Any, Any]:
        """Create ParamRef mappings for provided symbols.

        Parameters
        ----------
        symbols : sequence[sympy.Symbol]
            Symbols to bind to this control (must contain exactly one symbol).

        Returns
        -------
        dict
            Mapping of the symbol to a ``ProxyParamRef``.

        Raises
        ------
        ValueError
            If more than one symbol is provided.

        Examples
        --------
        >>> slider = FloatSlider()  # doctest: +SKIP
        >>> import sympy as sp  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> slider.make_refs([a])  # doctest: +SKIP

        Notes
        -----
        This method exists to integrate with :class:`ParameterManager` and
        :class:`Figure` parameter creation.
        """
        if len(symbols) != 1:
            raise ValueError("FloatSlider only supports a single symbol.")
        from .ParamRef import ProxyParamRef

        symbol = symbols[0]
        return {symbol: ProxyParamRef(symbol, self)}

    def set_modal_host(self, host: widgets.Box | None) -> None:
        """Attach the settings modal to a host container.

        Parameters
        ----------
        host : ipywidgets.Box or None
            Host container to overlay. If ``None``, the modal stays local to the slider.

        Returns
        -------
        None
            Updates widget parenting/layout in place.
        """
        if host is self._modal_host:
            return

        if self._modal_host is not None:
            self._modal_host.children = tuple(
                child
                for child in self._modal_host.children
                if child is not self.settings_modal
            )

        modal_add_class = getattr(self.settings_modal, "add_class", None)
        modal_remove_class = getattr(self.settings_modal, "remove_class", None)

        top_row = cast(widgets.HBox, self._top_row)

        if host is None:
            current_children = cast(tuple[Any, ...], self.children)
            if self.settings_modal not in current_children:
                cast(Any, self).children = (
                    top_row,
                    self._settings_accessibility,
                    self.settings_modal,
                )
            if callable(modal_remove_class):
                modal_remove_class("smart-slider-settings-modal-hosted")
            if callable(modal_add_class):
                modal_add_class("smart-slider-settings-modal-global")
        else:
            cast(Any, self).children = (top_row, self._settings_accessibility)
            add_class = getattr(host, "add_class", None)
            if callable(add_class):
                add_class("smart-slider-modal-host")
            if self.settings_modal not in host.children:
                host.children += (self.settings_modal,)
            if callable(modal_remove_class):
                modal_remove_class("smart-slider-settings-modal-global")
            if callable(modal_add_class):
                modal_add_class("smart-slider-settings-modal-hosted")

        self._modal_host = host

    def _close_settings(self, _: Any) -> None:
        """Close the settings dialog from explicit UI actions."""

        self.close_settings()

    def _toggle_settings(self, _: Any) -> None:
        """Toggle visibility of the settings panel.

        Parameters
        ----------
        _ : object
            Click event payload (unused).

        Returns
        -------
        None
            This method updates widget state in place.
        """
        self._set_settings_open(not self._settings_open)
