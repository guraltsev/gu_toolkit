from __future__ import annotations

import sympy as sp

from gu_toolkit import Figure


def test_plot_lifecycle_updates_legend_and_sidebar_visibility() -> None:
    x = sp.symbols("x")
    fig = Figure()

    assert fig._legend.has_legend is False
    assert fig._layout.sidebar_container.layout.display == "none"

    fig.plot(sp.sin(x), x, id="sin", label="sin(x)")

    assert fig._legend.has_legend is True
    assert fig._layout.legend_header.layout.display == "block"
    assert fig._layout.legend_box.layout.display == "flex"
    assert fig._layout.sidebar_container.layout.display == "flex"
    assert [row.children[1].value for row in fig._layout.legend_box.children] == [
        "sin(x)"
    ]

    fig.plot(sp.sin(x), x, id="sin", label="sin-updated", visible=False)

    row = fig._legend._rows["sin"]
    assert row.label_widget.value == "sin-updated"
    assert row.toggle.value is False


def test_view_switch_and_remove_view_resyncs_legend_rows() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.add_view("alt")

    fig.plot(sp.sin(x), x, id="main_plot", label="Main", view="main")
    fig.plot(sp.cos(x), x, id="alt_plot", label="Alt", view="alt")

    fig.set_active_view("main")
    assert [row.children[1].value for row in fig._layout.legend_box.children] == [
        "Main"
    ]

    fig.set_active_view("alt")
    assert [row.children[1].value for row in fig._layout.legend_box.children] == ["Alt"]

    fig.set_active_view("main")
    fig.remove_view("alt")

    assert fig.plots["alt_plot"].views == ()
    assert [row.children[1].value for row in fig._layout.legend_box.children] == [
        "Main"
    ]
