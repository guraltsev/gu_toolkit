from __future__ import annotations

from gu_toolkit import FigureLayout


def test_sidebar_contains_legend_section_before_parameters_section() -> None:
    layout = FigureLayout()

    assert layout.sidebar_container.children == (
        layout.legend_header,
        layout.legend_box,
        layout.params_header,
        layout.params_box,
        layout.info_header,
        layout.info_box,
    )


def test_update_sidebar_visibility_handles_legend_only() -> None:
    layout = FigureLayout()

    layout.update_sidebar_visibility(has_params=False, has_info=False, has_legend=True)

    assert layout.params_header.layout.display == "none"
    assert layout.params_box.layout.display == "none"
    assert layout.info_header.layout.display == "none"
    assert layout.info_box.layout.display == "none"
    assert layout.legend_header.layout.display == "block"
    assert layout.legend_box.layout.display == "flex"
    assert layout.sidebar_container.layout.display == "flex"


def test_update_sidebar_visibility_hides_sidebar_when_all_sections_empty() -> None:
    layout = FigureLayout()

    layout.update_sidebar_visibility(has_params=False, has_info=False, has_legend=False)

    assert layout.sidebar_container.layout.display == "none"


def test_layout_adds_css_classes_for_box_sizing_and_scroll_control() -> None:
    layout = FigureLayout()

    assert "gu-figure-root" in layout.root_widget._dom_classes
    assert "gu-figure-sidebar" in layout.sidebar_container._dom_classes
    assert "gu-figure-panel-box" in layout.params_box._dom_classes
    assert "gu-figure-print-output" in layout.print_output._dom_classes
    assert ".gu-figure-sidebar" in layout._style_widget.value


def test_layout_defaults_hide_horizontal_scrollbars_in_sidebar_and_output() -> None:
    layout = FigureLayout()

    assert layout.sidebar_container.layout.overflow_x == "hidden"
    assert layout.sidebar_container.layout.overflow_y == "auto"
    assert layout.info_box.layout.overflow_x == "hidden"
    assert layout.params_box.layout.overflow_x == "hidden"
    assert layout.legend_box.layout.overflow_x == "hidden"
    assert layout.print_output.layout.overflow_x == "hidden"
    assert layout.print_output.layout.overflow_y == "auto"
    assert ".gu-figure-print-output .output_scroll" in layout._style_widget.value
