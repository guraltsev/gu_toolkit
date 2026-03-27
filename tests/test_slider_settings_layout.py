from __future__ import annotations

from gu_toolkit.Slider import FloatSlider


def test_slider_settings_dialog_uses_parameter_wording_and_shared_shell_layout() -> None:
    slider = FloatSlider(description="x")

    assert slider.settings_title_text.value == "Parameter settings"
    assert "<b>" not in slider.settings_title_text.value.lower()
    assert slider.settings_panel.layout.width == "min(460px, calc(100vw - 32px))"
    assert slider.settings_panel.layout.min_width == "min(320px, calc(100vw - 32px))"
    assert slider.settings_panel.layout.max_width == "calc(100vw - 32px)"
    assert slider.set_step.layout.width == "100%"
    assert slider.set_live.layout.width == "auto"
    assert slider.set_animation_time.description == ""
    assert slider.set_animation_mode.description == ""
    assert slider._settings_animation_section.children[0].value == "Animation"
    assert slider._settings_animation_row.children == (
        slider._settings_animation_time_field,
        slider._settings_animation_mode_field,
    )
    assert slider.btn_settings.description == "Open parameter settings"
    assert slider.btn_close_settings.description == "Close parameter settings"
    assert slider.btn_done_settings.description == "Done"


def test_slider_settings_title_preserves_math_markup_without_chip_styling() -> None:
    slider = FloatSlider(description=r"$a$:")

    assert slider.settings_subject.value == r"$a$"
    assert slider.settings_subject.layout.display == "block"
    assert "smart-slider-settings-subject" in slider.settings_subject._dom_classes
    assert "gu-title-chip" not in slider.settings_subject._dom_classes


def test_slider_settings_css_avoids_duplicating_generic_modal_chrome() -> None:
    slider = FloatSlider(description="x")
    css = slider._limit_style.value

    assert ".smart-slider-settings-modal > *" not in css
    assert "width: min(440px, calc(100vw - 32px))" not in css
    assert ".smart-slider-top-row" in css
    assert ".smart-slider-settings-subject" in css
    assert "smart-slider-settings-title" not in css


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
