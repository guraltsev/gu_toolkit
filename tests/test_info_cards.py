from __future__ import annotations

import sympy as sp

import gu_toolkit
import gu_toolkit.figure_info as figure_info_module
from gu_toolkit import Figure, info


class _ImmediateDebouncer:
    def __init__(self, callback, *, execute_every_ms: int, drop_overflow: bool = True):
        self._callback = callback

    def __call__(self, *args, **kwargs):
        self._callback(*args, **kwargs)


def test_raw_info_output_activates_sidebar_visibility() -> None:
    fig = Figure()

    out = fig.info_manager.get_output("summary", height="90px")

    assert fig.info_manager.has_info is True
    assert fig._layout.sidebar_container.layout.display == "flex"
    assert fig._layout.info_header.layout.display == "block"
    assert fig._layout.info_box.layout.display == "flex"
    assert fig._layout.params_panel.panel.layout.display == "none"
    assert out in fig._layout.info_box.children
    assert getattr(out, "id", None) == "summary"
    assert out.layout.height == "90px"
    assert out.layout.width == "100%"
    assert out.layout.min_width == "0"
    assert out.layout.overflow_x == "hidden"
    assert out.layout.overflow_y == "auto"


def test_raw_info_output_requests_reflow_when_sidebar_appears() -> None:
    fig = Figure()

    fig.info_manager.get_output("summary")

    assert fig.pane.driver.pending_reason == "sidebar_visibility"
    assert fig.pane.driver.pending_request_id


def test_info_auto_id_and_replacement() -> None:
    original = figure_info_module.QueuedDebouncer
    try:
        figure_info_module.QueuedDebouncer = _ImmediateDebouncer

        fig = Figure()
        fig.info("hello")
        fig.info("world")

        assert "info0" in fig.info_output
        assert "info1" in fig.info_output

        first_out = fig.info_output["info0"]
        fig.info("updated", id="info0")
        assert fig.info_output["info0"] is first_out
    finally:
        figure_info_module.QueuedDebouncer = original


def test_info_dynamic_updates_on_all_render_reasons() -> None:
    original = figure_info_module.QueuedDebouncer
    try:
        figure_info_module.QueuedDebouncer = _ImmediateDebouncer

        fig = Figure()
        x, a = sp.symbols("x a")
        fig.parameter(a, value=1)

        seen = []

        def _dynamic(_fig, ctx):
            seen.append(ctx.reason)
            return f"<code>{ctx.reason}</code>"

        fig.info(["static", _dynamic], id="reasons")
        fig.render(reason="manual", force=True)
        fig.render(reason="relayout", force=True)
        fig.render(reason="param_change", trigger={"k": "v"}, force=True)

        assert seen[:4] == ["manual", "manual", "relayout", "param_change"]

        card = fig._info._simple_cards["reasons"]
        dynamic_seg = card.segments[1]
        assert "param_change" in dynamic_seg.widget.value
    finally:
        figure_info_module.QueuedDebouncer = original


def test_info_error_payload_is_bounded_and_escaped() -> None:
    original = figure_info_module.QueuedDebouncer
    try:
        figure_info_module.QueuedDebouncer = _ImmediateDebouncer

        fig = Figure()

        def _boom(_fig, _ctx):
            raise RuntimeError("<b>bad</b>")

        fig.info(_boom, id="err")
        card = fig._info._simple_cards["err"]
        dynamic_seg = card.segments[0]

        assert "<pre" in dynamic_seg.widget.value
        assert "&lt;b&gt;bad&lt;/b&gt;" in dynamic_seg.widget.value
        assert "max-height: 12em" in dynamic_seg.widget.value
        assert "overflow-x:hidden" in dynamic_seg.widget.value
        assert "overflow-wrap:anywhere" in dynamic_seg.widget.value
    finally:
        figure_info_module.QueuedDebouncer = original


def test_simple_info_cards_keep_width_constrained_to_sidebar() -> None:
    original = figure_info_module.QueuedDebouncer
    try:
        figure_info_module.QueuedDebouncer = _ImmediateDebouncer

        fig = Figure()
        fig.info("hello", id="summary")

        card = fig._info._simple_cards["summary"]
        assert card.container.layout.width == "100%"
        assert card.container.layout.min_width == "0"
        assert all(seg.widget.layout.width == "100%" for seg in card.segments)
        assert all(seg.widget.layout.min_width == "0" for seg in card.segments)
    finally:
        figure_info_module.QueuedDebouncer = original


def test_module_level_info_helper_targets_current_figure() -> None:
    original = figure_info_module.QueuedDebouncer
    try:
        figure_info_module.QueuedDebouncer = _ImmediateDebouncer

        fig = Figure()
        with fig:
            info("from module", id="module-card")

        assert "module-card" in fig.info_output
    finally:
        figure_info_module.QueuedDebouncer = original


def test_legacy_info_helpers_removed_from_figure_api() -> None:
    fig = Figure()
    assert not hasattr(fig, "get_info_output")
    assert not hasattr(fig, "add_info_component")


def test_legacy_info_helpers_removed_from_module_api() -> None:
    assert not hasattr(gu_toolkit, "get_info_output")
    assert not hasattr(gu_toolkit, "add_info_component")
