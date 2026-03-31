from __future__ import annotations

import importlib
import warnings

import plotly.graph_objects as go
import pytest
import sympy as sp

from gu_toolkit.Figure import Figure
from gu_toolkit.runtime_support import PlotlyWidgetSupportStatus


figure_module = importlib.import_module("gu_toolkit.Figure")


def _build_figure_with_wave() -> tuple[Figure, object]:
    x, t = sp.symbols("x t")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        fig = Figure()
    fig.parameter(t, min=0.0, max=1.0, value=0.0, step=0.1)
    plot = fig.plot(sp.sin(x + t), x, id="wave")
    return fig, plot


def test_figure_reports_degraded_plotly_widget_runtime(monkeypatch) -> None:
    status = PlotlyWidgetSupportStatus(
        anywidget_available=False,
        anywidget_is_fallback=True,
        figurewidget_supported=False,
        anywidget_mode="fallback_stub",
        figurewidget_mode="plotly_figure_fallback",
        reason="missing anywidget for test",
    )

    monkeypatch.setattr(
        figure_module,
        "create_plotly_figure_widget",
        lambda: (go.Figure(), status),
    )

    def _warn_once(_key: str, message: str, *, category=RuntimeWarning, stacklevel: int = 2) -> None:
        warnings.warn(message, category=category, stacklevel=stacklevel)

    monkeypatch.setattr(figure_module, "warn_once", _warn_once)

    with pytest.warns(RuntimeWarning, match="anywidget"):
        fig = Figure()

    diagnostics = fig.runtime_diagnostics()
    assert diagnostics["plotly_widget_support"]["figurewidget_supported"] is False
    assert diagnostics["figure"]["current_widget_type"] == "Figure"
    assert "widget_support" in fig.performance_report(recent_event_limit=1)


def test_plot_reuses_x_samples_when_range_is_unchanged() -> None:
    _fig, plot = _build_figure_with_wave()

    before = plot.performance_snapshot()["counters"].copy()
    plot.render()
    after = plot.performance_snapshot()

    assert after["counters"].get("x_reuse_hits", 0) == before.get("x_reuse_hits", 0) + 1
    assert after["state"]["last_x_reused"] is True


def test_figure_performance_snapshot_includes_runtime_scheduler_and_plot_metrics() -> None:
    fig, plot = _build_figure_with_wave()

    fig.render(force=True)
    snapshot = fig.performance_snapshot(recent_event_limit=2)

    assert "runtime" in snapshot
    assert "figure" in snapshot
    assert "render_scheduler" in snapshot
    assert "relayout_debouncer" in snapshot
    assert snapshot["plots"][plot.id]["counters"]["renders"] >= 1
    assert snapshot["runtime"]["figure"]["current_widget_type"] in {"Figure", "FigureWidget"}


def test_figure_performance_snapshot_includes_parameter_runtime_support_and_animation_clock() -> None:
    x, t = sp.symbols("x t")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        fig = Figure()
    fig.parameter(t, min=0.0, max=1.0, value=0.0, step=0.1)
    plot = fig.plot(sp.sin(x + t), x, id="wave")

    fig.render(force=True)
    snapshot = fig.performance_snapshot(recent_event_limit=2)

    assert "runtime_support" in snapshot
    assert "parameters" in snapshot
    assert "animation_clock" in snapshot
    assert snapshot["parameters"]["controls"]["t"]["widget_type"] == "FloatSlider"
    assert snapshot["plots"][plot.id]["counters"]["renders"] >= 1

    report = fig.performance_report(recent_event_limit=2)
    assert "Parameter manager" in report
    assert "Animation clock" in report
    assert "Runtime support scheduler" in report
