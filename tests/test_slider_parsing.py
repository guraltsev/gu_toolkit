from __future__ import annotations

from gu_toolkit.Slider import FloatSlider


def test_slider_accepts_expression_input() -> None:
    slider = FloatSlider(value=0.0, min=0.0, max=4.0, step=0.1)
    slider.number.value = "pi/2"
    assert abs(slider.value - 1.57079632679) < 1e-6


def test_slider_invalid_text_reverts_to_previous_value() -> None:
    slider = FloatSlider(value=1.25, min=0.0, max=4.0, step=0.1)
    slider.number.value = "not a number"
    assert slider.value == 1.25
    assert slider.number.value == "1.25"
