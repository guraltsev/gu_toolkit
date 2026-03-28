from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import sympy as sp

from gu_toolkit import (
    Figure,
    FieldPlotSnapshot,
    contour,
    density,
    field_palette_options,
    field_style_options,
    scalar_field,
    temperature,
)


def test_density_plot_renders_symbolic_heatmap_grid() -> None:
    x, y = sp.symbols("x y")
    fig = Figure(x_range=(-2, 2), y_range=(-3, 3))

    field = fig.density(
        x**2 + y,
        x,
        y,
        id="rho",
        grid=(6, 4),
        colorscale="Viridis",
        show_colorbar=True,
    )

    assert field.render_mode == "heatmap"
    assert field.grid == (6, 4)
    assert field.x_var == x
    assert field.y_var == y
    assert field.z_data is not None
    assert field.z_data.shape == (4, 6)
    assert np.allclose(field.x_data, np.linspace(-2.0, 2.0, 6))
    assert np.allclose(field.y_data, np.linspace(-3.0, 3.0, 4))
    assert isinstance(fig.figure_widget.data[0], go.Heatmap)


def test_contour_plot_updates_from_parameters_after_flush() -> None:
    x, y, a = sp.symbols("x y a")
    fig = Figure(x_range=(-1, 1), y_range=(-2, 2))
    fig.parameter(a, value=1.0)

    field = fig.contour(a * x + y, x, y, id="psi", grid=(5, 7), levels=9)
    before = field.z_data.copy()

    fig.parameters[a].value = 3.0
    assert np.array_equal(field.z_data, before)

    fig.flush_render_queue()

    assert field.parameters == (a,)
    assert field.levels == 9
    expected_x, expected_y = np.meshgrid(field.x_data, field.y_data)
    assert np.allclose(field.z_data, 3.0 * expected_x + expected_y)


def test_contour_plot_supports_exact_level_spacing_and_line_dash_styles() -> None:
    x, y = sp.symbols("x y")
    fig = Figure(x_range=(-1, 1), y_range=(-1, 1))

    field = fig.contour(
        x**2 + y**2,
        x,
        y,
        grid=(10, 10),
        level_step=0.5,
        level_start=0.0,
        level_end=2.0,
        line_dash="dashdot",
        line_color="black",
        line_width=2.0,
    )

    trace = fig.figure_widget.data[0]

    assert isinstance(trace, go.Contour)
    assert field.level_step == 0.5
    assert field.level_start == 0.0
    assert field.level_end == 2.0
    assert field.line_dash == "dashdot"
    assert trace.contours.size == 0.5
    assert trace.contours.start == 0.0
    assert trace.contours.end == 2.0
    assert trace.line.dash == "dashdot"
    assert trace.line.color == "black"
    assert trace.line.width == 2.0


def test_scalar_field_alias_helpers_route_to_current_figure() -> None:
    x, y = sp.symbols("x y")
    fig = Figure()

    with fig:
        f0 = scalar_field(x + y, x, y, id="f0", grid=(3, 3))
        f1 = contour(x - y, x, y, id="f1", grid=(4, 4))
        f2 = density(x * y, x, y, id="f2", grid=(5, 5))
        f3 = temperature(x**2 + y**2, x, y, id="f3", grid=(6, 6))

    assert fig.plots["f0"] is f0
    assert fig.plots["f1"] is f1
    assert fig.plots["f2"] is f2
    assert fig.plots["f3"] is f3
    assert f1.render_mode == "contour"
    assert f2.render_mode == "heatmap"
    assert f3.preset == "temperature"
    assert f3.colorscale == "hot"


def test_scalar_field_replaces_existing_cartesian_plot_with_same_id() -> None:
    x, y = sp.symbols("x y")
    fig = Figure()
    fig.plot(sp.sin(x), x, id="shared")

    replaced = fig.density(x + y, x, y, id="shared", grid=(4, 4))

    assert fig.plots["shared"] is replaced
    assert len(fig.figure_widget.data) == 1
    assert isinstance(fig.figure_widget.data[0], go.Heatmap)


def test_temperature_plot_supports_range_step_alpha_and_out_of_bounds_colors() -> None:
    x, y = sp.symbols("x y")
    fig = Figure(x_range=(-2, 2), y_range=(-1, 1))

    field = fig.temperature(
        3 * x + y,
        x,
        y,
        id="temp-range",
        grid=(5, 5),
        colorscale="thermal",
        z_range=(-1, 1),
        z_step=0.5,
        under_color="black",
        over_color="white",
        alpha=0.35,
    )

    trace = fig.figure_widget.data[0]
    display_z = np.asarray(trace.z, dtype=float)

    assert isinstance(trace, go.Heatmap)
    assert field.z_step == 0.5
    assert field.under_color == "black"
    assert field.over_color == "white"
    assert field.opacity == 0.35
    assert trace.opacity == 0.35
    assert trace.zmin == -1.5
    assert trace.zmax == 1.5
    assert trace.colorbar.tick0 == -1.0
    assert trace.colorbar.dtick == 0.5
    assert np.min(display_z) < -1.0
    assert np.max(display_z) > 1.0
    assert np.min(field.z_data) < -1.0
    assert np.max(field.z_data) > 1.0


def test_named_field_palette_aliases_resolve_for_heatmaps() -> None:
    x, y = sp.symbols("x y")
    fig = Figure()

    field = fig.density(x + y, x, y, colorscale="phase", grid=(4, 4))
    trace = fig.figure_widget.data[0]

    assert field.colorscale == "phase"
    assert isinstance(trace, go.Heatmap)
    assert isinstance(trace.colorscale, tuple)
    assert len(trace.colorscale) > 2


def test_scalar_field_snapshot_and_codegen_round_trip() -> None:
    x, y = sp.symbols("x y")
    fig = Figure(x_range=(-4, 4), y_range=(-3, 3))
    fig.temperature(
        x**2 - y,
        (x, -2, 2),
        (y, -1, 1),
        id="temp",
        label="Temp",
        grid=(8, 6),
        colorscale="thermal",
        z_range=(-1, 2),
        z_step=0.5,
        under_color="black",
        over_color="white",
        opacity=0.4,
        reversescale=True,
        connectgaps=False,
    )

    snapshot = fig.snapshot()
    field_snapshot = snapshot.plots["temp"]
    code = fig.to_code()

    assert isinstance(field_snapshot, FieldPlotSnapshot)
    assert field_snapshot.is_field is True
    assert field_snapshot.preset == "temperature"
    assert field_snapshot.render_mode == "heatmap"
    assert field_snapshot.grid == (8, 6)
    assert field_snapshot.colorscale == "thermal"
    assert field_snapshot.z_range == (-1.0, 2.0)
    assert field_snapshot.z_step == 0.5
    assert field_snapshot.under_color == "black"
    assert field_snapshot.over_color == "white"
    assert "from gu_toolkit import Figure, parameter, plot, temperature, info" in code
    assert "temperature(" in code
    assert "grid=(8, 6)" in code
    assert "z_step=0.5" in code
    assert "under_color='black'" in code
    assert "over_color='white'" in code

    namespace: dict[str, object] = {}
    exec(code, namespace)
    rebuilt = namespace["fig"]
    rebuilt_snapshot = rebuilt.snapshot()  # type: ignore[attr-defined]
    rebuilt_field = rebuilt_snapshot.plots["temp"]

    assert isinstance(rebuilt_field, FieldPlotSnapshot)
    assert rebuilt_field.func == field_snapshot.func
    assert rebuilt_field.x_domain == field_snapshot.x_domain
    assert rebuilt_field.y_domain == field_snapshot.y_domain
    assert rebuilt_field.grid == field_snapshot.grid
    assert rebuilt_field.colorscale == field_snapshot.colorscale
    assert rebuilt_field.z_range == field_snapshot.z_range
    assert rebuilt_field.z_step == field_snapshot.z_step
    assert rebuilt_field.under_color == field_snapshot.under_color
    assert rebuilt_field.over_color == field_snapshot.over_color
    assert rebuilt_field.reversescale == field_snapshot.reversescale


def test_field_style_options_are_discoverable() -> None:
    options = field_style_options()

    for key in (
        "colorscale",
        "z_range",
        "z_step",
        "under_color",
        "over_color",
        "show_colorbar",
        "showscale",
        "opacity",
        "alpha",
        "levels",
        "level_step",
        "level_start",
        "level_end",
        "filled",
        "show_labels",
        "line_color",
        "line_width",
        "line_dash",
        "dash",
        "smoothing",
        "zsmooth",
        "connectgaps",
        "trace",
    ):
        assert key in options

    assert Figure.field_style_options() == options


def test_field_palette_options_are_discoverable() -> None:
    options = field_palette_options()

    for key in (
        "thermal",
        "temperature",
        "phase",
        "diffraction",
        "potential",
        "grayscale",
        "viridis",
    ):
        assert key in options

    assert Figure.field_palette_options() == options
