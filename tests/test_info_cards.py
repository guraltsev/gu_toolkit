from __future__ import annotations

import sympy as sp
from gu_toolkit import Figure, info
import gu_toolkit.figure_info as figure_info_module


class _ImmediateDebouncer:
    def __init__(self, callback, *, execute_every_ms: int, drop_overflow: bool = True):
        self._callback = callback

    def __call__(self, *args, **kwargs):
        self._callback(*args, **kwargs)


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
        fig.render(reason="manual")
        fig.render(reason="relayout")
        fig.render(reason="param_change", trigger={"k": "v"})

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
