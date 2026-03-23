from __future__ import annotations

import numpy as np
import pytest
import sympy as sp

import gu_toolkit.figure_plot as figure_plot_module
import gu_toolkit.figure_render_scheduler as scheduler_module
from gu_toolkit import Figure


class _ManualDebouncer:
    """Deterministic render debouncer used by figure integration tests."""

    def __init__(self, callback, *, execute_every_ms: int, drop_overflow: bool = True, **kwargs):
        del execute_every_ms, drop_overflow, kwargs
        self._callback = callback
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        del args, kwargs
        self.call_count += 1

    def fire(self) -> None:
        self._callback()


@pytest.fixture
def manual_render_debouncer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler_module, "QueuedDebouncer", _ManualDebouncer)


def test_multiple_param_changes_coalesce_to_one_render_and_latest_hook(
    manual_render_debouncer: None,
) -> None:
    x, a = sp.symbols("x a")
    fig = Figure(sampling_points=12)
    ref = fig.parameter(a, value=1.0)
    plot = fig.plot(a * x, x, id="line")

    render_calls = 0
    hook_events: list[float] = []
    original_render = plot.render

    def _counted_render(*args, **kwargs):
        nonlocal render_calls
        render_calls += 1
        return original_render(*args, **kwargs)

    plot.render = _counted_render  # type: ignore[method-assign]
    fig.add_param_change_hook(lambda event: hook_events.append(float(event.new)), run_now=False)

    ref.value = 2.0
    ref.value = 3.0
    ref.value = 4.0

    assert render_calls == 0
    fig.flush_render_queue()

    assert render_calls == 1
    assert hook_events == [4.0]
    assert np.allclose(plot.y_data, plot.x_data * 4.0)


def test_numeric_expression_bindings_keep_stable_identity_across_renders(
    manual_render_debouncer: None,
) -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    ref = fig.parameter(a, value=1.0)
    plot = fig.plot(a * x, x, id="ax")

    live_1 = plot.numeric_expression
    live_2 = plot.numeric_expression
    render_bound_1 = plot._render_numeric_expression

    assert live_1 is live_2

    ref.value = 3.0
    fig.flush_render_queue()

    assert plot.numeric_expression is live_1
    assert plot._render_numeric_expression is render_bound_1
    assert np.allclose(np.asarray(plot.numeric_expression(np.array([1.0, 2.0]))), np.array([3.0, 6.0]))


def test_render_parameter_context_is_a_stable_snapshot_provider(
    manual_render_debouncer: None,
) -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    ref = fig.parameter(a, value=1.0)
    fig.plot(a * x, x, id="ax")
    fig.render(force=True)

    snapshot_provider = fig.parameters.render_parameter_context
    assert fig.parameters.render_parameter_context is snapshot_provider
    assert snapshot_provider["a"] == pytest.approx(1.0)
    assert snapshot_provider[a] == pytest.approx(1.0)

    ref.value = 2.5

    assert fig.parameters.parameter_context["a"] == pytest.approx(2.5)
    assert fig.parameters.parameter_context[a] == pytest.approx(2.5)
    assert snapshot_provider[a] == pytest.approx(1.0)

    fig.flush_render_queue()

    assert fig.parameters.render_parameter_context is snapshot_provider
    assert snapshot_provider["a"] == pytest.approx(2.5)
    assert snapshot_provider[a] == pytest.approx(2.5)


def test_render_reuses_compiled_numeric_function_without_recompiling(
    manual_render_debouncer: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    x, a = sp.symbols("x a")
    fig = Figure(sampling_points=10)
    ref = fig.parameter(a, value=1.0)
    plot = fig.plot(a * x, x, id="line")

    def _boom(*args, **kwargs):
        raise AssertionError("numpify_cached should not be called during render")

    monkeypatch.setattr(figure_plot_module, "numpify_cached", _boom)

    ref.value = 2.0
    fig.flush_render_queue()
    fig.render(reason="manual", force=True)

    assert np.allclose(plot.y_data, plot.x_data * 2.0)
