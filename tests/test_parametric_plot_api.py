from __future__ import annotations

import numpy as np
import pytest
import sympy as sp

from gu_toolkit import Figure, ParametricPlot, parametric_plot


def test_parametric_plot_renders_symbolic_curve_samples() -> None:
    t = sp.symbols("t")
    fig = Figure(sampling_points=8)

    curve = fig.parametric_plot(
        (sp.cos(t), sp.sin(t)),
        (t, 0, sp.pi),
        id="arc",
        label="arc",
        color="purple",
    )

    expected_t = np.linspace(0.0, float(sp.pi), 8)
    assert isinstance(curve, ParametricPlot)
    assert curve.parameter_var == t
    assert curve.parameter_domain == (0.0, float(sp.pi))
    assert curve.x_expression == sp.cos(t)
    assert curve.y_expression == sp.sin(t)
    assert curve.parameters == ()
    assert np.allclose(curve.x_data, np.cos(expected_t))
    assert np.allclose(curve.y_data, np.sin(expected_t))
    assert fig.figure_widget.data[0].name == "arc"


def test_parametric_plot_supports_constant_coordinate_component() -> None:
    t = sp.symbols("t")
    fig = Figure(sampling_points=5)

    curve = fig.parametric_plot((sp.Integer(2), t), (t, -1, 1), id="vertical")

    assert np.allclose(curve.x_data, np.full(5, 2.0))
    assert np.allclose(curve.y_data, np.linspace(-1.0, 1.0, 5))


def test_parametric_plot_updates_both_coordinate_components_from_parameters() -> None:
    t, a, b = sp.symbols("t a b")
    fig = Figure(sampling_points=6)
    fig.parameter(a, value=2.0)
    fig.parameter(b, value=0.5)

    curve = fig.parametric_plot(
        (a * sp.cos(t), b * sp.sin(t)),
        (t, 0, sp.pi / 2),
        id="ellipse",
    )

    before_x = curve.x_data.copy()
    before_y = curve.y_data.copy()

    fig.parameters[a].value = 3.0
    fig.parameters[b].value = 1.5

    # Parameter-triggered renders are queued until the figure flushes them.
    assert np.array_equal(curve.x_data, before_x)
    assert np.array_equal(curve.y_data, before_y)

    fig.flush_render_queue()

    expected_t = np.linspace(0.0, float(sp.pi) / 2.0, 6)
    assert curve.parameters == (a, b)
    assert np.allclose(curve.x_data, 3.0 * np.cos(expected_t))
    assert np.allclose(curve.y_data, 1.5 * np.sin(expected_t))


def test_module_level_parametric_plot_routes_to_current_figure() -> None:
    t = sp.symbols("t")
    fig = Figure()

    with fig:
        curve = parametric_plot((t, t**2), (t, -1, 1), id="parabola", samples=4)

    assert fig.plots["parabola"] is curve
    assert np.allclose(curve.x_data, np.linspace(-1.0, 1.0, 4))
    assert np.allclose(curve.y_data, np.linspace(-1.0, 1.0, 4) ** 2)


def test_parametric_plot_replaces_existing_cartesian_plot_with_same_id() -> None:
    x, t = sp.symbols("x t")
    fig = Figure(sampling_points=5)

    fig.plot(sp.sin(x), x, id="shared")
    replaced = fig.parametric_plot((sp.cos(t), sp.sin(t)), (t, 0, sp.pi), id="shared")

    assert isinstance(replaced, ParametricPlot)
    assert fig.plots["shared"] is replaced
    assert len(fig.figure_widget.data) == 1
    assert np.allclose(replaced.x_data, np.cos(np.linspace(0.0, float(sp.pi), 5)))


def test_parametric_plot_snapshot_and_codegen_round_trip() -> None:
    t = sp.symbols("t")
    fig = Figure(sampling_points=32)
    fig.parametric_plot(
        (sp.cos(t), sp.sin(t)),
        (t, 0, 2 * sp.pi),
        id="unit_circle",
        label="unit circle",
        color="green",
        autonormalization=True,
    )

    snapshot = fig.snapshot()
    plot_snapshot = snapshot.plots["unit_circle"]
    code = fig.to_code()

    assert plot_snapshot.is_parametric is True
    assert plot_snapshot.x_func == sp.cos(t)
    assert plot_snapshot.func == sp.sin(t)
    assert plot_snapshot.parameter_domain == pytest.approx((0.0, float(2 * sp.pi)))
    assert plot_snapshot.autonormalization is True
    assert "from gu_toolkit import Figure, parameter, plot, parametric_plot, info" in code
    assert "parametric_plot(" in code
    assert "(sp.cos(t), sp.sin(t))" in code
    assert "(t, 0.0, 6.283185307179586)" in code
    assert "autonormalization=True" in code

    namespace: dict[str, object] = {}
    exec(code, namespace)
    rebuilt = namespace["fig"]
    rebuilt_snapshot = rebuilt.snapshot()  # type: ignore[attr-defined]
    rebuilt_plot = rebuilt_snapshot.plots["unit_circle"]

    assert rebuilt_plot.is_parametric is True
    assert rebuilt_plot.x_func == plot_snapshot.x_func
    assert rebuilt_plot.func == plot_snapshot.func
    assert rebuilt_plot.parameter_domain == pytest.approx(plot_snapshot.parameter_domain)
    assert rebuilt_plot.color == plot_snapshot.color
    assert rebuilt_plot.autonormalization == plot_snapshot.autonormalization
