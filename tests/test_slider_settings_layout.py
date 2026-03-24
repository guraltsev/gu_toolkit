from __future__ import annotations

from gu_toolkit.Slider import FloatSlider


def test_slider_settings_dialog_uses_parameter_wording_and_wider_layout() -> None:
    slider = FloatSlider(description="x")

    assert "Parameter settings" in slider.settings_title.children[0].value
    assert slider.settings_panel.layout.width == "440px"
    assert slider.settings_panel.layout.min_width == "380px"
    assert slider.set_step.layout.width == "100%"
    assert slider.set_live.layout.width == "100%"
    assert slider.btn_settings.description == "Open parameter settings"
    assert slider.btn_close_settings.description == "Close parameter settings"


def test_slider_settings_css_exposes_wider_panel_constraints() -> None:
    slider = FloatSlider(description="x")
    css = slider._limit_style.value

    assert "width: min(440px, calc(100vw - 32px))" in css
    assert "min-width: min(380px, calc(100vw - 32px))" in css
    assert ".smart-slider-settings-modal > *" in css
    assert "background: rgba(15, 23, 42, 0.12)" in css


def test_slider_settings_toggle_updates_parameter_settings_copy() -> None:
    slider = FloatSlider(description="x")

    slider._toggle_settings(None)
    assert slider.btn_settings.description == "Close parameter settings"
    assert slider.btn_settings.tooltip == "Close parameter settings"
    assert slider._settings_accessibility.dialog_open is True

    slider._toggle_settings(None)
    assert slider.btn_settings.description == "Open parameter settings"
    assert slider.btn_settings.tooltip == "Open parameter settings"
    assert slider._settings_accessibility.dialog_open is False


def test_slider_escape_close_request_updates_dialog_state() -> None:
    slider = FloatSlider(description="x")

    slider.open_settings()
    assert slider._settings_open is True

    slider._settings_accessibility._emit_msg(
        {"type": "dialog_request", "action": "close", "reason": "escape"}
    )

    assert slider._settings_open is False
    assert slider.settings_modal.layout.display == "none"
    assert slider.btn_settings.description == "Open parameter settings"
