"""
Minimal verification script for module-level params/parameter helpers.

Run (from the repo root):

    python tests/test_Figure_module_params.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import sympy as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from gu_toolkit import Figure, params, parameter, plot_style_options  # noqa: E402
import gu_toolkit.debouncing as debouncing_module  # noqa: E402


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


def _assert_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as exc:  # pragma: no cover - defensive
        raise AssertionError(f"Expected {exc_type}, got {type(exc)}") from exc
    raise AssertionError(f"Expected {exc_type} to be raised.")


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
        _assert_raises(KeyError, lambda: params[a])


def test_parameter_creation_path() -> None:
    a = sp.symbols("a")
    fig = Figure()
    with fig:
        param_ref = parameter(a)
        assert params[a] is param_ref


def test_no_context_behavior() -> None:
    a = sp.symbols("a")
    _assert_raises(RuntimeError, lambda: params[a])
    _assert_raises(RuntimeError, parameter, a)


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

    _assert_raises(ValueError, setattr, plot, "opacity", 1.2)






def test_plot_cached_samples_none_before_first_render() -> None:
    x = sp.symbols("x")
    fig = Figure()
    plot = fig.plot(x, sp.sin(x), id="sin_hidden", visible=False)

    assert plot.x_data is None
    assert plot.y_data is None

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

    _assert_raises(ValueError, x_data.__setitem__, 0, 999.0)
    _assert_raises(ValueError, y_data.__setitem__, 0, 999.0)


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


def main() -> None:
    tests = [
        test_params_proxy_context_access,
        test_params_strict_lookup,
        test_parameter_creation_path,
        test_no_context_behavior,
        test_params_setitem_sugar,
        test_plot_opacity_shortcut_and_validation,
        test_plot_cached_samples_none_before_first_render,
        test_plot_render_caches_read_only_samples,
        test_plot_render_replaces_cached_samples,
        test_plot_figure_property_exposes_owner_and_context_manager,
        test_plot_style_options_are_discoverable,
        test_relayout_debounce_delays_first_event_until_timer,
        test_relayout_debounce_drop_overflow_keeps_final_event,
    ]
    for test in tests:
        test()
    print(f"OK: {len(tests)} tests passed")


if __name__ == "__main__":
    main()
