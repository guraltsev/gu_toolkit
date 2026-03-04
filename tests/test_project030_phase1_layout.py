from __future__ import annotations

from gu_toolkit import FigureLayout


def test_sidebar_contains_params_and_info_sections_only() -> None:
    layout = FigureLayout()

    assert layout.sidebar_container.children == (
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
    assert layout.legend_container.layout.display == "flex"
    assert layout.sidebar_container.layout.display == "none"


def test_update_sidebar_visibility_hides_sidebar_when_all_sections_empty() -> None:
    layout = FigureLayout()

    layout.update_sidebar_visibility(has_params=False, has_info=False, has_legend=False)

    assert layout.legend_container.layout.display == "none"
    assert layout.sidebar_container.layout.display == "none"


def test_legend_column_is_capped_and_immediately_right_of_plot() -> None:
    layout = FigureLayout()

    assert layout.plot_and_legend_wrapper.layout.flex_flow == "row nowrap"
    assert (
        layout.legend_container.layout.width
        == "min(calc(28px + 20ch + 22px), 10%)"
    )
    assert (
        layout.legend_container.layout.flex
        == "0 1 min(calc(28px + 20ch + 22px), 10%)"
    )
    assert layout.legend_container.layout.max_width == "10%"
