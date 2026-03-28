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
        curve_autonormalization=None,
    )
    base.update(overrides)
    return PlotEditorDraft(**base)


def test_toolbar_button_opens_new_dialog_and_row_edit_button_loads_existing_plot() -> None:
    x = sp.symbols("x")
    fig = Figure()

    assert fig._plot_editor.panel_visible is False
    assert fig._legend._plot_add_button is not None
    assert fig._legend._plot_add_button.description == "Create plot from expression"
    assert fig._layout.legend_header_toolbar.children == (fig._legend._plot_add_button,)

    fig._legend._plot_add_button.click()

    editor = fig._plot_editor
    assert editor.panel_visible is True
    assert editor._editing_plot_id is None
    assert editor._kind.value == "cartesian"
    assert editor._title.value == "Plot editor"
    assert editor._title_chip.layout.display == "none"
    assert editor._expression_tab.layout.display == "flex"
    assert editor._style_tab.layout.display == "none"
    assert editor._settings_tab.layout.display == "none"
    assert editor._expression_tab.children[0] is editor._expression_alert
    assert editor._expression_tab.children[1] is editor._cartesian_box
    assert editor._style_tab.children[0] is editor._style_alert
    assert editor._style_tab.children[1] is editor._visibility_section
    assert editor._style_tab.children[2] is editor._curve_style_section
    assert editor._style_tab.children[3] is editor._curve_sound_section
    assert editor._settings_tab.children[0] is editor._settings_alert
    assert editor._settings_tab.children[1] is editor._placement_section
    assert editor._settings_tab.children[2] is editor._identity_section
    assert editor._settings_tab.children[3] is editor._resolution_section
    assert editor._cartesian_setup_row.children == (
        editor._plot_type_field,
        editor._cartesian_variable_field,
    )
    assert editor._cartesian_expression_field.children[1] is editor._cartesian_expression
    assert editor._views_note.layout.display == "none"
    assert editor._views_field.layout.display == "flex"
    assert editor._placement_body.children == (editor._views_field,)
    assert editor._visibility_section.children[1] is editor._visibility_row
    assert "Parameters:" not in editor._parameter_preview.value

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
    assert editor._title_chip.layout.display == "block"
    assert "Editing sin" in editor._title_chip.value
    assert "gu-title-chip" not in editor._title_chip._dom_classes
    assert editor._id_text.layout.display == "none"
    assert editor._id_readonly.layout.display == "block"
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
    plot = fig.plot(
        x,
        x,
        id="curve",
        label="Original",
        samples=40,
        color="#111111",
        thickness=3.0,
        dash="dash",
        opacity=0.7,
    )

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
    assert plot.color == "#111111"
    assert plot.thickness == 3.0
    assert plot.dash == "dash"
    assert plot.opacity == 0.7
    assert "a" in set(fig.parameters.keys())


def test_apply_plot_editor_draft_applies_curve_style_overrides_to_curves() -> None:
    fig = Figure()

    cartesian = apply_plot_editor_draft(
        fig,
        _blank_draft(
            kind="cartesian",
            plot_id="curve",
            cartesian_expression_latex="x",
            cartesian_var_latex="x",
            curve_color="#123456",
            curve_thickness=4.5,
            curve_dash="dashdot",
            curve_opacity=0.4,
            curve_autonormalization=True,
        ),
    )

    assert isinstance(cartesian, Plot)
    assert cartesian.color == "#123456"
    assert cartesian.thickness == 4.5
    assert cartesian.dash == "dashdot"
    assert cartesian.opacity == 0.4
    assert cartesian.autonormalization() is True

    parametric = apply_plot_editor_draft(
        fig,
        _blank_draft(
            kind="parametric",
            plot_id="orbit",
            parametric_x_latex=r"\cos(t)",
            parametric_y_latex=r"\sin(t)",
            parameter_var_latex="t",
            parameter_min_latex="0",
            parameter_max_latex=r"2\pi",
            curve_color="#654321",
            curve_thickness=2.5,
            curve_dash="dot",
            curve_opacity=0.6,
            curve_autonormalization=True,
        ),
    )

    assert isinstance(parametric, ParametricPlot)
    assert parametric.color == "#654321"
    assert parametric.thickness == 2.5
    assert parametric.dash == "dot"
    assert parametric.opacity == 0.6
    assert parametric.autonormalization() is True


def test_plot_editor_uses_inline_validation_and_advanced_tab_for_missing_views() -> None:
    fig = Figure()
    fig.add_view("alt")
    editor = fig._plot_editor

    editor.open_for_new(default_kind="cartesian")
    editor._cartesian_expression.value = "x"
    editor._cartesian_variable.value = "x"
    editor._views.value = ()

    editor._apply_button.click()

    assert editor.panel_visible is True
    assert editor._error_open is False
    assert editor._active_tab == "advanced"
    assert editor._settings_alert.layout.display == "flex"
    assert "Select at least one target view." in editor._settings_alert.value


def test_plot_editor_shows_parse_errors_in_modal_without_inline_alert_artifacts() -> None:
    fig = Figure()
    editor = fig._plot_editor

    editor.open_for_new(default_kind="cartesian")
    editor._cartesian_expression.value = r"\sin("
    editor._cartesian_variable.value = "x"

    editor._apply_button.click()

    assert editor.panel_visible is True
    assert editor._error_open is True
    assert editor._expression_alert.layout.display == "none"
    assert "Could not parse Cartesian expression." in editor._error_message.value


def test_plot_editor_defers_parametric_validation_until_apply_and_shows_inline_expression_error() -> None:
    fig = Figure()
    editor = fig._plot_editor

    editor.open_for_new(default_kind="parametric")
    editor._parametric_x.value = r"\cos(t)"
    editor._parametric_y.value = r"\sin(t)"
    editor._parameter_variable.value = "t"
    editor._parameter_min.value = "0"
    editor._parameter_max.value = "a"
    editor._update_parameter_preview()

    assert "symbolic bounds are not supported" not in editor._parameter_preview.value
    assert editor._expression_alert.layout.display == "none"
    assert editor._error_open is False

    editor._apply_button.click()

    assert editor.panel_visible is True
    assert editor._error_open is False
    assert editor._active_tab == "expression"
    assert editor._expression_alert.layout.display == "flex"
    assert "symbolic bounds are not supported" in editor._expression_alert.value


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
