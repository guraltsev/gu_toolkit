from __future__ import annotations

from gu_toolkit import Figure, FigureLayout


def test_shell_presets_place_legend_in_requested_region() -> None:
    left = FigureLayout(shell="legend_left")
    left_snapshot = left.layout_snapshot()
    assert left_snapshot["shell_preset"] == "legend_left"
    assert left_snapshot["shell_pages"]["figure"]["left_sections"] == ["legend"]
    assert left.left_sidebar_container.children == (left.legend_panel.panel,)
    assert left.sidebar_container.children == (
        left.params_panel.panel,
        left.info_panel.panel,
    )

    bottom = FigureLayout(shell="legend_bottom")
    bottom_snapshot = bottom.layout_snapshot()
    assert bottom_snapshot["shell_preset"] == "legend_bottom"
    assert bottom_snapshot["shell_pages"]["figure"]["bottom_sections"] == ["legend"]
    assert bottom.bottom_section_container.children == (bottom.legend_panel.panel,)
    assert bottom.sidebar_container.children == (
        bottom.params_panel.panel,
        bottom.info_panel.panel,
    )

    hidden = FigureLayout(shell="legend_hidden")
    hidden_snapshot = hidden.layout_snapshot()
    assert hidden_snapshot["shell_preset"] == "legend_hidden"
    assert hidden_snapshot["shell_pages"]["figure"]["right_sections"] == ["parameters", "info"]
    assert hidden.sidebar_container.children == (
        hidden.params_panel.panel,
        hidden.info_panel.panel,
    )
    assert hidden.left_sidebar_container.children == ()
    assert hidden.bottom_section_container.children == ()

    page = FigureLayout(shell="legend_page")
    page_snapshot = page.layout_snapshot()
    assert page_snapshot["shell_preset"] == "legend_page"
    assert page_snapshot["shell_pages"]["figure"]["right_sections"] == ["parameters", "info"]
    assert page_snapshot["shell_pages"]["legend"]["main_sections"] == ["legend"]
    assert page.sidebar_container.children == (
        page.params_panel.panel,
        page.info_panel.panel,
    )
    assert page._shell_pages["legend"].center_box.children == (page.legend_panel.panel,)


def test_shell_pages_are_independent_from_view_selector_visibility() -> None:
    layout = FigureLayout(shell="legend_page")
    layout.ensure_view_page("main", "Main")
    layout.ensure_view_page("alt", "Alt")

    assert layout.view_selector.layout.display == "flex"
    assert layout.shell_page_tabs.layout.display == "none"
    assert layout.view_selector is not layout.shell_page_tabs

    layout.update_sidebar_visibility(has_params=False, has_info=False, has_legend=True)

    assert layout.shell_page_tabs.layout.display == "flex"
    assert layout.layout_snapshot()["visible_shell_page_ids"] == ["figure", "legend"]
    assert tuple(button.description for button in layout.shell_page_bar.children) == (
        "Figure",
        "Legend",
    )

    layout._shell_page_buttons["legend"].click()

    legend_snapshot = layout.layout_snapshot()
    assert legend_snapshot["active_shell_page_id"] == "legend"
    assert layout._shell_pages["figure"].host_box.layout.display == "none"
    assert layout._shell_pages["legend"].host_box.layout.display == "flex"
    assert layout.legend_panel.panel.layout.display == "flex"

    layout.update_sidebar_visibility(has_params=False, has_info=False, has_legend=False)

    hidden_snapshot = layout.layout_snapshot()
    assert hidden_snapshot["visible_shell_page_ids"] == ["figure"]
    assert hidden_snapshot["active_shell_page_id"] == "figure"
    assert layout.shell_page_tabs.layout.display == "none"


def test_stable_shell_slots_expose_page_mount_surfaces() -> None:
    layout = FigureLayout(shell="legend_page")

    assert layout._section_widgets["page_tabs"] is layout.shell_page_tabs
    assert layout._section_widgets["page_content"] is layout.shell_page_content
    assert layout._shell_slots["left_region"] is layout.left_sidebar_container
    assert layout._shell_slots["right_region"] is layout.sidebar_container
    assert layout._shell_slots["bottom_region"] is layout.bottom_section_container


def test_figure_accepts_shell_preset_and_routes_it_to_layout() -> None:
    fig = Figure(shell="legend_bottom")
    snapshot = fig._layout.layout_snapshot()

    assert snapshot["shell_preset"] == "legend_bottom"
    assert snapshot["shell_pages"]["figure"]["bottom_sections"] == ["legend"]
    assert fig._layout.bottom_section_container.children == (fig._layout.legend_panel.panel,)
