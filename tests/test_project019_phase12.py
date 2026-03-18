import sympy as sp

from gu_toolkit import Figure


def test_default_view_registry_and_active_range_delegation() -> None:
    fig = Figure(default_x_range=(-6, 6), default_y_range=(-5, 5))
    assert fig.views.current_id == "main"
    assert tuple(fig.views.keys()) == ("main",)
    assert fig.x_range == (-6.0, 6.0)
    assert fig.y_range == (-5.0, 5.0)


def test_add_view_and_switch_preserves_independent_defaults() -> None:
    fig = Figure(default_x_range=(-6, 6), default_y_range=(-5, 5))
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
    fig.parameter(a)
    fig.plot(a * sp.sin(x), x, id="sin", view=("main", "alt"))

    fig.parameter(a, value=1.0)
    fig.set_active_view("main")
    fig.parameter(a).value = 2.0

    assert fig.views["alt"].is_stale is True
    fig.set_active_view("alt")
    assert fig.views["alt"].is_stale is False


def test_layout_shows_view_selector_only_for_multi_view() -> None:
    fig = Figure()
    assert fig._layout.view_selector.layout.display == "none"
    fig.add_view("alt")
    assert fig._layout.view_selector.layout.display == "flex"
    options = tuple(fig._layout.view_selector.options)
    assert tuple(label for label, _ in options) == ("main", "alt")
    assert tuple(value for _, value in options) == ("main", "alt")


def test_set_active_view_does_not_rebuild_stage_children() -> None:
    fig = Figure()
    fig.add_view("frequency")

    first_children = fig._layout.view_stage.children
    fig.set_active_view("frequency")

    assert fig._layout.view_stage.children is first_children
    assert fig.views.current_id == "frequency"
