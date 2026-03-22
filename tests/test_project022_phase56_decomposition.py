"""Regression coverage for Project 022 phase 5 coordinator hardening."""

from __future__ import annotations

from pathlib import Path


def _figure_module_path() -> Path:
    """Return the Figure module path for either src-layout or legacy layout."""
    src_layout = Path("src/gu_toolkit/Figure.py")
    if src_layout.exists():
        return src_layout
    return Path("Figure.py")


def test_phase5_figure_module_does_not_reintroduce_legacy_extracts() -> None:
    source = _figure_module_path().read_text(encoding="utf-8")

    assert "def _normalize_plot_inputs" not in source
    assert "def _coerce_symbol" not in source
    assert "def _rebind_numeric_function_vars" not in source


def test_phase5_render_batching_extracts_keep_figure_module_below_baseline() -> None:
    line_count = len(_figure_module_path().read_text(encoding="utf-8").splitlines())
    scheduler_module = Path("src/gu_toolkit/figure_render_scheduler.py")

    # The original monolith was ~2,098 lines. The render scheduler is now
    # extracted into its own focused module, so the coordinator should remain
    # materially below the historical baseline even as new features land.
    assert scheduler_module.exists()
    assert line_count < 2000
