from __future__ import annotations

import importlib
from dataclasses import dataclass

import ipywidgets as widgets
import plotly.graph_objects as go
import pytest
import sympy as sp

from gu_toolkit.figure_color import color_for_trace_index, color_to_picker_hex, resolve_colorway
from gu_toolkit.figure_legend import LegendPanelManager
from gu_toolkit.figure_plot import Plot


@dataclass
class _FakePlotWithTrace:
    id: str
    trace: go.Scatter

    label: str = "auto"
    visible: bool = True
    views: tuple[str, ...] = ("main",)
    color: str | None = None

    def _reference_trace_handle(self) -> go.Scatter:
        return self.trace


class _FakeView:
    def __init__(self) -> None:
        self.figure_widget = go.Figure()
        self.figure_widget.update_layout(template="plotly_white")
        self.is_stale = False
        self.x_range = (-4.0, 4.0)
        self.current_x_range = self.x_range
        self.figure_widget.update_xaxes(range=self.x_range)
        self.figure_widget.update_yaxes(range=(-3.0, 3.0))


class _FakeViews(dict[str, _FakeView]):
    def __init__(self) -> None:
        super().__init__()
        self.current_id = "main"
        self["main"] = _FakeView()


class _FakeParameterManager:
    parameter_context: dict[object, object] = {}


class _FakeFigure:
    def __init__(self) -> None:
        self.views = _FakeViews()
        self.parameters = _FakeParameterManager()
        self.samples = 500
        self.x_range = (-4.0, 4.0)
        self.current_x_range = None


class _DummyPane:
    def __init__(self, figw: go.Figure, *args, **kwargs) -> None:
        self.widget = figw
        self.debug_pane_id = "dummy-pane"

    def bind_layout_debug(self, *args, **kwargs) -> None:
        return None

    def reflow(self, *args, **kwargs):
        return None

    def request_reflow(self, *args, **kwargs):
        return None

    def debug_snapshot(self) -> dict[str, object]:
        return {}


@pytest.fixture
def patched_figure_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    figure_module = importlib.import_module("gu_toolkit.Figure")
    monkeypatch.setattr(go, "FigureWidget", go.Figure)
    monkeypatch.setattr(figure_module, "PlotlyPane", _DummyPane)


def test_resolve_colorway_prefers_template_colorway() -> None:
    fig = go.Figure()
    fig.update_layout(template="plotly_white")

    palette = resolve_colorway(fig)

    assert palette[:3] == ("#636efa", "#EF553B", "#00cc96")
    assert color_for_trace_index(fig, 0) == "#636efa"
    assert color_for_trace_index(fig, 1) == "#EF553B"


def test_color_to_picker_hex_normalizes_common_plot_color_formats() -> None:
    assert color_to_picker_hex("#abc") == "#aabbcc"
    assert color_to_picker_hex("#123456") == "#123456"
    assert color_to_picker_hex("rgb(31, 119, 180)") == "#1f77b4"
    assert color_to_picker_hex("rgba(31, 119, 180, 0.4)") == "#1f77b4"


def test_legend_uses_template_colorway_when_trace_color_unspecified() -> None:
    fig = go.Figure()
    fig.update_layout(template="plotly_white")
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="first")
    fig.add_scatter(x=[0, 1], y=[1, 2], mode="lines", name="second")

    manager = LegendPanelManager(widgets.VBox())
    manager.set_active_view("main")
    manager.on_plot_added(_FakePlotWithTrace(id="p1", trace=fig.data[0]))
    manager.on_plot_added(_FakePlotWithTrace(id="p2", trace=fig.data[1]))

    assert manager._rows["p1"].toggle.style.text_color == "#636efa"
    assert manager._rows["p2"].toggle.style.text_color == "#EF553B"


def test_add_to_view_clones_existing_trace_style() -> None:
    x = sp.symbols("x")
    fig = _FakeFigure()

    plot = Plot(
        x,
        sp.sin(x),
        fig,
        plot_id="p1",
        label="p1",
        color="#123456",
        thickness=4,
        dash="dash",
        opacity=0.4,
    )

    fig.views["alt"] = _FakeView()
    plot.add_to_view("alt")
    alt_trace = plot._handles["alt"].trace_handle

    assert alt_trace is not None
    assert alt_trace.line.color == "#123456"
    assert alt_trace.line.width == 4
    assert alt_trace.line.dash == "dash"
    assert alt_trace.opacity == 0.4


def test_figure_assigns_explicit_stable_colors_to_hidden_and_visible_plots(
    patched_figure_runtime: None,
) -> None:
    from gu_toolkit import Figure

    x = sp.symbols("x")
    fig = Figure()

    hidden = fig.plot(sp.sin(x), x, id="hidden", visible=False)
    shown = fig.plot(sp.cos(x), x, id="shown")

    assert hidden._reference_trace_handle().line.color == "#636efa"
    assert shown._reference_trace_handle().line.color == "#EF553B"
    assert hidden.color == "#636efa"
    assert shown.color == "#EF553B"
    assert fig._legend._rows["hidden"].toggle.style.text_color == "#636efa"
    assert fig._legend._rows["shown"].toggle.style.text_color == "#EF553B"

    hidden.visible = True

    assert hidden._reference_trace_handle().line.color == "#636efa"
    assert fig._legend._rows["hidden"].toggle.style.text_color == "#636efa"
