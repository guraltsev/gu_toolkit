from __future__ import annotations

from gu_toolkit import Figure
from gu_toolkit.Slider import FloatSlider


RESPONSIVE_ROW_NAMES = (
    "_cartesian_setup_row",
    "_parametric_setup_row",
    "_field_setup_row",
    "_visibility_row",
    "_identity_row",
    "_cartesian_resolution_row",
    "_parametric_resolution_row",
    "_field_resolution_row",
)

EXPECTED_FIELD_FLEX = {
    "_plot_type_field": "0 1 260px",
    "_cartesian_variable_field": "0 1 180px",
    "_parameter_variable_field": "0 1 180px",
    "_parameter_min_field": "1 1 160px",
    "_parameter_max_field": "1 1 160px",
    "_field_x_variable_field": "0 1 160px",
    "_field_y_variable_field": "0 1 160px",
    "_label_field": "1 1 280px",
    "_id_field": "0 1 220px",
    "_visibility_field": "0 1 150px",
    "_cartesian_resolution_field": "0 1 190px",
    "_parametric_resolution_field": "0 1 190px",
    "_field_grid_x_field": "0 1 190px",
    "_field_grid_y_field": "0 1 190px",
}

HOSTED_PANEL_NAMES = (
    ("plot editor", "_panel"),
    ("plot editor error", "_error_panel"),
)

HOSTED_OVERLAY_NAMES = (
    ("plot editor overlay", "_modal"),
    ("plot editor error overlay", "_error_modal"),
)

TAB_CLASS_NAMES = (
    "gu-action-button",
    "gu-action-button-tab",
    "gu-plot-editor-tab-button",
)


def _layout_value(widget: object, attr_name: str) -> str | None:
    layout = getattr(widget, "layout", None)
    if layout is None:
        return None
    try:
        return getattr(layout, attr_name)
    except Exception:
        return None


def test_plot_editor_rows_and_fields_follow_shared_responsive_contract() -> None:
    editor = Figure()._plot_editor

    for row_name in RESPONSIVE_ROW_NAMES:
        row = getattr(editor, row_name)
        assert _layout_value(row, "flex_flow") == "row wrap"
        assert _layout_value(row, "width") == "100%"
        assert _layout_value(row, "min_width") == "0"
        assert _layout_value(row, "max_width") == "100%"
        assert _layout_value(row, "overflow_x") == "hidden"
        assert _layout_value(row, "overflow_y") == "visible"
        assert "gu-wrap-row" in row._dom_classes
        assert "gu-plot-editor-wrap-row" in row._dom_classes
        for child in row.children:
            assert _layout_value(child, "min_width") == "0"
            assert _layout_value(child, "max_width") == "100%"

    for field_name, flex in EXPECTED_FIELD_FLEX.items():
        field = getattr(editor, field_name)
        assert _layout_value(field, "flex") == flex
        assert _layout_value(field, "width") == "100%"
        assert _layout_value(field, "min_width") == "0"
        assert _layout_value(field, "max_width") == "100%"
        assert _layout_value(field, "overflow_x") == "hidden"
        assert _layout_value(field, "overflow_y") == "visible"

    assert editor._cartesian_setup_row.children == (
        editor._plot_type_field,
        editor._cartesian_variable_field,
    )
    assert editor._parametric_setup_row.children == (
        editor._plot_type_field,
        editor._parameter_variable_field,
        editor._parameter_min_field,
        editor._parameter_max_field,
    )
    assert editor._field_setup_row.children == (
        editor._plot_type_field,
        editor._field_x_variable_field,
        editor._field_y_variable_field,
    )
    assert editor._visibility_row.children == (editor._visibility_field,)
    assert editor._identity_row.children == (
        editor._label_field,
        editor._id_field,
    )


def test_shared_single_line_controls_hide_cross_axis_overflow() -> None:
    figure = Figure()
    editor = figure._plot_editor
    legend = figure._legend

    single_line_controls = (
        editor._kind,
        editor._id_text,
        editor._label_text,
        editor._curve_style_color,
        editor._curve_style_thickness,
        editor._curve_style_opacity,
        editor._curve_style_dash,
        legend._dialog_color,
        legend._dialog_width,
        legend._dialog_opacity,
        legend._dialog_dash,
    )

    for control in single_line_controls:
        assert _layout_value(control, "overflow_x") == "hidden"
        assert _layout_value(control, "overflow_y") == "hidden"


def test_parametric_labels_follow_the_selected_parameter_symbol() -> None:
    editor = Figure()._plot_editor
    editor.open_for_new(default_kind="parametric")

    editor._parameter_variable.value = "u"

    assert editor._parametric_x_label.value == r"\(x\left(u\right)\)"
    assert editor._parametric_y_label.value == r"\(y\left(u\right)\)"
    assert editor._parameter_min_label.value == r"\(u_{\mathrm{min}}\)"
    assert editor._parameter_max_label.value == r"\(u_{\mathrm{max}}\)"
    assert editor._parameter_min.aria_label == "Minimum value for u"
    assert editor._parameter_max.aria_label == "Maximum value for u"

    editor._parameter_variable.value = r"\theta"

    assert editor._parametric_x_label.value == r"\(x\left(\theta\right)\)"
    assert editor._parametric_y_label.value == r"\(y\left(\theta\right)\)"
    assert editor._parameter_min_label.value == r"\(\theta_{\mathrm{min}}\)"
    assert editor._parameter_max_label.value == r"\(\theta_{\mathrm{max}}\)"


def test_hosted_plot_editor_and_legend_dialogs_use_container_relative_widths() -> None:
    figure = Figure()
    editor = figure._plot_editor
    legend = figure._legend

    for panel_label, attr_name in HOSTED_PANEL_NAMES:
        panel = getattr(editor, attr_name)
        for layout_attr in ("width", "min_width", "max_width"):
            value = _layout_value(panel, layout_attr)
            assert value is not None
            assert "100%" in value, (panel_label, layout_attr, value)
            assert "100vw" not in value, (panel_label, layout_attr, value)
            assert "100vh" not in value, (panel_label, layout_attr, value)

    for overlay_label, attr_name in HOSTED_OVERLAY_NAMES:
        overlay = getattr(editor, attr_name)
        assert _layout_value(overlay, "width") == "100%", (
            overlay_label,
            _layout_value(overlay, "width"),
        )
        assert _layout_value(overlay, "height") == "100%", (
            overlay_label,
            _layout_value(overlay, "height"),
        )

    for layout_attr in ("width", "min_width", "max_width"):
        value = _layout_value(legend._dialog_panel, layout_attr)
        assert value is not None
        assert "100%" in value, ("legend dialog", layout_attr, value)
        assert "100vw" not in value, ("legend dialog", layout_attr, value)
        assert "100vh" not in value, ("legend dialog", layout_attr, value)

    assert _layout_value(legend._dialog_modal, "width") == "100%"
    assert _layout_value(legend._dialog_modal, "height") == "100%"


def test_plot_editor_header_tabs_and_shared_sections_follow_shared_shell() -> None:
    editor = Figure()._plot_editor
    editor.open_for_new(default_kind="cartesian")

    assert editor._title.value == "Plot editor"
    assert "<b>" not in editor._title.value.lower()
    assert "gu-modal-title-text" in editor._title._dom_classes
    assert editor._title_chip.layout.display == "none"
    assert editor._apply_button.description == "Create"
    assert editor._id_text.layout.display == "flex"
    assert editor._id_readonly.layout.display == "none"

    header = editor._panel.children[0]
    tab_bar = editor._panel.children[1]
    assert "gu-modal-header" in header._dom_classes
    assert "gu-tab-bar" in tab_bar._dom_classes
    assert editor._expression_tab.layout.display == "flex"
    assert editor._style_tab.layout.display == "none"
    assert editor._settings_tab.layout.display == "none"

    for class_name in TAB_CLASS_NAMES:
        assert class_name in editor._expression_tab_button._dom_classes
        assert class_name in editor._style_tab_button._dom_classes
        assert class_name in editor._settings_tab_button._dom_classes

    assert editor._expression_tab_button.description == "Expression"
    assert editor._style_tab_button.description == "Style"
    assert editor._settings_tab_button.description == "Advanced"
    assert "mod-selected" in editor._expression_tab_button._dom_classes
    assert "mod-selected" not in editor._style_tab_button._dom_classes
    assert "mod-selected" not in editor._settings_tab_button._dom_classes

    editor._set_tab("style")

    assert "mod-selected" not in editor._expression_tab_button._dom_classes
    assert "mod-selected" in editor._style_tab_button._dom_classes
    assert "mod-selected" not in editor._settings_tab_button._dom_classes
    assert editor._expression_tab.layout.display == "none"
    assert editor._style_tab.layout.display == "flex"
    assert editor._settings_tab.layout.display == "none"
    assert editor._tab_bridge.selected_index == 1
    assert editor._style_tab.children[1] is editor._visibility_section
    assert editor._style_tab.children[2] is editor._curve_style_section

    editor._set_tab("advanced")

    assert "mod-selected" not in editor._expression_tab_button._dom_classes
    assert "mod-selected" not in editor._style_tab_button._dom_classes
    assert "mod-selected" in editor._settings_tab_button._dom_classes
    assert editor._expression_tab.layout.display == "none"
    assert editor._style_tab.layout.display == "none"
    assert editor._settings_tab.layout.display == "flex"
    assert editor._tab_bridge.selected_index == 2

    assert editor._views_field.layout.display == "flex"
    assert editor._views_note.layout.display == "none"
    assert editor._placement_body.children == (editor._views_field,)


def test_plot_editor_switches_to_readonly_id_presentation_in_edit_mode_and_uses_inline_errors() -> None:
    figure = Figure()
    figure.add_view("alt")
    editor = figure._plot_editor

    editor.open_for_new(default_kind="cartesian")
    assert editor._views_field.layout.display == "flex"
    assert editor._views_note.layout.display == "none"

    editor._cartesian_expression.value = "x"
    editor._cartesian_variable.value = "x"
    editor._views.value = ()
    editor._apply_button.click()

    assert editor.panel_visible is True
    assert editor._error_open is False
    assert editor._active_tab == "advanced"
    assert editor._settings_alert.layout.display == "flex"
    assert "Select at least one target view." in editor._settings_alert.value

    editor.open_for_new(default_kind="parametric")
    editor._parametric_x.value = r"\cos(t)"
    editor._parametric_y.value = r"\sin(t)"
    editor._parameter_variable.value = "t"
    editor._parameter_min.value = "0"
    editor._parameter_max.value = "a"
    editor._apply_button.click()

    assert editor.panel_visible is True
    assert editor._error_open is False
    assert editor._active_tab == "expression"
    assert editor._expression_alert.layout.display == "flex"
    assert "symbolic bounds are not supported" in editor._expression_alert.value

    import sympy as sp

    x = sp.symbols("x")
    figure.plot(x, x, id="curve", label="Curve")
    editor.open_for_plot("curve")

    assert editor._title.value == "Plot editor"
    assert editor._title_chip.layout.display == "block"
    assert "Editing curve" in editor._title_chip.value
    assert "gu-title-chip" not in editor._title_chip._dom_classes
    assert editor._id_text.layout.display == "none"
    assert editor._id_readonly.layout.display == "block"
    assert editor._apply_button.description == "Apply"


def test_slider_settings_dialog_uses_shared_shell_wording_and_done_action() -> None:
    slider = FloatSlider(description=r"$a$:")

    assert slider.settings_title_text.value == "Parameter settings"
    assert "<b>" not in slider.settings_title_text.value.lower()
    assert slider.settings_subject.value == r"$a$"
    assert "gu-title-chip" not in slider.settings_subject._dom_classes
    assert slider._settings_animation_section.children[0].value == "Animation"
    assert slider.btn_done_settings.description == "Done"
    assert slider.btn_settings.description == "Open parameter settings"
    assert slider.btn_close_settings.description == "Close parameter settings"
    assert slider.settings_panel.layout.width == "min(460px, calc(100vw - 32px))"
    assert slider.settings_panel.layout.min_width == "min(320px, calc(100vw - 32px))"


def test_plot_editor_single_view_keeps_target_views_table_available() -> None:
    editor = Figure()._plot_editor
    editor.open_for_new(default_kind="cartesian")

    assert editor._views_field.layout.display == "flex"
    assert editor._views_field.layout.height == "auto"
    assert editor._views_field.layout.min_height == "0px"
    assert editor._views.layout.display == "flex"
    assert editor._views.layout.height == "auto"
    assert editor._views.layout.min_height == "96px"
    assert editor._views_note.layout.display == "none"
    assert editor._placement_body.children == (editor._views_field,)


def test_plot_editor_multi_view_keeps_target_views_field_mounted_and_moves_visibility_to_style_tab() -> None:
    figure = Figure()
    figure.add_view("alt")
    editor = figure._plot_editor

    editor.open_for_new(default_kind="cartesian")

    assert editor._views_field.layout.display == "flex"
    assert editor._views_note.layout.display == "none"
    assert editor._placement_body.children == (editor._views_field,)
    assert editor._visibility_row.children == (editor._visibility_field,)
    assert editor._style_tab.children[1] is editor._visibility_section
