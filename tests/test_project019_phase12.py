import sympy as sp

from gu_toolkit import Figure


def test_default_view_registry_and_active_range_delegation() -> None:
    fig = Figure(x_range=(-6, 6), y_range=(-5, 5))
    assert fig.active_view_id == "main"
    assert tuple(fig.views.keys()) == ("main",)
    assert fig.x_range == (-6.0, 6.0)
    assert fig.y_range == (-5.0, 5.0)


def test_add_view_and_switch_preserves_independent_defaults() -> None:
    fig = Figure(x_range=(-6, 6), y_range=(-5, 5))
    fig.add_view("alt", x_range=(-2, 2), y_range=(-1, 1))
    fig.set_active_view("alt")
    assert fig.x_range == (-2.0, 2.0)
    assert fig.y_range == (-1.0, 1.0)
    fig.set_active_view("main")
    assert fig.x_range == (-6.0, 6.0)
    assert fig.y_range == (-5.0, 5.0)


def test_plot_membership_helpers_add_and_remove_views() -> None:
    x = sp.symbols("x")
    fig = Figure()
    fig.add_view("alt")
    p = fig.plot(sp.sin(x), x, id="sin")
    assert p.views == ("main",)
    p.add_to_view("alt")
    assert p.views == ("alt", "main")
    p.remove_views("main")
    assert p.views == ("alt",)


def test_parameter_change_marks_inactive_view_stale_until_activation() -> None:
    x, a = sp.symbols("x a")
    fig = Figure()
    fig.add_view("alt")
    fig.plot(a * sp.sin(x), x, parameters=[a], id="sin", view=("main", "alt"))

    fig.parameter(a, value=1.0)
    fig.set_active_view("main")
    fig.parameter(a).value = 2.0

    assert fig.views["alt"].is_stale is True
    fig.set_active_view("alt")
    assert fig.views["alt"].is_stale is False


def test_layout_shows_tabs_only_for_multi_view() -> None:
    fig = Figure()
    assert fig._layout.view_tabs.layout.display == "none"
    fig.add_view("alt")
    assert fig._layout.view_tabs.layout.display == "flex"
    assert fig._layout.view_tabs.get_title(0) == "main"
    assert fig._layout.view_tabs.get_title(1) == "alt"


def test_set_active_view_does_not_rebuild_tab_children() -> None:
    fig = Figure()
    fig.add_view("frequency")

    first_children = fig._layout.view_tabs.children
    fig.set_active_view("frequency")

    assert fig._layout.view_tabs.children is first_children
    assert fig.active_view_id == "frequency"
