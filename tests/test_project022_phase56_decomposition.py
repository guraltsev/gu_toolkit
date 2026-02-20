"""Regression coverage for Project 022 phase 5 coordinator hardening."""

from __future__ import annotations

from pathlib import Path

import sympy as sp

from gu_toolkit import Figure
import importlib

figure_module = importlib.import_module("gu_toolkit.Figure")


def test_phase5_plot_uses_shared_style_alias_resolver(monkeypatch) -> None:
    x = sp.symbols("x")
    fig = Figure()
    called = {"value": False}

    def _fake_resolver(**kwargs):
        called["value"] = True
        assert kwargs["width"] == 3
        assert kwargs["thickness"] is None
        return 3, None

    monkeypatch.setattr(figure_module, "resolve_style_aliases", _fake_resolver)
    fig.plot(sp.sin(x), x, id="wave", width=3)

    assert called["value"] is True


def test_phase5_figure_module_does_not_reintroduce_legacy_extracts() -> None:
    source = Path("Figure.py").read_text(encoding="utf-8")

    assert "def _normalize_plot_inputs" not in source
    assert "def _coerce_symbol" not in source
    assert "def _rebind_numeric_function_vars" not in source
    assert "def _resolve_style_aliases" not in source


def test_phase5_figure_line_count_is_materially_reduced_from_baseline() -> None:
    line_count = len(Path("Figure.py").read_text(encoding="utf-8").splitlines())
    # Project 022 baseline was ~2,098 lines before decomposition phases.
    assert line_count < 1700
