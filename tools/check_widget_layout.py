from __future__ import annotations

import sys
from pathlib import Path


RESPONSIVE_ROW_NAMES = (
    "_plot_type_row",
    "_cartesian_variable_row",
    "_parametric_parameter_row",
    "_field_variable_row",
    "_advanced_meta_row",
    "_cartesian_samples_row",
    "_parametric_samples_row",
    "_field_grid_row",
)

HOSTED_PANELS = (
    ("plot editor panel", "_panel"),
    ("plot editor error panel", "_error_panel"),
)

SOURCE_FILE_PATHS = (
    "src/gu_toolkit/figure_plot_editor.py",
    "src/gu_toolkit/figure_legend.py",
)

SCROLL_GUARD_SNIPPETS = (
    ".gu-plot-editor-tab-panel,.gu-plot-editor-wrap-row {overflow-x: hidden !important;}",
    "select[multiple]",
    "overflow-x: hidden !important;",
)

BANNED_VIEWPORT_TOKENS = ("100vw", "100vh", "calc(100vw", "calc(100vh")

EXPECTED_PANEL_WIDTH_TOKENS = {
    "width": "100%",
    "min_width": "100%",
    "max_width": "100%",
}


def _layout_value(widget: object, attr_name: str) -> str:
    layout = getattr(widget, "layout", None)
    if layout is None:
        return ""
    try:
        value = getattr(layout, attr_name)
    except Exception:
        return ""
    return str(value or "")


def _require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _check_hosted_panel(name: str, panel: object, failures: list[str]) -> None:
    for layout_attr, required_token in EXPECTED_PANEL_WIDTH_TOKENS.items():
        value = _layout_value(panel, layout_attr)
        _require(bool(value), f"{name}: missing layout.{layout_attr}", failures)
        _require(
            required_token in value,
            (
                f"{name}: layout.{layout_attr} must stay container-relative "
                f"(expected '{required_token}' in {value!r})"
            ),
            failures,
        )
        _require(
            "100vw" not in value and "100vh" not in value,
            f"{name}: layout.{layout_attr} must not use viewport units ({value!r})",
            failures,
        )


def _check_editor_runtime(failures: list[str]) -> None:
    from gu_toolkit import Figure

    figure = Figure()
    editor = figure._plot_editor
    legend = figure._legend

    for name, attr_name in HOSTED_PANELS:
        _check_hosted_panel(name, getattr(editor, attr_name), failures)

    _check_hosted_panel("legend style dialog panel", legend._dialog_panel, failures)

    for overlay_name, overlay in (
        ("plot editor overlay", editor._modal),
        ("plot editor error overlay", editor._error_modal),
        ("legend style dialog overlay", legend._dialog_modal),
    ):
        _require(
            _layout_value(overlay, "width") == "100%",
            f"{overlay_name}: hosted overlays must stay width=100%",
            failures,
        )
        _require(
            _layout_value(overlay, "height") == "100%",
            f"{overlay_name}: hosted overlays must stay height=100%",
            failures,
        )

    for row_name in RESPONSIVE_ROW_NAMES:
        row = getattr(editor, row_name)
        _require(
            _layout_value(row, "flex_flow") == "row wrap",
            f"{row_name}: responsive rows must wrap instead of forcing overflow",
            failures,
        )
        _require(
            _layout_value(row, "width") == "100%",
            f"{row_name}: rows must keep width=100%",
            failures,
        )
        _require(
            _layout_value(row, "min_width") == "0",
            f"{row_name}: rows must keep min_width=0 to allow shrinking",
            failures,
        )
        for index, child in enumerate(getattr(row, "children", ())):
            _require(
                _layout_value(child, "min_width") == "0",
                f"{row_name}[{index}]: child wrappers must keep min_width=0",
                failures,
            )
            _require(
                _layout_value(child, "max_width") == "100%",
                f"{row_name}[{index}]: child wrappers must keep max_width=100%",
                failures,
            )

    css = editor._style.value
    for snippet in SCROLL_GUARD_SNIPPETS:
        _require(
            snippet in css,
            (
                "plot editor shared style is missing required scroll guard "
                f"snippet: {snippet!r}"
            ),
            failures,
        )


def _check_source_guardrails(repo_root: Path, failures: list[str]) -> None:
    for relative_path in SOURCE_FILE_PATHS:
        source_file = repo_root / relative_path
        source = source_file.read_text()
        _require(
            "hosted_modal_dimensions(" in source,
            (
                f"{source_file}: hosted dialogs must derive widths from "
                "hosted_modal_dimensions()"
            ),
            failures,
        )
        for token in BANNED_VIEWPORT_TOKENS:
            _require(
                token not in source,
                (
                    f"{source_file}: found banned viewport-sized token {token!r}; "
                    "use hosted_modal_dimensions() instead"
                ),
                failures,
            )


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    failures: list[str] = []
    _check_source_guardrails(repo_root, failures)
    _check_editor_runtime(failures)

    if failures:
        print("Widget layout guardrails failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print("Widget layout guardrails passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
