from __future__ import annotations

import sympy as sp

from gu_toolkit import Figure, sympy_to_code


def _build_exportable_figure(*, include_dynamic_info: bool) -> Figure:
    x, a, b = sp.symbols("x a b")
    fig = Figure(x_range=(-5, 5), y_range=(-3, 3), sampling_points=256)
    fig.title = "Snapshot demo"
    fig.parameter(a, min=-2, max=2, value=0.75, step=0.05)
    fig.parameter(b, min=-1, max=1, value=-0.25, step=0.05)
    fig.plot(
        x,
        a * sp.sin(x) + b,
        parameters=[a, b],
        id="model",
        label="model(a,b)",
        visible="legendonly",
        x_domain=(-2, 2),
        sampling_points=64,
        color="purple",
        thickness=2.5,
        dash="dash",
        opacity=0.6,
    )
    if include_dynamic_info:
        fig.info(["<b>Static</b>", lambda _fig, ctx: f"<i>{ctx.reason}</i>"], id="status")
    else:
        fig.info("<b>Static only</b>", id="status")
    return fig


def test_snapshot_captures_parameters_plots_and_info_cards() -> None:
    fig = _build_exportable_figure(include_dynamic_info=True)
    x, a, b = sp.symbols("x a b")

    snap = fig.snapshot()
    assert snap.x_range == (-5.0, 5.0)
    assert snap.y_range == (-3.0, 3.0)
    assert snap.sampling_points == 256
    assert snap.title == "Snapshot demo"

    assert list(snap.parameters) == [a, b]
    assert snap.parameters[a]["value"] == 0.75
    assert snap.parameters[a]["min"] == -2.0
    assert snap.parameters[b]["max"] == 1.0

    plot = snap.plots["model"]
    assert plot.var == x
    assert plot.func == a * sp.sin(x) + b
    assert plot.parameters == (a, b)
    assert plot.visible == "legendonly"
    assert plot.x_domain == (-2.0, 2.0)
    assert plot.sampling_points == 64
    assert plot.color == "purple"
    assert plot.thickness == 2.5
    assert plot.dash == "dash"
    assert plot.opacity == 0.6

    assert len(snap.info_cards) == 1
    assert snap.info_cards[0].id == "status"
    assert snap.info_cards[0].segments == ("<b>Static</b>", "<dynamic>")


def test_to_code_emits_reconstruction_script_with_dynamic_info_comment() -> None:
    fig = _build_exportable_figure(include_dynamic_info=True)

    code = fig.to_code()

    assert "import sympy as sp" in code
    assert "from gu_toolkit import Figure" in code
    assert "fig = Figure(x_range=(-5.0, 5.0), y_range=(-3.0, 3.0), sampling_points=256)" in code
    assert "fig.parameter(a, value=0.75, min=-2.0, max=2.0, step=0.05)" in code
    assert "fig.parameter(b, value=-0.25, min=-1.0, max=1.0, step=0.05)" in code
    assert "id='model'" in code
    assert "# Info card 'status' contains dynamic segments that cannot be serialized." in code


def test_generated_code_round_trips_for_static_exportable_content() -> None:
    fig = _build_exportable_figure(include_dynamic_info=False)

    original = fig.snapshot()
    ns: dict[str, object] = {}
    exec(fig.to_code(), ns)
    rebuilt = ns["fig"]

    rebuilt_snapshot = rebuilt.snapshot()  # type: ignore[attr-defined]
    assert rebuilt_snapshot.x_range == original.x_range
    assert rebuilt_snapshot.y_range == original.y_range
    assert rebuilt_snapshot.sampling_points == original.sampling_points
    assert rebuilt_snapshot.title == original.title
    assert rebuilt_snapshot.parameters == original.parameters

    rebuilt_plot = rebuilt_snapshot.plots["model"]
    original_plot = original.plots["model"]
    assert rebuilt_plot.func == original_plot.func
    assert rebuilt_plot.parameters == original_plot.parameters
    assert rebuilt_plot.visible == original_plot.visible
    assert rebuilt_plot.x_domain == original_plot.x_domain
    assert rebuilt_plot.color == original_plot.color

    assert rebuilt_snapshot.info_cards[0].segments == ("<b>Static only</b>",)


def test_sympy_to_code_prefixes_sympy_functions_and_constants() -> None:
    x = sp.Symbol("x")
    expr = sp.pi + sp.sqrt(x) + sp.Abs(sp.sin(x))

    rendered = sympy_to_code(expr)

    assert "sp.pi" in rendered
    assert "sp.sqrt(x)" in rendered
    assert "sp.Abs(sp.sin(x))" in rendered
