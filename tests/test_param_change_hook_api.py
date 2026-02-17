from __future__ import annotations

import warnings

import pytest
import sympy as sp

from gu_toolkit import Figure


def _figure_with_parameter() -> tuple[Figure, sp.Symbol]:
    x, a = sp.symbols("x a")
    fig = Figure(x_range=(-6, 6), y_range=(-3, 3))
    fig.parameter(a)
    fig.plot(a * sp.sin(x), x, id="a_sin")
    return fig, a


def test_auto_hook_id_starts_at_one() -> None:
    fig, _ = _figure_with_parameter()

    hook_id = fig.add_param_change_hook(lambda _event: None, run_now=False)

    assert hook_id == "hook:1"


def test_replacing_same_hook_id_overwrites_callback() -> None:
    fig, a = _figure_with_parameter()
    calls: list[str] = []

    def first(_event):
        calls.append("first")

    def second(_event):
        calls.append("second")

    hook_id = fig.add_param_change_hook(first, run_now=False)
    hook_id_2 = fig.add_param_change_hook(second, hook_id=hook_id, run_now=False)

    assert hook_id_2 == hook_id

    fig.parameter(a).value = 2.0
    assert calls == ["second"]


def test_explicit_hook_namespace_id_bumps_auto_counter() -> None:
    fig, _ = _figure_with_parameter()

    explicit = fig.add_param_change_hook(
        lambda _event: None, hook_id="hook:10", run_now=False
    )
    auto = fig.add_param_change_hook(lambda _event: None, run_now=False)

    assert explicit == "hook:10"
    assert auto == "hook:11"


def test_non_string_hashable_hook_id_is_supported() -> None:
    fig, a = _figure_with_parameter()
    calls: list[float] = []
    tuple_id = ("analysis", 1)

    def callback(event):
        calls.append(float(event.new))

    returned = fig.add_param_change_hook(callback, hook_id=tuple_id, run_now=False)

    assert returned == tuple_id
    fig.parameter(a).value = 1.75
    assert calls[-1] == pytest.approx(1.75)


def test_unhashable_hook_id_raises_type_error() -> None:
    fig, _ = _figure_with_parameter()

    with pytest.raises(TypeError):
        fig.add_param_change_hook(lambda _event: None, hook_id=[], run_now=False)


def test_failing_hook_warns_without_blocking_other_hooks() -> None:
    fig, a = _figure_with_parameter()
    ok_calls: list[float] = []

    def ok_hook(event):
        ok_calls.append(float(event.new))

    def failing_hook(_event):
        raise RuntimeError("intentional hook failure")

    fig.add_param_change_hook(ok_hook, hook_id="ok-hook", run_now=False)
    fig.add_param_change_hook(failing_hook, hook_id="fail-hook", run_now=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig.parameter(a).value = 2.5

    assert ok_calls[-1] == pytest.approx(2.5)
    assert any("Hook fail-hook failed" in str(w.message) for w in caught)
