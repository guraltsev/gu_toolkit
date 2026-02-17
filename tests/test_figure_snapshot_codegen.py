from __future__ import annotations

import pytest
import sympy as sp

from gu_toolkit import CodegenOptions, Figure, sympy_to_code


def _build_exportable_figure(*, include_dynamic_info: bool) -> Figure:
    x, a, b = sp.symbols("x a b")
    fig = Figure(x_range=(-5, 5), y_range=(-3, 3), sampling_points=256)
    fig.title = "Snapshot demo"
    fig.parameter(a, min=-2, max=2, value=0.75, step=0.05)
    fig.parameter(b, min=-1, max=1, value=-0.25, step=0.05)
    fig.plot(
        a * sp.sin(x) + b,
        x,
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
        fig.info(
            ["<b>Static</b>", lambda _fig, ctx: f"<i>{ctx.reason}</i>"], id="status"
        )
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


def test_to_code_default_is_context_manager_with_dynamic_info_comment_block() -> None:
    fig = _build_exportable_figure(include_dynamic_info=True)

    code = fig.to_code()

    assert "import sympy as sp" in code
    assert "from gu_toolkit import Figure, parameter, plot, info, set_title" in code
    assert "from IPython.display import display" in code
    assert "fig = Figure(" in code
    assert "display(fig)" in code
    assert "with fig:" in code
    assert "set_title('Snapshot demo')" in code
    assert "parameter(a, value=0.75, min=-2.0, max=2.0, step=0.05)" in code
    assert "plot(" in code
    assert "# info('<b>Static</b>', id='status')" in code
    assert "# print(inspect.getsource(my_dynamic_func))" in code


def test_to_code_supports_figure_methods_style_and_round_trip() -> None:
    fig = _build_exportable_figure(include_dynamic_info=False)

    original = fig.snapshot()
    ns: dict[str, object] = {}
    exec(fig.to_code(options=CodegenOptions(interface_style="figure_methods")), ns)
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


def test_to_code_can_disable_imports_symbols_and_dynamic_comment_blocks() -> None:
    fig = _build_exportable_figure(include_dynamic_info=True)

    code = fig.to_code(
        options=CodegenOptions(
            include_imports=False,
            include_symbol_definitions=False,
            include_dynamic_info_as_commented_blocks=False,
        )
    )

    assert "import sympy as sp" not in code
    assert "sp.symbols(" not in code
    assert "# dynamic info omitted" in code


def test_sympy_to_code_prefixes_sympy_functions_and_constants() -> None:
    x = sp.Symbol("x")
    expr = sp.pi + sp.sqrt(x) + sp.Abs(sp.sin(x))

    rendered = sympy_to_code(expr)

    assert "sp.pi" in rendered
    assert "sp.sqrt(x)" in rendered
    assert "sp.Abs(sp.sin(x))" in rendered


def test_code_property_is_read_only_and_matches_to_code() -> None:
    fig = _build_exportable_figure(include_dynamic_info=False)

    assert fig.code == fig.to_code()
    with pytest.raises(AttributeError):
        fig.code = "override"  # type: ignore[misc]


def test_get_code_passes_codegen_options() -> None:
    fig = _build_exportable_figure(include_dynamic_info=False)

    code = fig.get_code(CodegenOptions(interface_style="figure_methods"))

    assert "fig.parameter(" in code
    assert "with fig:" not in code


def test_codegen_options_reject_invalid_interface_style() -> None:
    with pytest.raises(ValueError, match="interface_style"):
        CodegenOptions(interface_style="invalid")  # type: ignore[arg-type]
