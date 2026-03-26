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
        visible=True,
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
    assert fig._legend._plot_add_button.description == "Create plot from expression"

    fig._legend._plot_add_button.click()

    editor = fig._plot_editor
    assert editor.panel_visible is True
    assert editor._editing_plot_id is None
    assert editor._kind.value == "cartesian"
    assert editor._formula_tab.layout.display == "flex"
    assert editor._advanced_tab.layout.display == "none"
    assert editor._formula_tab.children[0] is editor._plot_type_row
    assert editor._plot_type_field.children[1] is editor._kind
    assert editor._formula_tab.children[1] is editor._cartesian_box
    assert editor._cartesian_expression_field.children[1] is editor._cartesian_expression
    assert editor._cartesian_variable_field.children[1] is editor._cartesian_variable
    assert editor._advanced_tab.children[0] is editor._advanced_meta_row
    assert editor._advanced_tab.children[1] is editor._views_field
    assert editor._views_field.children[1] is editor._views
    assert editor._advanced_meta_row.children[0].children[1] is editor._label_text
    assert editor._advanced_meta_row.children[1].children[1] is editor._id_text
    assert editor._advanced_meta_row.children[2].children[1].children[0] is editor._visible_toggle
    assert "validated when you click Create" in editor._status_bar.value
    assert "Advanced settings hold label, id, visibility, views" in editor._status_bar.value

    editor.close()
    fig.plot(sp.sin(x), x, id="sin", label="Sine")

    row = fig._legend._rows["sin"]
    assert row.edit_button is not None
    assert row.edit_button.description.startswith("Edit plot")

    row.edit_button.click()

    assert editor.panel_visible is True
    assert editor._editing_plot_id == "sin"
    assert editor._label_text.value == "Sine"
    assert editor._apply_button.description == "Apply"
    assert "sin" in editor._cartesian_expression.value.lower()


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
    assert plot.visible is True
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
    assert plot.visible is True
    assert plot.samples == 240
    assert plot.parameter_var == sp.Symbol("t")
    assert "a" in set(fig.parameters.keys())


def test_apply_plot_editor_draft_updates_existing_plot_label_views_samples_and_visibility() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.add_view("alt")
    plot = fig.plot(x, x, id="curve", label="Original", samples=40)

    draft = _blank_draft(
        kind="cartesian",
        plot_id="curve",
        label="Edited",
        view_ids=("alt",),
        visible=False,
        cartesian_expression_latex="a*x",
        cartesian_var_latex="x",
        cartesian_samples=123,
    )

    updated = apply_plot_editor_draft(fig, draft, existing_plot=plot)

    assert updated is plot
    assert plot.label == "Edited"
    assert plot.visible is False
    assert plot.samples == 123
    assert plot.views == ("alt",)
    assert "a" in set(fig.parameters.keys())


def test_plot_editor_defers_parametric_validation_until_apply_and_uses_error_modal() -> None:
    fig = Figure()

    draft = _blank_draft(
        kind="parametric",
        parametric_x_latex=r"\cos(t)",
        parametric_y_latex=r"\sin(t)",
        parameter_var_latex="t",
        parameter_min_latex="0",
        parameter_max_latex="a",
    )

    editor = fig._plot_editor
    editor.open_for_new(default_kind="parametric")
    editor._parametric_x.value = draft.parametric_x_latex
    editor._parametric_y.value = draft.parametric_y_latex
    editor._parameter_variable.value = draft.parameter_var_latex
    editor._parameter_min.value = draft.parameter_min_latex
    editor._parameter_max.value = draft.parameter_max_latex
    editor._update_parameter_preview()

    assert "symbolic bounds are not supported" not in editor._parameter_preview.value
    assert "validated when you click Create" in editor._parameter_preview.value
    assert editor._error_open is False

    editor._apply_button.click()

    assert editor.panel_visible is True
    assert editor._error_open is True
    assert editor._error_modal.layout.display == "flex"
    assert editor._active_tab == "formula"
    assert "symbolic bounds are not supported" in editor._error_message.value


def test_plot_editor_missing_views_routes_error_to_advanced_tab() -> None:
    fig = Figure()
    editor = fig._plot_editor

    editor.open_for_new(default_kind="cartesian")
    editor._cartesian_expression.value = "x"
    editor._cartesian_variable.value = "x"
    editor._views.value = ()

    editor._apply_button.click()

    assert editor.panel_visible is True
    assert editor._error_open is True
    assert editor._active_tab == "advanced"
    assert "Select at least one target view." in editor._error_message.value


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
    assert contour.visible is True
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
    assert temperature.visible is True
    assert temperature.grid == (42, 39)
    assert temperature.label == "Heat"
