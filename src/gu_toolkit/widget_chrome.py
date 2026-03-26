"""Reusable widget chrome for dialogs, form rows, and button styling.

Purpose
-------
The toolkit contains several notebook dialogs and inline icon buttons. Those
widgets repeatedly need the same defensive layout defaults: modal overlays that
respect hosted/global positioning, form rows that do not introduce phantom
horizontal scrollbars, and buttons whose visual styling is consistent across
Jupyter themes.

This module centralizes that chrome so new UI code can follow a single natural
path that is already safe by default.
"""

from __future__ import annotations

from typing import Any, Iterable, Literal

import traitlets

from ._widget_stubs import anywidget, widgets

ButtonVariant = Literal["primary", "secondary", "tab"]
IconButtonRole = Literal[
    "animate",
    "reset",
    "settings",
    "close",
    "plus",
    "edit",
]


_BASE_CSS = r"""
.gu-modal-overlay,
.gu-modal-overlay > *,
.gu-modal-panel,
.gu-modal-panel > *,
.gu-modal-section,
.gu-modal-section > *,
.gu-modal-row,
.gu-modal-row > *,
.gu-modal-status-bar,
.gu-modal-status-bar > *,
.gu-form-field,
.gu-form-field > *,
.gu-fill,
.gu-fill > * {
  box-sizing: border-box !important;
  min-width: 0 !important;
}

.gu-modal-panel,
.gu-modal-section,
.gu-modal-row,
.gu-modal-status-bar,
.gu-form-field,
.gu-fill {
  width: 100% !important;
  max-width: 100% !important;
}

.gu-modal-overlay,
.smart-slider-settings-modal {
  z-index: 99999 !important;
  box-sizing: border-box !important;
  align-items: center !important;
  justify-content: center !important;
  overflow-x: hidden !important;
  overflow-y: hidden !important;
  background: rgba(15, 23, 42, 0.12) !important;
}

.gu-modal-overlay > *,
.smart-slider-settings-modal > * {
  min-width: 0 !important;
  max-width: 100% !important;
}

.gu-modal-overlay-hosted,
.smart-slider-settings-modal-hosted {
  position: absolute !important;
  inset: 0 !important;
  width: 100% !important;
  height: 100% !important;
  padding: 12px !important;
}

.gu-modal-overlay-global,
.smart-slider-settings-modal-global {
  position: fixed !important;
  inset: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  padding: 12px !important;
}

.gu-modal-host,
.smart-slider-modal-host {
  position: relative !important;
}

.gu-modal-panel,
.smart-slider-settings-panel {
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.32) !important;
  border-radius: 10px !important;
  opacity: 1 !important;
  background: #ffffff !important;
  box-sizing: border-box !important;
  max-width: min(calc(100% - 24px), calc(100vw - 32px)) !important;
  overflow-x: hidden !important;
  overflow-y: auto !important;
}

.gu-modal-panel *,
.smart-slider-settings-panel * {
  box-sizing: border-box !important;
  min-width: 0 !important;
  max-width: 100% !important;
}

.gu-modal-panel :is(
  .widget-inline-hbox,
  .widget-inline-vbox,
  .widget-box,
  .jupyter-widgets,
  .widget-text,
  .widget-textarea,
  .widget-dropdown,
  .widget-select,
  .widget-select-multiple,
  .widget-html,
  .widget-htmlmath,
  .widget-label,
  .widget-checkbox
),
.smart-slider-settings-panel :is(
  .widget-inline-hbox,
  .widget-inline-vbox,
  .widget-box,
  .jupyter-widgets,
  .widget-text,
  .widget-textarea,
  .widget-dropdown,
  .widget-select,
  .widget-select-multiple,
  .widget-html,
  .widget-htmlmath,
  .widget-label,
  .widget-checkbox
) {
  min-width: 0 !important;
  max-width: 100% !important;
}

.gu-modal-panel :is(
  textarea,
  select,
  input:not([type='checkbox']):not([type='radio']):not([type='color']):not([type='button']):not([type='submit']):not([type='reset'])
),
.smart-slider-settings-panel :is(
  textarea,
  select,
  input:not([type='checkbox']):not([type='radio']):not([type='color']):not([type='button']):not([type='submit']):not([type='reset'])
) {
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}

.gu-modal-panel :is(select[multiple], .widget-select-multiple select),
.smart-slider-settings-panel :is(select[multiple], .widget-select-multiple select) {
  overflow-x: hidden !important;
}

.gu-modal-panel pre,
.gu-modal-panel code,
.smart-slider-settings-panel pre,
.smart-slider-settings-panel code {
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
}

.gu-form-field-label {
  font-weight: 600 !important;
  color: #0f172a !important;
}

.gu-wrap-row {
  flex-wrap: wrap !important;
  align-items: flex-start !important;
}

.gu-modal-header {
  align-items: flex-start !important;
  padding-bottom: 10px !important;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08) !important;
}

.gu-modal-header-copy {
  flex: 1 1 auto !important;
  min-width: 0 !important;
}

.gu-modal-title-eyebrow {
  margin: 0 !important;
  font-size: 11px !important;
  line-height: 1.3 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  font-weight: 700 !important;
  color: #64748b !important;
}

.gu-modal-title-text {
  margin: 0 !important;
  font-size: 22px !important;
  line-height: 1.2 !important;
  font-weight: 700 !important;
  color: #0f172a !important;
}

.gu-modal-subtitle {
  margin: 0 !important;
  font-size: 13px !important;
  line-height: 1.4 !important;
  color: #475569 !important;
}

.gu-modal-status-bar {
  font-size: 12px !important;
  line-height: 1.4 !important;
  color: #475569 !important;
  background: rgba(15, 23, 42, 0.04) !important;
  border: 1px solid rgba(15, 23, 42, 0.08) !important;
  border-radius: 8px !important;
  padding: 6px 10px !important;
}

:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button),
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button):hover,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button):focus,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button):active,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button).mod-active,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button).mod-active:hover,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button).mod-active:focus,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) button,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) button:hover,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) button:focus,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) button:active,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) .widget-button,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) .widget-button:hover,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) .widget-button:focus,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) .jupyter-button,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) .jupyter-button:hover,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) .jupyter-button:focus {
  background: transparent !important;
  background-color: transparent !important;
  background-image: none !important;
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) {
  position: relative !important;
  overflow: hidden !important;
  border-radius: 999px !important;
  color: var(--jp-ui-font-color1, #334155) !important;
  font-size: 0 !important;
  line-height: 0 !important;
}

:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button)::before {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  width: 100% !important;
  height: 100% !important;
  font-size: 13px !important;
  line-height: 1 !important;
}

:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button):hover,
:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button):focus-visible {
  background-color: rgba(15, 23, 42, 0.06) !important;
}

:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) :is(button, .widget-button, .jupyter-button) {
  padding: 0 !important;
  min-width: 0 !important;
}

:is(.smart-slider-icon-button, .gu-inline-icon-button, .gu-legend-inline-button) :is(button, .widget-button, .jupyter-button):focus-visible,
.gu-action-button :is(button, .widget-button, .jupyter-button):focus-visible,
.gu-modal-panel :is(input, textarea, select, button):focus-visible,
.smart-slider-settings-panel :is(input, textarea, select, button):focus-visible {
  outline: 2px solid var(--jp-brand-color1, #0b76d1) !important;
  outline-offset: 1px !important;
}

.smart-slider-animate-button::before {
  content: ">>";
}

.smart-slider-animate-button.mod-mode-once::before {
  content: ">";
}

.smart-slider-animate-button.mod-mode-loop::before {
  content: ">>";
}

.smart-slider-animate-button.mod-mode-bounce::before {
  content: "<>";
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

.smart-slider-close-button::before,
.gu-icon-close-button::before {
  content: "✕";
}

.gu-icon-plus-button::before {
  content: "+";
}

.gu-icon-edit-button::before {
  content: "✎";
}

.gu-action-button,
.gu-action-button:hover,
.gu-action-button:focus,
.gu-action-button:active,
.gu-action-button button,
.gu-action-button button:hover,
.gu-action-button button:focus,
.gu-action-button button:active,
.gu-action-button .widget-button,
.gu-action-button .widget-button:hover,
.gu-action-button .widget-button:focus,
.gu-action-button .jupyter-button,
.gu-action-button .jupyter-button:hover,
.gu-action-button .jupyter-button:focus {
  background: transparent !important;
  background-color: transparent !important;
  background-image: none !important;
  border: none !important;
  padding: 0 !important;
  box-shadow: none !important;
  outline: none !important;
}

.gu-action-button button,
.gu-action-button .widget-button,
.gu-action-button .jupyter-button {
  min-height: 32px !important;
  padding: 0 12px !important;
  border-radius: 8px !important;
  border: 1px solid rgba(15, 23, 42, 0.14) !important;
  font-weight: 600 !important;
  transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease !important;
}

.gu-action-button-secondary button,
.gu-action-button-secondary .widget-button,
.gu-action-button-secondary .jupyter-button {
  background: #ffffff !important;
  color: #334155 !important;
}

.gu-action-button-secondary:hover button,
.gu-action-button-secondary:hover .widget-button,
.gu-action-button-secondary:hover .jupyter-button,
.gu-action-button-secondary:focus-visible button,
.gu-action-button-secondary:focus-visible .widget-button,
.gu-action-button-secondary:focus-visible .jupyter-button {
  background: rgba(15, 23, 42, 0.05) !important;
  border-color: rgba(15, 23, 42, 0.22) !important;
}

.gu-action-button-primary button,
.gu-action-button-primary .widget-button,
.gu-action-button-primary .jupyter-button {
  background: var(--jp-brand-color1, #0b76d1) !important;
  border-color: var(--jp-brand-color1, #0b76d1) !important;
  color: #ffffff !important;
}

.gu-action-button-primary:hover button,
.gu-action-button-primary:hover .widget-button,
.gu-action-button-primary:hover .jupyter-button,
.gu-action-button-primary:focus-visible button,
.gu-action-button-primary:focus-visible .widget-button,
.gu-action-button-primary:focus-visible .jupyter-button {
  background: #095fa7 !important;
  border-color: #095fa7 !important;
}

.gu-tab-bar {
  padding: 4px !important;
  gap: 4px !important;
  border-radius: 12px !important;
  background: rgba(15, 23, 42, 0.04) !important;
  border: 1px solid rgba(15, 23, 42, 0.08) !important;
}

.gu-action-button-tab button,
.gu-action-button-tab .widget-button,
.gu-action-button-tab .jupyter-button {
  background: transparent !important;
  border-color: transparent !important;
  color: #475569 !important;
  border-radius: 8px !important;
}

.gu-action-button-tab:hover button,
.gu-action-button-tab:hover .widget-button,
.gu-action-button-tab:hover .jupyter-button,
.gu-action-button-tab:focus-visible button,
.gu-action-button-tab:focus-visible .widget-button,
.gu-action-button-tab:focus-visible .jupyter-button {
  background: rgba(15, 23, 42, 0.06) !important;
  border-color: rgba(15, 23, 42, 0.10) !important;
  color: #334155 !important;
}

.gu-action-button-tab.mod-selected button,
.gu-action-button-tab.mod-selected .widget-button,
.gu-action-button-tab.mod-selected .jupyter-button {
  background: #ffffff !important;
  border-color: rgba(11, 118, 209, 0.18) !important;
  color: var(--jp-brand-color1, #0b76d1) !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08) !important;
}

.gu-action-button-tab button,
.gu-action-button-tab .widget-button,
.gu-action-button-tab .jupyter-button,
.gu-action-button-tab:hover button,
.gu-action-button-tab:hover .widget-button,
.gu-action-button-tab:hover .jupyter-button,
.gu-action-button-tab:focus-visible button,
.gu-action-button-tab:focus-visible .widget-button,
.gu-action-button-tab:focus-visible .jupyter-button {
  min-height: 34px !important;
  padding: 0 14px !important;
}
"""


def _set_if_missing(layout: Any, attr_name: str, value: str) -> None:
    if layout is None:
        return
    current = getattr(layout, attr_name, None)
    if current in (None, ""):
        setattr(layout, attr_name, value)


def set_widget_class_state(widget: Any, class_name: str, enabled: bool) -> None:
    """Add or remove one CSS class when supported by the widget."""

    add_class = getattr(widget, "add_class", None)
    remove_class = getattr(widget, "remove_class", None)
    if enabled:
        if callable(add_class):
            add_class(class_name)
        return
    if callable(remove_class):
        remove_class(class_name)


def add_widget_classes(widget: Any, *class_names: str) -> Any:
    """Apply every non-empty CSS class to ``widget`` and return it."""

    add_class = getattr(widget, "add_class", None)
    if callable(add_class):
        for class_name in class_names:
            if class_name:
                add_class(class_name)
    return widget


def ensure_fill_layout(widget: Any) -> Any:
    """Give a widget the defensive width defaults used by shared forms."""

    layout = getattr(widget, "layout", None)
    if layout is None:
        return widget
    _set_if_missing(layout, "width", "100%")
    _set_if_missing(layout, "min_width", "0")
    return widget


def full_width_layout(**overrides: str) -> widgets.Layout:
    """Return a layout that stretches safely without causing x-overflow."""

    base: dict[str, str] = {"width": "100%", "min_width": "0"}
    base.update(overrides)
    return widgets.Layout(**base)


def hosted_modal_dimensions(
    *,
    preferred_width_px: int,
    minimum_width_px: int,
    gutter_px: int = 24,
) -> tuple[str, str, str]:
    """Return container-relative width strings for hosted modal panels.

    The returned values deliberately size the panel against its hosting widget
    container rather than the browser viewport. That avoids the recurring bug
    where a modal hosted inside a narrower notebook output uses ``100vw``-based
    sizing and introduces phantom horizontal scrollbars.
    """

    inner_width = f"calc(100% - {int(gutter_px)}px)"
    return (
        f"min({int(preferred_width_px)}px, {inner_width})",
        f"min({int(minimum_width_px)}px, {inner_width})",
        inner_width,
    )


def vbox(
    children: Iterable[widgets.Widget],
    *,
    gap: str = "8px",
    extra_classes: Iterable[str] = (),
    **layout_overrides: str,
) -> widgets.VBox:
    """Return a full-width vertical container with defensive layout defaults."""

    widget = widgets.VBox(
        list(children),
        layout=full_width_layout(gap=gap, **layout_overrides),
    )
    add_widget_classes(widget, "gu-modal-section", *tuple(extra_classes))
    return widget


def hbox(
    children: Iterable[widgets.Widget],
    *,
    gap: str = "8px",
    extra_classes: Iterable[str] = (),
    **layout_overrides: str,
) -> widgets.HBox:
    """Return a full-width horizontal container with defensive layout defaults."""

    overrides = {"gap": gap, "align_items": "center"}
    overrides.update(layout_overrides)
    widget = widgets.HBox(list(children), layout=full_width_layout(**overrides))
    add_widget_classes(widget, "gu-modal-row", *tuple(extra_classes))
    return widget


def responsive_row(
    children: Iterable[widgets.Widget],
    *,
    gap: str = "8px",
    extra_classes: Iterable[str] = (),
    **layout_overrides: str,
) -> widgets.HBox:
    """Return a wrapping form row for compact controls in responsive dialogs."""

    overrides = {"gap": gap, "align_items": "flex-start", "flex_flow": "row wrap"}
    overrides.update(layout_overrides)
    widget = widgets.HBox(list(children), layout=full_width_layout(**overrides))
    add_widget_classes(widget, "gu-modal-row", "gu-wrap-row", *tuple(extra_classes))
    return widget


def labelled_field(
    title: str | widgets.Widget,
    field: widgets.Widget,
    *,
    flex: str | None = None,
    width: str | None = None,
    max_width: str | None = "100%",
    extra_classes: Iterable[str] = (),
) -> widgets.VBox:
    """Wrap one field in a labelled row that avoids intrinsic-width overflow."""

    ensure_fill_layout(field)
    if isinstance(title, str):
        label: widgets.Widget = widgets.HTML(
            f"<span class='gu-form-field-label'>{title}</span>",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
    else:
        label = title
        ensure_fill_layout(label)
    wrapper = vbox([label, field], gap="4px", extra_classes=("gu-form-field", *tuple(extra_classes)))
    if flex is not None:
        wrapper.layout.flex = flex
    if width is not None:
        wrapper.layout.width = width
    if max_width is not None:
        wrapper.layout.max_width = max_width
    return wrapper


def configure_icon_button(
    button: widgets.Button,
    *,
    role: IconButtonRole | None = None,
    size_px: int = 24,
    extra_classes: Iterable[str] = (),
) -> widgets.Button:
    """Apply shared icon-button chrome and the requested glyph role."""

    width = f"{int(size_px)}px"
    if getattr(button, "layout", None) is None:
        button.layout = widgets.Layout()
    button.layout.width = width
    button.layout.min_width = width
    button.layout.height = width
    button.layout.margin = getattr(button.layout, "margin", None) or "0"
    button.layout.padding = "0px"
    add_widget_classes(button, "smart-slider-icon-button", "gu-inline-icon-button", *tuple(extra_classes))
    role_classes = {
        "animate": ("smart-slider-animate-button",),
        "reset": ("smart-slider-reset-button",),
        "settings": ("smart-slider-settings-button",),
        "close": ("smart-slider-close-button", "gu-icon-close-button"),
        "plus": ("gu-icon-plus-button",),
        "edit": ("gu-icon-edit-button",),
    }
    for class_name in role_classes.get(role, ()):  # pragma: no branch - tiny dict lookup
        add_widget_classes(button, class_name)
    return button


def configure_action_button(
    button: widgets.Button,
    *,
    variant: ButtonVariant = "secondary",
    min_width_px: int = 88,
    extra_classes: Iterable[str] = (),
) -> widgets.Button:
    """Apply shared text-button chrome used by dialogs and tab selectors."""

    if getattr(button, "layout", None) is None:
        button.layout = widgets.Layout()
    button.layout.width = getattr(button.layout, "width", None) or "auto"
    button.layout.min_width = f"{int(min_width_px)}px"
    add_widget_classes(
        button,
        "gu-action-button",
        f"gu-action-button-{variant}",
        *tuple(extra_classes),
    )
    return button


def set_tab_button_selected(button: widgets.Button, selected: bool) -> None:
    """Toggle the CSS class used by shared segmented-tab buttons."""

    set_widget_class_state(button, "mod-selected", bool(selected))


def build_modal_panel(
    children: Iterable[widgets.Widget],
    *,
    width: str,
    min_width: str,
    max_width: str = "calc(100vw - 32px)",
    padding: str = "12px",
    gap: str = "8px",
    display: str = "none",
    extra_classes: Iterable[str] = (),
) -> widgets.VBox:
    """Create a shared modal panel with consistent overflow protection."""

    panel = widgets.VBox(
        list(children),
        layout=widgets.Layout(
            width=width,
            min_width=min_width,
            max_width=max_width,
            display=display,
            border="1px solid rgba(15, 23, 42, 0.12)",
            padding=padding,
            gap=gap,
            background_color="white",
            opacity="1",
            box_shadow="0 10px 28px rgba(15, 23, 42, 0.28)",
            align_items="stretch",
            overflow_x="hidden",
            overflow_y="auto",
        ),
    )
    add_widget_classes(panel, "smart-slider-settings-panel", "gu-modal-panel", *tuple(extra_classes))
    return panel


def build_modal_overlay(
    panel: widgets.Widget,
    *,
    modal_class: str = "",
    hosted: bool = True,
    z_index: str = "1000",
    background_color: str = "rgba(15, 23, 42, 0.12)",
) -> widgets.Box:
    """Create a shared modal overlay that reuses slider-style modal chrome."""

    overlay = widgets.Box(
        [panel],
        layout=widgets.Layout(
            display="none",
            position="absolute" if hosted else "fixed",
            top="0",
            left="0",
            width="100%" if hosted else "100vw",
            height="100%" if hosted else "100vh",
            align_items="center",
            justify_content="center",
            background_color=background_color,
            z_index=z_index,
            overflow_x="hidden",
            overflow_y="hidden",
        ),
    )
    add_widget_classes(
        overlay,
        "smart-slider-settings-modal",
        "gu-modal-overlay",
        "smart-slider-settings-modal-hosted" if hosted else "smart-slider-settings-modal-global",
        "gu-modal-overlay-hosted" if hosted else "gu-modal-overlay-global",
        modal_class,
    )
    return overlay


def attach_host_children(host: widgets.Box | None, *children: widgets.Widget) -> None:
    """Append unique widgets to one host container in order."""

    if host is None:
        return
    current = list(host.children)
    changed = False
    add_class = getattr(host, "add_class", None)
    if callable(add_class):
        add_class("smart-slider-modal-host")
        add_class("gu-modal-host")
    for child in children:
        if child not in current:
            current.append(child)
            changed = True
    if changed:
        host.children = tuple(current)


def shared_style_widget(*css_fragments: str) -> widgets.HTML:
    """Return a hidden ``HTML`` widget containing shared chrome CSS."""

    css = _BASE_CSS + "".join(str(fragment or "") for fragment in css_fragments)
    return widgets.HTML(
        value=f"<style>{css}</style>",
        layout=widgets.Layout(width="0px", height="0px", margin="0px"),
    )


class ModalDialogBridge(anywidget.AnyWidget):
    """Frontend bridge for modal dialog semantics and keyboard handling."""

    modal_class = traitlets.Unicode("").tag(sync=True)
    panel_selector = traitlets.Unicode(".gu-modal-panel").tag(sync=True)
    close_selector = traitlets.Unicode(".gu-icon-close-button").tag(sync=True)
    title_selector = traitlets.Unicode(".gu-modal-title-text").tag(sync=True)
    dialog_open = traitlets.Bool(False).tag(sync=True)
    dialog_label = traitlets.Unicode("Dialog").tag(sync=True)
    return_focus_selector = traitlets.Unicode("").tag(sync=True)

    _esm = r"""
    function q(node, selector) {
      return node ? node.querySelector(selector) : null;
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
        const dialogId = `gu-modal-${Math.random().toString(16).slice(2)}`;
        const titleId = `${dialogId}-title`;
        let returnFocusEl = null;

        function modalEl() {
          const className = model.get("modal_class") || "";
          return className ? document.querySelector(`.${className}`) : null;
        }

        function panelEl() {
          const modal = modalEl();
          if (!modal) return null;
          const selector = model.get("panel_selector") || ".gu-modal-panel";
          return modal.querySelector(selector) || modal.firstElementChild;
        }

        function closeButtonEl() {
          return q(modalEl(), model.get("close_selector") || ".gu-icon-close-button");
        }

        function titleEl() {
          return q(modalEl(), model.get("title_selector") || ".gu-modal-title-text");
        }

        function sendClose(reason) {
          try {
            model.send({ type: "dialog_request", action: "close", reason: reason || "request" });
          } catch (_error) {}
        }

        function applyState() {
          const modal = modalEl();
          const panel = panelEl();
          const title = titleEl();
          const closeButton = closeButtonEl();
          const isOpen = !!model.get("dialog_open");
          const label = model.get("dialog_label") || "Dialog";

          if (title instanceof HTMLElement) {
            title.id = titleId;
          }

          if (panel instanceof HTMLElement) {
            panel.id = dialogId;
            panel.setAttribute("role", "dialog");
            panel.setAttribute("aria-modal", "true");
            panel.setAttribute("tabindex", "-1");
            panel.setAttribute("aria-hidden", isOpen ? "false" : "true");
            if (title instanceof HTMLElement) {
              panel.setAttribute("aria-labelledby", titleId);
            } else {
              panel.setAttribute("aria-label", label);
            }
          }

          if (modal instanceof HTMLElement) {
            modal.setAttribute("aria-hidden", isOpen ? "false" : "true");
          }

          if (closeButton instanceof HTMLElement) {
            closeButton.setAttribute("aria-controls", dialogId);
          }
        }

        function focusDialog() {
          const panel = panelEl();
          if (!(panel instanceof HTMLElement) || !model.get("dialog_open")) return;
          const items = focusables(panel);
          const target = items[0] || panel;
          try {
            target.focus({ preventScroll: true });
          } catch (_error) {
            try { target.focus(); } catch (_inner) {}
          }
        }

        function restoreFocus() {
          const selector = model.get("return_focus_selector") || "";
          const preferred = selector ? document.querySelector(selector) : null;
          const target = document.documentElement.contains(returnFocusEl)
            ? returnFocusEl
            : (preferred instanceof HTMLElement ? preferred : null);
          if (target instanceof HTMLElement) {
            try {
              target.focus({ preventScroll: true });
            } catch (_error) {
              try { target.focus(); } catch (_inner) {}
            }
            return;
          }
          const panel = panelEl();
          if (panel instanceof HTMLElement) {
            panel.blur();
          }
        }

        function syncFromModel() {
          applyState();
          const isOpen = !!model.get("dialog_open");
          if (isOpen) {
            const active = document.activeElement;
            if (active instanceof HTMLElement) {
              returnFocusEl = active;
            }
            requestAnimationFrame(() => focusDialog());
            return;
          }
          restoreFocus();
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
            try { panel.focus({ preventScroll: true }); } catch (_error) {}
            return;
          }

          const first = items[0];
          const last = items[items.length - 1];
          const active = document.activeElement;

          if (!panel.contains(active)) {
            event.preventDefault();
            try { first.focus({ preventScroll: true }); } catch (_error) { try { first.focus(); } catch (_inner) {} }
            return;
          }

          if (event.shiftKey && active === first) {
            event.preventDefault();
            try { last.focus({ preventScroll: true }); } catch (_error) { try { last.focus(); } catch (_inner) {} }
            return;
          }

          if (!event.shiftKey && active === last) {
            event.preventDefault();
            try { first.focus({ preventScroll: true }); } catch (_error) { try { first.focus(); } catch (_inner) {} }
          }
        }

        function onDocumentClick(event) {
          if (!model.get("dialog_open")) return;
          const modal = modalEl();
          if (!(modal instanceof HTMLElement)) return;
          if (event.target === modal) {
            sendClose("backdrop");
          }
        }

        const onModelChange = () => syncFromModel();
        model.on("change:dialog_open", onModelChange);
        model.on("change:dialog_label", onModelChange);
        model.on("change:modal_class", onModelChange);
        model.on("change:panel_selector", onModelChange);
        model.on("change:close_selector", onModelChange);
        model.on("change:title_selector", onModelChange);
        model.on("change:return_focus_selector", onModelChange);
        document.addEventListener("keydown", onKeydown, true);
        document.addEventListener("click", onDocumentClick, true);

        requestAnimationFrame(() => syncFromModel());

        return () => {
          try { model.off("change:dialog_open", onModelChange); } catch (_error) {}
          try { model.off("change:dialog_label", onModelChange); } catch (_error) {}
          try { model.off("change:modal_class", onModelChange); } catch (_error) {}
          try { model.off("change:panel_selector", onModelChange); } catch (_error) {}
          try { model.off("change:close_selector", onModelChange); } catch (_error) {}
          try { model.off("change:title_selector", onModelChange); } catch (_error) {}
          try { model.off("change:return_focus_selector", onModelChange); } catch (_error) {}
          try { document.removeEventListener("keydown", onKeydown, true); } catch (_error) {}
          try { document.removeEventListener("click", onDocumentClick, true); } catch (_error) {}
        };
      },
    };
    """


__all__ = [
    "ModalDialogBridge",
    "add_widget_classes",
    "attach_host_children",
    "build_modal_overlay",
    "build_modal_panel",
    "configure_action_button",
    "configure_icon_button",
    "ensure_fill_layout",
    "full_width_layout",
    "hbox",
    "hosted_modal_dimensions",
    "labelled_field",
    "responsive_row",
    "set_tab_button_selected",
    "set_widget_class_state",
    "shared_style_widget",
    "vbox",
]
