from __future__ import annotations

import warnings

import sympy as sp

from gu_toolkit import (
    CodegenOptions,
    Figure,
    get_default_samples,
    get_default_x_range,
    get_default_y_range,
    get_samples,
    set_default_samples,
    set_default_x_range,
    set_default_y_range,
    set_samples,
    set_x_range,
    set_y_range,
)


def test_figure_constructor_accepts_x_range_y_range_without_deprecation() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig = Figure(x_range=(-2, 2), y_range=(-1, 1), samples=300)

    assert not any(
        issubclass(w.category, DeprecationWarning)
        and ("x_range" in str(w.message) or "y_range" in str(w.message))
        for w in caught
    )
    assert fig.x_range == (-2.0, 2.0)
    assert fig.y_range == (-1.0, 1.0)
    assert fig.default_x_range == (-2.0, 2.0)
    assert fig.default_y_range == (-1.0, 1.0)
    assert fig.samples == 300
    assert fig.default_samples == 300


def test_default_range_properties_only_affect_new_views() -> None:
    fig = Figure(x_range=(-6, 6), y_range=(-5, 5))

    fig.default_x_range = (-10, 10)
    fig.default_y_range = (-7, 7)

    assert fig.x_range == (-6.0, 6.0)
    assert fig.y_range == (-5.0, 5.0)

    fig.add_view("alt")

    assert fig.views["alt"].x_range == (-10.0, 10.0)
    assert fig.views["alt"].y_range == (-7.0, 7.0)
    assert fig.views["main"].x_range == (-6.0, 6.0)
    assert fig.views["main"].y_range == (-5.0, 5.0)


def test_module_helpers_split_current_and_default_ranges() -> None:
    fig = Figure(x_range=(-4, 4), y_range=(-3, 3))

    with fig:
        set_default_x_range((-8, 8))
        set_default_y_range((-6, 6))
        set_x_range((-2, 2))
        set_y_range((-1, 1))
        assert get_default_x_range() == (-8.0, 8.0)
        assert get_default_y_range() == (-6.0, 6.0)

    assert fig.x_range == (-2.0, 2.0)
    assert fig.y_range == (-1.0, 1.0)
    assert fig.default_x_range == (-8.0, 8.0)
    assert fig.default_y_range == (-6.0, 6.0)

    fig.add_view("alt")
    assert fig.views["alt"].x_range == (-8.0, 8.0)
    assert fig.views["alt"].y_range == (-6.0, 6.0)


def test_default_samples_only_seed_new_plots() -> None:
    x = sp.symbols("x")
    fig = Figure(samples=400)

    inherited = fig.plot(sp.sin(x), x, id="inherited")
    assert inherited.samples is None
    assert fig.samples == 400
    assert fig.default_samples == 400

    fig.default_samples = 128
    seeded = fig.plot(sp.cos(x), x, id="seeded")

    assert inherited.samples is None
    assert seeded.samples == 128

    fig.samples = 256
    assert fig.samples == 256
    assert fig.default_samples == 128
    assert inherited.samples is None
    assert seeded.samples == 128


def test_module_helpers_set_samples_and_default_samples() -> None:
    x = sp.symbols("x")
    fig = Figure(samples=500)

    with fig:
        set_default_samples(111)
        set_samples(222)
        assert get_default_samples() == 111
        assert get_samples() == 222

    assert fig.default_samples == 111
    assert fig.samples == 222

    seeded = fig.plot(sp.sin(x), x, id="seeded")
    inherited = fig.plot(sp.cos(x), x, id="inherited", samples="figure_default")

    assert seeded.samples == 111
    assert inherited.samples is None


def test_codegen_preserves_default_samples_and_figure_default_plot_requests() -> None:
    x = sp.symbols("x")
    fig = Figure(x_range=(-5, 5), y_range=(-3, 3), samples=256)
    fig.default_x_range = (-9, 9)
    fig.default_y_range = (-8, 8)
    fig.default_samples = 128
    fig.plot(sp.sin(x), x, id="seeded")
    fig.plot(sp.cos(x), x, id="inherit_current", samples="figure_default")

    code = fig.to_code(options=CodegenOptions(interface_style="figure_methods"))

    assert "x_range=(-5.0, 5.0)" in code
    assert "y_range=(-3.0, 3.0)" in code
    assert "samples=256" in code
    assert "fig.default_x_range = (-9.0, 9.0)" in code
    assert "fig.default_y_range = (-8.0, 8.0)" in code
    assert "fig.default_samples = 128" in code
    assert "samples='figure_default'" in code

    ns: dict[str, object] = {}
    exec(code, ns)
    rebuilt = ns["fig"]

    assert rebuilt.samples == 256  # type: ignore[attr-defined]
    assert rebuilt.default_samples == 128  # type: ignore[attr-defined]
    rebuilt_snapshot = rebuilt.snapshot()  # type: ignore[attr-defined]
    assert rebuilt_snapshot.default_x_range == (-9.0, 9.0)
    assert rebuilt_snapshot.default_y_range == (-8.0, 8.0)
    assert rebuilt_snapshot.default_samples == 128
    assert rebuilt_snapshot.plots["seeded"].samples == 128
    assert rebuilt_snapshot.plots["inherit_current"].samples is None
