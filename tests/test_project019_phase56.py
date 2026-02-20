from __future__ import annotations

import sympy as sp

from gu_toolkit import Figure, info


def test_view_context_manager_scopes_plot_and_restores_active_view() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.add_view("alt")

    with fig.view("alt"):
        fig.plot(sp.cos(x), x, id="cos_alt")
        assert fig.active_view_id == "alt"

    assert fig.active_view_id == "main"
    assert fig.plots["cos_alt"].views == ("alt",)


def test_info_cards_support_shared_and_view_scoped_visibility() -> None:
    fig = Figure()
    fig.add_view("alt")

    fig.info("shared", id="shared")
    fig.info("alt only", id="alt", view="alt")

    assert fig.info_output["shared"].layout.display == "block"
    assert fig.info_output["alt"].layout.display == "none"

    fig.set_active_view("alt")
    assert fig.info_output["shared"].layout.display == "block"
    assert fig.info_output["alt"].layout.display == "block"


def test_module_info_helper_accepts_view_argument() -> None:
    fig = Figure()
    fig.add_view("alt")

    with fig:
        info("from module", id="module-alt", view="alt")

    assert fig.info_output["module-alt"].layout.display == "none"
    fig.set_active_view("alt")
    assert fig.info_output["module-alt"].layout.display == "block"


def test_snapshot_and_codegen_capture_multi_view_state() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.add_view("alt", x_range=(-2, 2), y_range=(-1, 1), x_label="time", y_label="amp")
    fig.plot(sp.sin(x), x, id="wave", view=("main", "alt"))
    fig.info("shared", id="shared")
    fig.info("alt only", id="alt", view="alt")
    fig.set_active_view("alt")

    snap = fig.snapshot()
    assert snap.active_view_id == "alt"
    assert tuple(v.id for v in snap.views) == ("main", "alt")
    assert snap.plots["wave"].views == ("alt", "main")
    assert any(card.id == "alt" and card.view_id == "alt" for card in snap.info_cards)

    code = fig.to_code()
    assert "fig.add_view('alt'" in code
    assert "view=('alt', 'main')" in code or "view=('main', 'alt')" in code
    assert "info('alt only', id='alt', view='alt')" in code


def test_view_scoped_plot_uses_isolated_figure_widgets() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.add_view("frequency")

    fig.plot(sp.sin(x), x, id="main-wave", view="main")
    with fig.view("frequency"):
        fig.plot(sp.cos(x), x, id="freq-only", view="frequency")

    main_widget = fig.figure_widget_for("main")
    freq_widget = fig.figure_widget_for("frequency")

    assert len(main_widget.data) == 1
    assert len(freq_widget.data) == 1
    assert main_widget.data[0].name == "main-wave"
    assert freq_widget.data[0].name == "freq-only"


def test_multi_view_layout_embeds_plot_widget_inside_active_tab() -> None:
    fig = Figure()
    fig.add_view("frequency")

    active_idx = fig._layout.view_tabs.selected_index
    assert active_idx is not None
    assert fig._layout.plot_container.layout.display == "none"
    assert fig._layout.view_tabs.children[active_idx].children[0] is fig.pane.widget


def test_view_scoped_plots_use_per_view_traces_without_extra_handles() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.add_view("frequency")

    fig.plot(sp.sin(x), x, id="main-only", view="main")
    fig.plot(sp.cos(x), x, id="freq-only", view="frequency")

    assert len(fig.figure_widget_for("main").data) == 1
    assert len(fig.figure_widget_for("frequency").data) == 1
    assert fig.plots["main-only"].views == ("main",)
    assert fig.plots["freq-only"].views == ("frequency",)

    fig.set_active_view("main")
    visible_names = [
        trace.name for trace in fig.figure_widget.data if trace.visible is True
    ]
    assert visible_names == ["main-only"]

    fig.set_active_view("frequency")
    visible_names = [
        trace.name for trace in fig.figure_widget.data if trace.visible is True
    ]
    assert visible_names == ["freq-only"]
