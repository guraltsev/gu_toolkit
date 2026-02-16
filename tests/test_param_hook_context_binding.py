from __future__ import annotations

import sympy as sp

from gu_toolkit import Figure, params


def test_param_change_hooks_run_inside_triggering_figure_context() -> None:
    x, a, c = sp.symbols("x a c")
    fig1 = Figure(x_range=(-6, 6), y_range=(-3, 3))
    fig2 = Figure(x_range=(-4, 4), y_range=(-2, 2))

    with fig1:
        fig1.plot(x, a * sp.sin(x), parameters=[a], id="a_sin")
        params[a].value = 1

    with fig2:
        fig2.plot(x, c * sp.cos(x), parameters=[c], id="c_cos")
        params[c].value = 1

    log: list[tuple[str, float]] = []

    def hook_fig1(event):
        log.append(("fig1", float(params[a].value), float(event.new)))

    def hook_fig2(event):
        log.append(("fig2", float(params[c].value), float(event.new)))

    fig1.add_param_change_hook(hook_fig1, run_now=False)
    fig2.add_param_change_hook(hook_fig2, run_now=False)

    fig1.parameter(a).value = 2
    fig2.parameter(c).value = 3

    assert log[0] == ("fig1", 2.0, 2.0)
    assert log[1] == ("fig2", 3.0, 3.0)
