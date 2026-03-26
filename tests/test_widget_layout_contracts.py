from __future__ import annotations

from gu_toolkit import Figure


RESPONSIVE_ROW_NAMES = (
    "_plot_type_row",
    "_cartesian_variable_row",
    "_parametric_parameter_row",
    "_field_variable_row",
    "_advanced_meta_row",
    "_cartesian_samples_row",
    "_parametric_samples_row",
    "_field_grid_row",
)

EXPECTED_FIELD_FLEX = {
    "_plot_type_field": "0 1 260px",
    "_cartesian_variable_field": "0 1 190px",
    "_parameter_variable_field": "0 1 190px",
    "_parameter_min_field": "1 1 190px",
    "_parameter_max_field": "1 1 190px",
    "_field_x_variable_field": "0 1 190px",
    "_field_y_variable_field": "0 1 190px",
    "_label_field": "1 1 280px",
    "_id_field": "0 1 220px",
    "_visibility_field": "0 1 150px",
    "_cartesian_samples_field": "0 1 190px",
    "_parametric_samples_field": "0 1 190px",
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

SCROLL_GUARD_SNIPPETS = (
    ".gu-plot-editor-tab-panel,.gu-plot-editor-wrap-row {overflow-x: hidden !important;}",
    "select[multiple]",
    "max-width: 100% !important;",
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


def test_plot_editor_rows_and_fields_stay_compact_and_wrap_responsively() -> None:
    editor = Figure()._plot_editor

    for row_name in RESPONSIVE_ROW_NAMES:
        row = getattr(editor, row_name)
        assert _layout_value(row, "flex_flow") == "row wrap"
        assert _layout_value(row, "width") == "100%"
        assert _layout_value(row, "min_width") == "0"
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

    assert editor._plot_type_field.children[1] is editor._kind
    assert editor._parametric_parameter_row.children[0].children[1] is editor._parameter_variable
    assert editor._parametric_parameter_row.children[1].children[1] is editor._parameter_min
    assert editor._parametric_parameter_row.children[2].children[1] is editor._parameter_max
    assert editor._field_variable_row.children[0].children[1] is editor._field_x_variable
    assert editor._field_variable_row.children[1].children[1] is editor._field_y_variable
    assert (
        editor._advanced_meta_row.children[2].children[1].children[0]
        is editor._visible_toggle
    )


def test_parametric_labels_follow_the_selected_parameter_symbol() -> None:
    editor = Figure()._plot_editor
    editor.open_for_new(default_kind="parametric")

    editor._parameter_variable.value = "u"

    assert editor._parametric_x_label.value == r"x\left(u\right)"
    assert editor._parametric_y_label.value == r"y\left(u\right)"
    assert editor._parameter_min_label.value == r"u_{\mathrm{min}}"
    assert editor._parameter_max_label.value == r"u_{\mathrm{max}}"
    assert editor._parameter_min.aria_label == "Minimum value for u"
    assert editor._parameter_max.aria_label == "Maximum value for u"

    editor._parameter_variable.value = r"\theta"

    assert editor._parametric_x_label.value == r"x\left(\theta\right)"
    assert editor._parametric_y_label.value == r"y\left(\theta\right)"
    assert editor._parameter_min_label.value == r"\theta_{\mathrm{min}}"
    assert editor._parameter_max_label.value == r"\theta_{\mathrm{max}}"


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


def test_plot_editor_tab_bar_titlebars_and_scroll_css_keep_accessible_modal_chrome() -> None:
    editor = Figure()._plot_editor

    assert editor._title.value == "Create plot"
    assert "<b>" not in editor._title.value.lower()
    assert "gu-modal-title-text" in editor._title._dom_classes
    assert "gu-modal-title-eyebrow" in editor._title_eyebrow._dom_classes
    assert "gu-modal-subtitle" in editor._title_context._dom_classes
    assert "gu-modal-title-text" in editor._error_title._dom_classes

    header = editor._panel.children[0]
    tab_bar = editor._panel.children[1]
    assert "gu-modal-header" in header._dom_classes
    assert "gu-tab-bar" in tab_bar._dom_classes
    assert editor._formula_tab.layout.display == "flex"
    assert editor._advanced_tab.layout.display == "none"

    for class_name in TAB_CLASS_NAMES:
        assert class_name in editor._formula_tab_button._dom_classes
        assert class_name in editor._advanced_tab_button._dom_classes

    assert "mod-selected" in editor._formula_tab_button._dom_classes
    assert "mod-selected" not in editor._advanced_tab_button._dom_classes

    editor._set_tab("advanced")

    assert "mod-selected" not in editor._formula_tab_button._dom_classes
    assert "mod-selected" in editor._advanced_tab_button._dom_classes
    assert editor._formula_tab.layout.display == "none"
    assert editor._advanced_tab.layout.display == "flex"

    css = editor._style.value
    for snippet in SCROLL_GUARD_SNIPPETS:
        assert snippet in css
