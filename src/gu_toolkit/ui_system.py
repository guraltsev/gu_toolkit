"""Shared UI system for notebook theming and layout.

This module defines the *single* shared presentation layer used by the toolkit's
widget-based surfaces. It intentionally separates four concerns:

* design tokens such as spacing, radii, control heights, typography, and colors;
* layout primitives such as panel surfaces, dialog shells, headers, action bars,
  section containers, and tab bars;
* shared control helpers for buttons and labelled form rows;
* CSS resource loading so generic chrome lives in readable stylesheet files.

Feature modules should compose these helpers instead of redefining generic
button or dialog styling locally. That keeps the theming code maintainable and
makes layout guardrails enforceable.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Literal

from ._widget_stubs import widgets

ButtonVariant = Literal["primary", "secondary", "tab"]
IconButtonRole = Literal[
    "animate",
    "reset",
    "settings",
    "close",
    "plus",
    "edit",
]
PanelVariant = Literal["card", "minimal", "toolbar"]


@dataclass(frozen=True)
class SectionPanel:
    """Shared figure/sidebar section panel bundle.

    The returned bundle keeps the ownership boundaries explicit: callers can use
    ``panel`` as the mounted surface, ``body`` as the content host owned by a
    feature manager, and ``toolbar`` as an optional header tool slot.
    """

    panel: widgets.VBox
    header: widgets.HBox
    title: widgets.HTML
    toolbar: widgets.HBox
    body: widgets.VBox


_CSS_DIR = Path(__file__).resolve().parent / "css"
_BASE_THEME_RESOURCES: tuple[str, ...] = (
    "tokens.css",
    "controls.css",
    "surfaces.css",
)


@lru_cache(maxsize=None)
def _read_css_resource(resource_name: str) -> str:
    path = _CSS_DIR / str(resource_name)
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def shared_theme_css() -> str:
    """Return the shared base theme CSS loaded from resource files."""

    return "\n\n".join(_read_css_resource(name) for name in _BASE_THEME_RESOURCES)


def load_ui_css(*resource_names: str) -> str:
    """Load one or more stylesheet resources from ``src/gu_toolkit/css``."""

    return "\n\n".join(
        _read_css_resource(name)
        for name in resource_names
        if str(name or "").strip()
    )


def style_widget_value(*css_fragments: str, include_base: bool = True) -> str:
    """Return the HTML payload used by hidden stylesheet widgets."""

    css_parts: list[str] = []
    if include_base:
        css_parts.append(shared_theme_css())
    css_parts.extend(str(fragment or "") for fragment in css_fragments if str(fragment or ""))
    css = "\n\n".join(part for part in css_parts if part)
    if not css:
        return ""
    return f"<style>\n{css}\n</style>"


def _set_if_missing(layout: Any, attr_name: str, value: str) -> None:
    if layout is None:
        return
    current = getattr(layout, attr_name, None)
    if current in (None, ""):
        setattr(layout, attr_name, value)


def _layout_trait_names() -> frozenset[str]:
    try:
        probe = widgets.Layout()
    except Exception:
        return frozenset()
    keys = getattr(probe, "keys", ())
    if callable(keys):
        keys = keys()
    return frozenset(str(key) for key in keys)


_LAYOUT_TRAIT_NAMES = _layout_trait_names()


def build_layout(**kwargs: str) -> widgets.Layout:
    """Return a layout while preserving extra attrs unsupported by some builds.

    Real ``ipywidgets.Layout`` accepts only a fixed trait set in its constructor.
    Some notebook builds drop extra keyword arguments such as ``overflow_x`` or
    ``gap`` entirely, which means later code and tests cannot inspect the values
    that higher-level layout helpers intended to apply. This helper keeps the
    supported traits in the constructor, attaches the extra fields afterwards,
    and maps axis-specific overflow requests onto the supported ``overflow``
    shorthand when the caller did not provide one explicitly.
    """

    extras: dict[str, str] = {}
    overflow_x = kwargs.pop("overflow_x", None)
    overflow_y = kwargs.pop("overflow_y", None)
    overflow = kwargs.get("overflow")
    if overflow in (None, "") and (overflow_x is not None or overflow_y is not None):
        ox = "visible" if overflow_x is None else str(overflow_x)
        oy = ox if overflow_y is None else str(overflow_y)
        kwargs["overflow"] = f"{ox} {oy}"

    ctor_kwargs: dict[str, str] = {}
    for key, value in kwargs.items():
        if key in _LAYOUT_TRAIT_NAMES:
            ctor_kwargs[key] = value
        else:
            extras[key] = value

    layout = widgets.Layout(**ctor_kwargs)
    if overflow_x is not None:
        extras["overflow_x"] = str(overflow_x)
    if overflow_y is not None:
        extras["overflow_y"] = str(overflow_y)
    for key, value in extras.items():
        setattr(layout, key, value)
    return layout


def set_widget_class_state(widget: Any, class_name: str, enabled: bool) -> None:
    """Add or remove one CSS class when supported by ``widget``."""

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
    _set_if_missing(layout, "max_width", "100%")
    return widget


def full_width_layout(**overrides: str) -> widgets.Layout:
    """Return a layout that stretches safely without causing x-overflow."""

    base: dict[str, str] = {"width": "100%", "min_width": "0", "max_width": "100%"}
    base.update(overrides)
    return build_layout(**base)


def full_width_box_layout(**overrides: str) -> widgets.Layout:
    """Return shared box defaults that opt out of ipywidgets' auto scrollbars.

    Jupyter's generic ``Box`` widgets default to ``overflow: auto``. That is a
    sensible fallback for arbitrary layout containers, but it can expose stray
    cross-axis scrollbars when a native control ends up a pixel taller than its
    host row. Shared structural boxes therefore default to a non-scrolling
    vertical overflow policy and let true scroll surfaces opt back in.
    """

    base: dict[str, str] = {
        "width": "100%",
        "min_width": "0",
        "max_width": "100%",
        "overflow_x": "hidden",
        "overflow_y": "visible",
    }
    base.update(overrides)
    return build_layout(**base)


def hosted_modal_dimensions(
    *,
    preferred_width_px: int,
    minimum_width_px: int,
    gutter_px: int = 24,
) -> tuple[str, str, str]:
    """Return container-relative width strings for hosted modal panels."""

    inner_width = f"calc(100% - {int(gutter_px)}px)"
    return (
        f"min({int(preferred_width_px)}px, {inner_width})",
        f"min({int(minimum_width_px)}px, {inner_width})",
        inner_width,
    )


def shared_style_widget(*css_fragments: str, include_base: bool = True) -> widgets.HTML:
    """Return a hidden widget containing shared UI CSS and optional overrides."""

    return widgets.HTML(
        value=style_widget_value(*css_fragments, include_base=include_base),
        layout=build_layout(width="0px", height="0px", margin="0px"),
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
        layout=full_width_box_layout(gap=gap, **layout_overrides),
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
    widget = widgets.HBox(list(children), layout=full_width_box_layout(**overrides))
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
    widget = widgets.HBox(list(children), layout=full_width_box_layout(**overrides))
    add_widget_classes(widget, "gu-modal-row", "gu-wrap-row", *tuple(extra_classes))
    return widget


def configure_control(
    widget: widgets.Widget,
    *,
    family: str = "text",
    extra_classes: Iterable[str] = (),
) -> widgets.Widget:
    """Apply shared control classes to a widget.

    The helper is intentionally lightweight: visual chrome is defined by CSS,
    while the function only supplies width defaults and family class names.
    """

    ensure_fill_layout(widget)

    single_line_families = {"text", "numeric", "dropdown", "color", "math"}
    shell_families = single_line_families | {"checkbox", "boolean"}
    layout = getattr(widget, "layout", None)
    if layout is not None and family in shell_families:
        _set_if_missing(layout, "overflow_x", "hidden")
    if layout is not None and family in single_line_families:
        _set_if_missing(layout, "overflow_y", "hidden")

    family_classes: dict[str, tuple[str, ...]] = {
        "text": ("gu-control-text",),
        "numeric": ("gu-control-numeric",),
        "dropdown": ("gu-control-dropdown",),
        "multiselect": ("gu-control-multiselect", "gu-control-targets"),
        "targets": ("gu-control-multiselect", "gu-control-targets"),
        "checkbox": ("gu-control-checkbox",),
        "boolean": ("gu-control-checkbox",),
        "math": ("gu-control-math",),
        "readonly": ("gu-readonly-value",),
        "color": ("gu-control-color",),
    }
    add_widget_classes(
        widget,
        "gu-control",
        f"gu-control-{family}",
        *family_classes.get(family, ()),
        *tuple(extra_classes),
    )
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
    """Wrap one field in a labelled section that avoids intrinsic-width overflow."""

    ensure_fill_layout(field)
    if isinstance(title, str):
        label: widgets.Widget = widgets.HTML(
            html.escape(title),
            layout=build_layout(margin="0px", min_width="0"),
        )
        add_widget_classes(label, "gu-form-field-label")
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


def build_boolean_field(
    field: widgets.Widget,
    *,
    flex: str | None = None,
    width: str | None = None,
    max_width: str | None = "100%",
    extra_classes: Iterable[str] = (),
) -> widgets.HBox:
    """Wrap an inline boolean control without reusing text-field composition."""

    if getattr(field, "layout", None) is None:
        field.layout = widgets.Layout()
    _set_if_missing(field.layout, "width", "auto")
    _set_if_missing(field.layout, "min_width", "0")
    wrapper = hbox(
        [field],
        gap="0px",
        justify_content="flex-start",
        align_items="center",
        extra_classes=("gu-boolean-field", *tuple(extra_classes)),
    )
    if flex is not None:
        wrapper.layout.flex = flex
    if width is not None:
        wrapper.layout.width = width
    if max_width is not None:
        wrapper.layout.max_width = max_width
    return wrapper


def build_inline_alert(
    *,
    display: str = "none",
    extra_classes: Iterable[str] = (),
) -> widgets.HTML:
    """Create a shared inline alert widget for routine validation feedback."""

    alert = widgets.HTML(value="", layout=full_width_layout(display=display))
    add_widget_classes(alert, "gu-inline-alert", *tuple(extra_classes))
    return alert


def build_action_bar(
    children: Iterable[widgets.Widget],
    *,
    justify_content: str = "flex-end",
    extra_classes: Iterable[str] = (),
) -> widgets.HBox:
    """Create a footer action bar that wraps cleanly on narrow widths."""

    return hbox(
        list(children),
        justify_content=justify_content,
        align_items="center",
        gap="8px",
        flex_flow="row wrap",
        extra_classes=("gu-action-bar", *tuple(extra_classes)),
    )


def build_tab_bar(
    children: Iterable[widgets.Widget],
    *,
    extra_classes: Iterable[str] = (),
) -> widgets.HBox:
    """Create a non-wrapping shared tab bar."""

    return hbox(
        list(children),
        justify_content="flex-start",
        align_items="stretch",
        gap="4px",
        flex_flow="row nowrap",
        extra_classes=("gu-tab-bar", *tuple(extra_classes)),
    )


def build_title_chip(text: str = "", *, display: str = "none") -> widgets.HTML:
    """Return a compact chip used for edit-mode or subject context."""

    chip = widgets.HTML(html.escape(text), layout=build_layout(display=display, min_width="0"))
    add_widget_classes(chip, "gu-title-chip")
    return chip


def build_readonly_value(value: str = "", *, display: str = "block") -> widgets.HTML:
    """Return a readonly value surface styled like the shared control family."""

    widget = widgets.HTML(html.escape(value), layout=full_width_layout(display=display))
    add_widget_classes(widget, "gu-readonly-value")
    return widget


def build_dialog_header(
    title_widget: widgets.Widget,
    close_button: widgets.Widget,
    *,
    chip_widget: widgets.Widget | None = None,
    subtitle_widget: widgets.Widget | None = None,
    extra_classes: Iterable[str] = (),
) -> widgets.HBox:
    """Create the standard dialog header with optional chip/subtitle rows."""

    title_row_children = [title_widget]
    if chip_widget is not None:
        title_row_children.append(chip_widget)
    title_row = hbox(
        title_row_children,
        gap="8px",
        align_items="center",
        extra_classes=("gu-modal-title-row",),
    )
    copy_children = [title_row]
    if subtitle_widget is not None:
        copy_children.append(subtitle_widget)
    copy = vbox(copy_children, gap="6px", extra_classes=("gu-modal-header-copy",))
    return hbox(
        [copy, close_button],
        justify_content="space-between",
        align_items="flex-start",
        gap="12px",
        extra_classes=("gu-modal-header", *tuple(extra_classes)),
    )


def build_form_section(
    title: str,
    children: Iterable[widgets.Widget],
    *,
    gap: str = "10px",
    extra_classes: Iterable[str] = (),
) -> widgets.VBox:
    """Create a titled form section used within dialogs and side panels."""

    header = widgets.HTML(html.escape(title), layout=build_layout(margin="0px", min_width="0"))
    add_widget_classes(header, "gu-form-section-header")
    return vbox([header, *list(children)], gap=gap, extra_classes=("gu-form-section", *tuple(extra_classes)))


def build_section_panel(
    title_text: str,
    *,
    body: widgets.VBox | None = None,
    variant: PanelVariant = "card",
    display: str = "none",
    body_display: str = "flex",
    extra_classes: Iterable[str] = (),
    body_extra_classes: Iterable[str] = (),
) -> SectionPanel:
    """Create a shared panel surface with header, toolbar host, and body."""

    title_display = "none" if variant == "toolbar" else "block"
    title = widgets.HTML(
        html.escape(title_text),
        layout=build_layout(margin="0px", min_width="0", display=title_display),
    )
    add_widget_classes(title, "gu-panel-title", f"gu-panel-title-variant-{variant}")

    toolbar = widgets.HBox(
        [],
        layout=build_layout(
            width="auto",
            min_width="0",
            align_items="center",
            justify_content="flex-end",
            gap="4px",
            overflow_x="hidden",
            overflow_y="visible",
        ),
    )
    add_widget_classes(toolbar, "gu-panel-toolbar")

    header = widgets.HBox(
        [title, toolbar],
        layout=build_layout(
            width="100%",
            min_width="0",
            align_items="center",
            justify_content="space-between",
            gap="8px",
            overflow_x="hidden",
            overflow_y="visible",
        ),
    )
    add_widget_classes(header, "gu-panel-header", f"gu-panel-header-variant-{variant}")

    if body is None:
        body = widgets.VBox(
            [],
            layout=build_layout(
                width="100%",
                min_width="0",
                max_width="100%",
                display=body_display,
                gap="8px",
                overflow_x="hidden",
                overflow_y="visible",
            ),
        )
    else:
        ensure_fill_layout(body)
        body.layout.display = body_display
        if not getattr(body.layout, "overflow_x", None):
            body.layout.overflow_x = "hidden"
        if not getattr(body.layout, "overflow_y", None):
            body.layout.overflow_y = "visible"
    add_widget_classes(body, "gu-panel-body", f"gu-panel-body-variant-{variant}", *tuple(body_extra_classes))

    panel = widgets.VBox(
        [header, body],
        layout=build_layout(
            width="100%",
            min_width="0",
            max_width="100%",
            display=display,
            overflow_x="hidden",
            overflow_y="visible",
        ),
    )
    add_widget_classes(panel, "gu-panel", f"gu-panel-variant-{variant}", *tuple(extra_classes))
    return SectionPanel(panel=panel, header=header, title=title, toolbar=toolbar, body=body)


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
    add_widget_classes(
        button,
        "gu-icon-button",
        "smart-slider-icon-button",
        "gu-inline-icon-button",
        *tuple(extra_classes),
    )
    role_classes = {
        "animate": ("smart-slider-animate-button",),
        "reset": ("smart-slider-reset-button",),
        "settings": ("smart-slider-settings-button",),
        "close": ("smart-slider-close-button", "gu-icon-close-button"),
        "plus": ("gu-icon-plus-button",),
        "edit": ("gu-icon-edit-button",),
    }
    for class_name in role_classes.get(role, ()):  # pragma: no branch
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
    if getattr(button.layout, "width", None) in (None, ""):
        button.layout.width = "auto"
    button.layout.min_width = f"{int(min_width_px)}px"
    add_widget_classes(button, "gu-action-button", f"gu-action-button-{variant}", *tuple(extra_classes))
    return button


def set_tab_button_selected(button: widgets.Button, selected: bool) -> None:
    """Toggle the CSS class used by shared tab buttons."""

    set_widget_class_state(button, "mod-selected", bool(selected))


def build_modal_panel(
    children: Iterable[widgets.Widget],
    *,
    width: str,
    min_width: str,
    max_width: str = "calc(100vw - 32px)",
    padding: str = "16px",
    gap: str = "12px",
    display: str = "none",
    extra_classes: Iterable[str] = (),
) -> widgets.VBox:
    """Create a shared modal panel with consistent overflow protection."""

    panel = widgets.VBox(
        list(children),
        layout=build_layout(
            width=width,
            min_width=min_width,
            max_width=max_width,
            display=display,
            padding=padding,
            gap=gap,
            background_color="white",
            opacity="1",
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
    """Create a shared modal overlay."""

    overlay = widgets.Box(
        [panel],
        layout=build_layout(
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


__all__ = [
    "ButtonVariant",
    "IconButtonRole",
    "PanelVariant",
    "SectionPanel",
    "add_widget_classes",
    "attach_host_children",
    "build_action_bar",
    "build_boolean_field",
    "build_dialog_header",
    "build_form_section",
    "build_inline_alert",
    "build_modal_overlay",
    "build_modal_panel",
    "build_readonly_value",
    "build_section_panel",
    "build_tab_bar",
    "build_title_chip",
    "configure_action_button",
    "configure_control",
    "configure_icon_button",
    "ensure_fill_layout",
    "full_width_layout",
    "hbox",
    "hosted_modal_dimensions",
    "labelled_field",
    "load_ui_css",
    "responsive_row",
    "set_tab_button_selected",
    "set_widget_class_state",
    "shared_style_widget",
    "shared_theme_css",
    "style_widget_value",
    "vbox",
]
