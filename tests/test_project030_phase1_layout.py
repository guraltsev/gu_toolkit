from __future__ import annotations

from gu_toolkit import FigureLayout


def test_sidebar_contains_shared_section_panels_in_legend_params_info_order() -> None:
    layout = FigureLayout()

    assert layout.sidebar_container.children == (
        layout.legend_panel.panel,
        layout.params_panel.panel,
        layout.info_panel.panel,
    )


def test_update_sidebar_visibility_handles_legend_only_via_panel_surfaces() -> None:
    layout = FigureLayout()

    layout.update_sidebar_visibility(has_params=False, has_info=False, has_legend=True)

    assert layout.params_header.layout.display == "none"
    assert layout.params_panel.panel.layout.display == "none"
    assert layout.info_header.layout.display == "none"
    assert layout.info_panel.panel.layout.display == "none"
    assert layout.legend_header.layout.display == "none"
    assert layout.legend_panel.panel.layout.display == "flex"
    assert layout.legend_box.layout.display == "flex"
    assert layout.sidebar_container.layout.display == "flex"


def test_update_sidebar_visibility_hides_sidebar_when_all_sections_empty() -> None:
    layout = FigureLayout()

    layout.update_sidebar_visibility(has_params=False, has_info=False, has_legend=False)

    assert layout.sidebar_container.layout.display == "none"
    assert layout.legend_panel.panel.layout.display == "none"
    assert layout.params_panel.panel.layout.display == "none"
    assert layout.info_panel.panel.layout.display == "none"


def test_layout_adds_shared_panel_classes_and_theme_root() -> None:
    layout = FigureLayout()

    assert "gu-theme-root" in layout.root_widget._dom_classes
    assert "gu-figure-root" in layout.root_widget._dom_classes
    assert "gu-figure-sidebar" in layout.sidebar_container._dom_classes
    assert "gu-panel" in layout.params_panel.panel._dom_classes
    assert "gu-panel-variant-toolbar" in layout.legend_panel.panel._dom_classes
    assert "gu-panel-variant-minimal" in layout.params_panel.panel._dom_classes
    assert "gu-panel-variant-minimal" in layout.info_panel.panel._dom_classes
    assert "gu-panel-variant-minimal" in layout.print_panel._dom_classes
    assert "gu-panel-body" in layout.params_box._dom_classes
    assert "gu-figure-output-panel" in layout.print_panel._dom_classes
    assert "gu-figure-output-widget" in layout.print_output._dom_classes
    assert ".gu-figure-sidebar" in layout._style_widget.value
    assert ".gu-panel" in layout._style_widget.value


def test_layout_defaults_hide_horizontal_scrollbars_in_sidebar_and_output() -> None:
    layout = FigureLayout()

    assert layout.sidebar_container.layout.overflow_x == "hidden"
    assert layout.sidebar_container.layout.overflow_y == "auto"
    assert layout.info_box.layout.overflow_x == "hidden"
    assert layout.info_box.layout.overflow_y == "visible"
    assert layout.params_box.layout.overflow_x == "hidden"
    assert layout.params_box.layout.overflow_y == "visible"
    assert layout.legend_box.layout.overflow_x == "hidden"
    assert layout.legend_box.layout.overflow_y == "visible"
    assert layout.print_panel.layout.overflow_x == "hidden"
    assert layout.print_panel.layout.overflow_y == "visible"
    assert layout.output_panel.body.layout.overflow_y == "auto"
    assert layout.print_output.layout.margin == "0px"
    assert layout.print_output.layout.padding == "0px"
    assert ".gu-figure-output-body :is(.jupyter-widgets-output-area" in layout._style_widget.value
