"""
Minimal verification script for module-level params/parameter helpers.

Run (from the repo root):

    python tests/test_Figure_module_params.py
"""

from __future__ import annotations

import sympy as sp
import pytest

from gu_toolkit import Figure, params, parameter, plot_style_options
import gu_toolkit.debouncing as debouncing_module


class _FakeTimer:
    created: list["_FakeTimer"] = []

    def __init__(self, delay: float, callback):
        self.delay = delay
        self.callback = callback
        self.started = False
        self.canceled = False
        self.daemon = False
        _FakeTimer.created.append(self)

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.canceled = True



def test_params_proxy_context_access() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    with fig:
        param_ref = fig.params.parameter(a)
        assert params[a] is param_ref


def test_params_strict_lookup() -> None:
    a = sp.symbols("a")
    fig = Figure()
    with fig:
        assert a not in params
        with pytest.raises(KeyError):
            _ = params[a]


def test_parameter_creation_path() -> None:
    a = sp.symbols("a")
    fig = Figure()
    with fig:
        param_ref = parameter(a)
        assert params[a] is param_ref


def test_no_context_behavior() -> None:
    a = sp.symbols("a")
    with pytest.raises(RuntimeError):
        _ = params[a]
    with pytest.raises(RuntimeError):
        parameter(a)


def test_params_setitem_sugar() -> None:
    a = sp.symbols("a")
    fig = Figure()
    with fig:
        fig.params.parameter(a, value=1)
        params[a] = 7
        assert params[a].value == 7



def test_plot_opacity_shortcut_and_validation() -> None:
    x = sp.symbols("x")
    fig = Figure()
    plot = fig.plot(x, sp.sin(x), id="sin", opacity=0.4)
    assert plot.opacity == 0.4

    plot.update(opacity=0.7)
    assert plot.opacity == 0.7

    with pytest.raises(ValueError):
        setattr(plot, "opacity", 1.2)






def test_plot_cached_samples_none_before_first_render() -> None:
    x = sp.symbols("x")
    fig = Figure()
    plot = fig.plot(x, sp.sin(x), id="sin_hidden", visible=False)

    assert plot.x_data is None
    assert plot.y_data is None

def test_plot_update_accepts_visible_kwarg() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.plot(x, sp.sin(x), id="sin")

    updated = fig.plot(x, sp.sin(x), id="sin", visible=False)

    assert updated.visible is False
    assert updated.x_data is not None


def test_plot_render_caches_read_only_samples() -> None:
    x = sp.symbols("x")
    fig = Figure()
    plot = fig.plot(x, sp.sin(x), id="sin")

    x_data = plot.x_data
    y_data = plot.y_data
    assert x_data is not None
    assert y_data is not None

    assert not x_data.flags.writeable
    assert not y_data.flags.writeable

    with pytest.raises(ValueError):
        x_data[0] = 999.0
    with pytest.raises(ValueError):
        y_data[0] = 999.0


def test_plot_render_replaces_cached_samples() -> None:
    x = sp.symbols("x")
    fig = Figure()
    plot = fig.plot(x, sp.sin(x), id="sin")

    first_x = plot.x_data
    first_y = plot.y_data
    assert first_x is not None
    assert first_y is not None

    plot.sampling_points = 25

    second_x = plot.x_data
    second_y = plot.y_data
    assert second_x is not None
    assert second_y is not None

    assert len(second_x) == 25
    assert len(second_y) == 25
    assert len(first_x) != len(second_x)



def test_plot_figure_property_exposes_owner_and_context_manager() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    plot = fig.plot(x, sp.sin(x), id="sin")

    assert plot.figure is fig

    with plot.figure:
        param_ref = parameter(a)
        assert params[a] is param_ref

def test_plot_style_options_are_discoverable() -> None:
    options = plot_style_options()
    for key in ("color", "thickness", "dash", "opacity", "line", "trace"):
        assert key in options

    fig_options = Figure.plot_style_options()
    assert fig_options == options


def test_plot_accepts_label_kwarg_on_create() -> None:
    x = sp.symbols("x")
    fig = Figure()
    plot = fig.plot(x, sp.sin(x), id="sin", label="Sine")

    assert plot.label == "Sine"
    assert fig.figure_widget.data[0].name == "Sine"


def test_plot_accepts_label_kwarg_on_update() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.plot(x, sp.sin(x), id="sin", label="Sine")
    updated = fig.plot(x, sp.cos(x), id="sin", label="Cosine")

    assert updated.label == "Cosine"
    assert fig.figure_widget.data[0].name == "Cosine"


def test_relayout_debounce_delays_first_event_until_timer() -> None:
    original_timer = debouncing_module.threading.Timer
    original_render = Figure.render
    calls = []

    def _render_spy(self, reason="manual", trigger=None):
        calls.append(reason)

    try:
        _FakeTimer.created.clear()
        debouncing_module.threading.Timer = _FakeTimer
        Figure.render = _render_spy

        fig = Figure()
        calls.clear()
        fig._throttled_relayout()

        assert calls == []
        assert len(_FakeTimer.created) == 1
        assert _FakeTimer.created[0].started

        _FakeTimer.created[0].callback()

        assert calls == ["relayout"]
    finally:
        debouncing_module.threading.Timer = original_timer
        Figure.render = original_render


def test_relayout_debounce_drop_overflow_keeps_final_event() -> None:
    original_timer = debouncing_module.threading.Timer
    original_render = Figure.render
    calls = []

    def _render_spy(self, reason="manual", trigger=None):
        calls.append(reason)

    try:
        _FakeTimer.created.clear()
        debouncing_module.threading.Timer = _FakeTimer
        Figure.render = _render_spy

        fig = Figure()
        calls.clear()
        fig._throttled_relayout()
        fig._throttled_relayout()
        fig._throttled_relayout()

        assert calls == []
        assert len(_FakeTimer.created) == 1

        # First tick should collapse the queue to the last event and render once.
        _FakeTimer.created[0].callback()
        assert calls == ["relayout"]
        assert len(_FakeTimer.created) == 1
    finally:
        debouncing_module.threading.Timer = original_timer
        Figure.render = original_render



def test_viewport_range_controls_read_widget_state() -> None:
    fig = Figure(x_range=(-4, 4), y_range=(-3, 3))

    fig.figure_widget.update_xaxes(range=(-2, 2))
    fig.figure_widget.update_yaxes(range=(-1, 1))

    assert fig._viewport_x_range == (-2.0, 2.0)
    assert fig._viewport_y_range == (-1.0, 1.0)
    assert fig.current_x_range == (-2.0, 2.0)
    assert fig.current_y_range == (-1.0, 1.0)


def test_viewport_range_controls_move_view_without_changing_defaults() -> None:
    fig = Figure(x_range=(-6, 6), y_range=(-5, 5))

    fig._viewport_x_range = (-3, 1)
    fig._viewport_y_range = (-2, 2)

    assert fig.x_range == (-6.0, 6.0)
    assert fig.y_range == (-5.0, 5.0)
    assert fig.current_x_range == (-3.0, 1.0)
    assert fig.current_y_range == (-2.0, 2.0)


def test_viewport_range_controls_support_reset_to_defaults() -> None:
    fig = Figure(x_range=(-7, 7), y_range=(-4, 4))

    fig._viewport_x_range = (-2, 2)
    fig._viewport_y_range = (-1, 1)

    fig._viewport_x_range = None
    fig._viewport_y_range = None

    assert fig.current_x_range == (-7.0, 7.0)
    assert fig.current_y_range == (-4.0, 4.0)
