from __future__ import annotations

import sympy as sp

from gu_toolkit import Figure
from gu_toolkit.figure_field import ScalarFieldPlot
from gu_toolkit.figure_parametric_plot import ParametricPlot
from gu_toolkit.figure_plot import Plot
from gu_toolkit.figure_plot_editor import PlotEditorDraft, apply_plot_editor_draft


def _blank_draft(**overrides: object) -> PlotEditorDraft:
    base = dict(
        kind="cartesian",
        plot_id=None,
        label="",
        view_ids=("main",),
        cartesian_expression_latex="",
        cartesian_var_latex="x",
        cartesian_samples=500,
        parametric_x_latex="",
        parametric_y_latex="",
        parameter_var_latex="t",
        parameter_min_latex="0",
        parameter_max_latex=r"2\pi",
        parametric_samples=500,
        field_expression_latex="",
        field_x_var_latex="x",
        field_y_var_latex="y",
        field_grid_x=120,
        field_grid_y=120,
    )
    base.update(overrides)
    return PlotEditorDraft(**base)


def test_toolbar_button_opens_new_dialog_and_row_edit_button_loads_existing_plot() -> None:
    x = sp.symbols("x")
    fig = Figure()

    assert fig._plot_editor.panel_visible is False
    assert fig._legend._plot_add_button is not None

    fig._legend._plot_add_button.click()

    assert fig._plot_editor.panel_visible is True
    assert fig._plot_editor._editing_plot_id is None
    assert fig._plot_editor._kind.value == "cartesian"

    fig._plot_editor.close()
    fig.plot(sp.sin(x), x, id="sin", label="Sine")

    row = fig._legend._rows["sin"]
    assert row.edit_button is not None

    row.edit_button.click()

    assert fig._plot_editor.panel_visible is True
    assert fig._plot_editor._editing_plot_id == "sin"
    assert fig._plot_editor._label_text.value == "Sine"
    assert "sin" in fig._plot_editor._cartesian_expression.value.lower()


def test_apply_plot_editor_draft_creates_cartesian_plot_and_missing_parameter() -> None:
    fig = Figure()
    fig.add_view("alt")

    draft = _blank_draft(
        kind="cartesian",
        plot_id="line",
        label="Line",
        view_ids=("main", "alt"),
        cartesian_expression_latex="a*x + 1",
        cartesian_var_latex="x",
        cartesian_samples=321,
    )

    plot = apply_plot_editor_draft(fig, draft)

    assert isinstance(plot, Plot)
    assert plot.id == "line"
    assert plot.label == "Line"
    assert plot.samples == 321
    assert plot.views == ("alt", "main")
    assert "a" in set(fig.parameters.keys())


def test_apply_plot_editor_draft_creates_parametric_plot_and_missing_parameter() -> None:
    fig = Figure()

    draft = _blank_draft(
        kind="parametric",
        plot_id="orbit",
        label="Orbit",
        parametric_x_latex=r"a\cos(t)",
        parametric_y_latex=r"\sin(t)",
        parameter_var_latex="t",
        parameter_min_latex="0",
        parameter_max_latex=r"2\pi",
        parametric_samples=240,
    )

    plot = apply_plot_editor_draft(fig, draft)

    assert isinstance(plot, ParametricPlot)
    assert plot.id == "orbit"
    assert plot.label == "Orbit"
    assert plot.samples == 240
    assert plot.parameter_var == sp.Symbol("t")
    assert "a" in set(fig.parameters.keys())


def test_apply_plot_editor_draft_updates_existing_plot_label_views_and_samples() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.add_view("alt")
    plot = fig.plot(x, x, id="curve", label="Original", samples=40)

    draft = _blank_draft(
        kind="cartesian",
        plot_id="curve",
        label="Edited",
        view_ids=("alt",),
        cartesian_expression_latex="a*x",
        cartesian_var_latex="x",
        cartesian_samples=123,
    )

    updated = apply_plot_editor_draft(fig, draft, existing_plot=plot)

    assert updated is plot
    assert plot.label == "Edited"
    assert plot.samples == 123
    assert plot.views == ("alt",)
    assert "a" in set(fig.parameters.keys())


def test_plot_editor_rejects_symbolic_parametric_bounds_for_now() -> None:
    fig = Figure()

    draft = _blank_draft(
        kind="parametric",
        parametric_x_latex=r"\cos(t)",
        parametric_y_latex=r"\sin(t)",
        parameter_var_latex="t",
        parameter_min_latex="0",
        parameter_max_latex="a",
    )

    preview = fig._plot_editor
    preview.open_for_new(default_kind="parametric")
    preview._parametric_x.value = draft.parametric_x_latex
    preview._parametric_y.value = draft.parametric_y_latex
    preview._parameter_variable.value = draft.parameter_var_latex
    preview._parameter_min.value = draft.parameter_min_latex
    preview._parameter_max.value = draft.parameter_max_latex
    preview._update_parameter_preview()

    assert "symbolic bounds are not supported" in preview._parameter_preview.value


def test_apply_plot_editor_draft_creates_contour_and_temperature_plots() -> None:
    fig = Figure()
    fig.add_view("alt")

    contour_draft = _blank_draft(
        kind="contour",
        plot_id="contours",
        label="Contours",
        view_ids=("alt",),
        field_expression_latex="x^2 + y^2 + a",
        field_x_var_latex="x",
        field_y_var_latex="y",
        field_grid_x=80,
        field_grid_y=60,
    )
    contour = apply_plot_editor_draft(fig, contour_draft)

    assert isinstance(contour, ScalarFieldPlot)
    assert contour.render_mode == "contour"
    assert contour.preset is None
    assert contour.grid == (80, 60)
    assert contour.views == ("alt",)
    assert contour.label == "Contours"
    assert "a" in set(fig.parameters.keys())

    temperature_draft = _blank_draft(
        kind="temperature",
        plot_id="heat",
        label="Heat",
        field_expression_latex="x + y",
        field_x_var_latex="x",
        field_y_var_latex="y",
        field_grid_x=42,
        field_grid_y=39,
    )
    temperature = apply_plot_editor_draft(fig, temperature_draft)

    assert isinstance(temperature, ScalarFieldPlot)
    assert temperature.render_mode == "heatmap"
    assert temperature.preset == "temperature"
    assert temperature.grid == (42, 39)
    assert temperature.label == "Heat"
