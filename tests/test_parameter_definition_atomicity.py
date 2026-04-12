from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
import sympy as sp

from gu_toolkit import Figure, FloatSlider, parameter
from gu_toolkit.figure_parameters import ParameterManager


class _RecordingParameterLayout:
    def __init__(self) -> None:
        self.controls: list[object] = []

    def _mount_parameter_control(self, control: object) -> None:
        self.controls.append(control)


def test_existing_parameter_redefinition_applies_final_explicit_value() -> None:
    fig = Figure()
    a = sp.Symbol("a")

    fig.parameter(a)
    ref = fig.parameter(a, value=10.0, min=1.0, max=100.0)

    assert ref.value == pytest.approx(10.0)
    assert ref.widget.value == pytest.approx(10.0)
    assert ref.min == pytest.approx(1.0)
    assert ref.max == pytest.approx(100.0)


def test_plot_autocreated_parameters_reconfigure_without_intermediate_value_events() -> None:
    x, a, b = sp.symbols("x a b")
    fig = Figure(x_range=(0.0, 1 / 220), y_range=(-2.5, 2.5), samples=1200)

    fig.plot(a * sp.sin(2 * sp.pi * b * x), x, label=r"$a\sin(2 \pi b x)$")

    events: list[tuple[Any, Any]] = []
    fig.parameters[a].observe(lambda ev: events.append((ev.old, ev.new)))

    ref_a = fig.parameter(a, value=2.0, min=0.2, max=2.0, step=0.1)
    ref_b = fig.parameter(b, value=220.0, min=50.0, max=440.0, step=0.1)

    assert ref_a.value == pytest.approx(2.0)
    assert ref_a.widget.value == pytest.approx(2.0)
    assert ref_a.min == pytest.approx(0.2)
    assert ref_a.max == pytest.approx(2.0)
    assert ref_a.step == pytest.approx(0.1)

    assert ref_b.value == pytest.approx(220.0)
    assert ref_b.widget.value == pytest.approx(220.0)
    assert ref_b.min == pytest.approx(50.0)
    assert ref_b.max == pytest.approx(440.0)
    assert ref_b.step == pytest.approx(0.1)

    assert len(events) == 1
    assert events[0][0] == pytest.approx(0.0)
    assert events[0][1] == pytest.approx(2.0)


def test_parameter_manager_reconfigures_custom_floatslider_atomically() -> None:
    a = sp.Symbol("a")
    layout = _RecordingParameterLayout()
    manager = ParameterManager(lambda *_: None, layout_manager=layout)

    ref = manager.parameter(
        a,
        control=FloatSlider(),
        value=10.0,
        min=1.0,
        max=100.0,
        step=0.1,
    )

    assert layout.controls == [ref.widget]
    assert ref.value == pytest.approx(10.0)
    assert ref.widget.value == pytest.approx(10.0)
    assert ref.min == pytest.approx(1.0)
    assert ref.max == pytest.approx(100.0)
    assert ref.step == pytest.approx(0.1)


def test_direct_floatslider_parameter_reconfigure_coalesces_value_events() -> None:
    slider = FloatSlider(value=0.0, min=-1.0, max=1.0, step=0.01)
    events: list[tuple[float, float]] = []

    slider.observe(
        lambda change: events.append((float(change["old"]), float(change["new"]))),
        names="value",
    )

    slider._apply_parameter_kwargs(
        {"value": 2.0, "min": 0.2, "max": 2.0, "step": 0.1}
    )

    assert slider.value == pytest.approx(2.0)
    assert slider.min == pytest.approx(0.2)
    assert slider.max == pytest.approx(2.0)
    assert slider.step == pytest.approx(0.1)
    assert events == [(0.0, 2.0)]


def test_module_parameter_routes_through_figure_parameter() -> None:
    a = sp.Symbol("a")
    fig = Figure()
    sentinel = object()

    with patch.object(Figure, "parameter", autospec=True, return_value=sentinel) as mocked:
        with fig:
            result = parameter(a, value=1.0, min=0.2)

    assert result is sentinel
    mocked.assert_called_once_with(fig, a, control=None, value=1.0, min=0.2)
