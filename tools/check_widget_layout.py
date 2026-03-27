from __future__ import annotations

import sys
from pathlib import Path


CSS_RESOURCE_FILES = (
    "tokens.css",
    "controls.css",
    "surfaces.css",
    "figure_layout.css",
    "legend.css",
    "plot_editor.css",
    "slider.css",
)

HOSTED_DIALOG_SOURCES = (
    "src/gu_toolkit/figure_plot_editor.py",
    "src/gu_toolkit/figure_legend.py",
)

FEATURE_MODULES = (
    "src/gu_toolkit/figure_layout.py",
    "src/gu_toolkit/figure_plot_editor.py",
    "src/gu_toolkit/figure_legend.py",
    "src/gu_toolkit/Slider.py",
    "src/gu_toolkit/_mathlive_widget.py",
)

SOURCE_REQUIREMENTS = {
    "src/gu_toolkit/ui_system.py": (
        "shared_theme_css()",
        "load_ui_css(",
        "build_boolean_field(",
        'PanelVariant = Literal["card", "minimal", "toolbar"]',
    ),
    "src/gu_toolkit/figure_layout.py": (
        'load_ui_css("figure_layout.css")',
        'variant="toolbar"',
        'variant="minimal"',
        'self.root_widget.add_class("gu-theme-root")',
    ),
    "src/gu_toolkit/figure_plot_editor.py": (
        'load_ui_css("plot_editor.css")',
        "build_boolean_field(",
        'family="dropdown"',
        'family="checkbox"',
        'family="numeric"',
    ),
    "src/gu_toolkit/figure_legend.py": (
        'load_ui_css("legend.css")',
        'family="color"',
        'family="numeric"',
        'toggle.icon = ""',
    ),
    "src/gu_toolkit/Slider.py": (
        'load_ui_css("slider.css")',
        "style_widget_value(",
        "self._theme_style",
        'family="checkbox"',
        'family="numeric"',
    ),
    "src/gu_toolkit/_mathlive_widget.py": (
        'add_class("gu-control")',
        'add_class("gu-control-math")',
    ),
}

FORBIDDEN_GENERIC_CSS_SNIPPETS = (
    ".gu-action-button",
    ".gu-modal-panel",
    ".gu-panel",
    ".gu-tab-bar",
    ".gu-inline-alert",
    "--gu-space-1",
)

FORBIDDEN_MATHLIVE_INLINE_STYLE_SNIPPETS = (
    "style.border =",
    "style.borderRadius =",
    "style.background =",
    "style.padding =",
)


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


def _read(repo_root: Path, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8")


def _check_hosted_panel(name: str, panel: object, failures: list[str]) -> None:
    for layout_attr in ("width", "min_width", "max_width"):
        value = _layout_value(panel, layout_attr)
        _require(bool(value), f"{name}: missing layout.{layout_attr}", failures)
        _require(
            "100%" in value,
            f"{name}: layout.{layout_attr} must stay container-relative ({value!r})",
            failures,
        )
        _require(
            "100vw" not in value and "100vh" not in value,
            f"{name}: layout.{layout_attr} must not use viewport units ({value!r})",
            failures,
        )


def _check_css_resources(repo_root: Path, failures: list[str]) -> None:
    css_root = repo_root / "src" / "gu_toolkit" / "css"
    for resource_name in CSS_RESOURCE_FILES:
        _require((css_root / resource_name).is_file(), f"missing CSS resource {resource_name}", failures)

    tokens = (css_root / "tokens.css").read_text(encoding="utf-8")
    controls = (css_root / "controls.css").read_text(encoding="utf-8")
    surfaces = (css_root / "surfaces.css").read_text(encoding="utf-8")

    for token in (
        "--gu-panel-label-size",
        "--gu-section-padding-minimal",
        "--gu-tab-height",
        "--gu-tab-padding-x",
        "--gu-tab-radius",
        "--gu-icon-hit-area",
        "--gu-icon-glyph-size",
        "--gu-legend-marker-diameter",
        "--gu-checkbox-size",
        "--gu-checkbox-accent",
    ):
        _require(token in tokens, f"tokens.css: missing token {token}", failures)

    _require(
        ".gu-control :is(input, textarea, select)" not in controls,
        "controls.css: blanket input styling must not target every input descendant",
        failures,
    )
    for snippet in (
        ".gu-control-checkbox input[type=\"checkbox\"]",
        ".gu-control-dropdown select:not([multiple])",
        ".gu-control-multiselect select[multiple]",
        ".gu-control-targets select[multiple]",
    ):
        _require(snippet in controls, f"controls.css: missing family selector {snippet}", failures)

    for snippet in (
        ".gu-panel-variant-minimal",
        ".gu-panel-variant-toolbar",
        ".gu-panel-title-variant-toolbar",
        ".gu-action-button-tab",
        "var(--gu-tab-height)",
        "var(--gu-icon-glyph-size)",
    ):
        _require(snippet in surfaces, f"surfaces.css: missing shared surface snippet {snippet}", failures)


def _check_source_guardrails(repo_root: Path, failures: list[str]) -> None:
    for relative_path, required_snippets in SOURCE_REQUIREMENTS.items():
        source = _read(repo_root, relative_path)
        for snippet in required_snippets:
            _require(
                snippet in source,
                f"{relative_path}: expected shared UI requirement {snippet!r}",
                failures,
            )

    ui_system_source = _read(repo_root, "src/gu_toolkit/ui_system.py")
    _require(
        ".gu-control :is(input, textarea, select)" not in ui_system_source,
        "ui_system.py: old blanket input selector must not be reintroduced",
        failures,
    )

    figure_layout_source = _read(repo_root, "src/gu_toolkit/figure_layout.py")
    _require(
        figure_layout_source.count('variant="minimal"') >= 3,
        "figure_layout.py: figure-side Output/Parameters/Info surfaces must use minimal panel variants",
        failures,
    )
    _require(
        figure_layout_source.count('variant="toolbar"') >= 1,
        "figure_layout.py: legend surface must use toolbar/titleless panel variant",
        failures,
    )

    for relative_path in HOSTED_DIALOG_SOURCES:
        source = _read(repo_root, relative_path)
        _require(
            "hosted_modal_dimensions(" in source,
            f"{relative_path}: hosted dialogs must derive widths from hosted_modal_dimensions()",
            failures,
        )
        for token in ("100vw", "100vh", "calc(100vw", "calc(100vh"):
            _require(
                token not in source,
                f"{relative_path}: found banned viewport-sized token {token!r}",
                failures,
            )

    for relative_path in (
        "src/gu_toolkit/figure_plot_editor.py",
        "src/gu_toolkit/figure_legend.py",
        "src/gu_toolkit/Slider.py",
    ):
        source = _read(repo_root, relative_path)
        for snippet in FORBIDDEN_GENERIC_CSS_SNIPPETS:
            _require(
                snippet not in source,
                f"{relative_path}: generic chrome must live in CSS resources, not local Python strings ({snippet!r})",
                failures,
            )

    mathlive_source = _read(repo_root, "src/gu_toolkit/_mathlive_widget.py")
    for snippet in FORBIDDEN_MATHLIVE_INLINE_STYLE_SNIPPETS:
        _require(
            snippet not in mathlive_source,
            f"_mathlive_widget.py: local visual styling must use shared tokens ({snippet!r})",
            failures,
        )

    pyproject = _read(repo_root, "pyproject.toml")
    _require(
        '"gu_toolkit" = ["css/*.css"]' in pyproject,
        "pyproject.toml: CSS resources must be packaged as package data",
        failures,
    )

    all_source = "\n".join(_read(repo_root, path) for path in FEATURE_MODULES)
    _require("<b>" not in all_source, "shared dialog titles must not rely on raw <b> markup", failures)


def _check_runtime(failures: list[str]) -> None:
    import sympy as sp

    from gu_toolkit import Figure, FigureLayout
    from gu_toolkit.Slider import FloatSlider
    from gu_toolkit._mathlive_widget import MathLiveField

    layout = FigureLayout()
    _require(
        "gu-panel-variant-toolbar" in layout.legend_panel.panel._dom_classes,
        "figure layout: legend panel must use toolbar/titleless surface variant",
        failures,
    )
    for panel_name, panel in (
        ("params", layout.params_panel.panel),
        ("info", layout.info_panel.panel),
        ("output", layout.print_panel),
    ):
        _require(
            "gu-panel-variant-minimal" in panel._dom_classes,
            f"figure layout: {panel_name} panel must use minimal surface variant",
            failures,
        )
    _require(layout.legend_header.layout.display == "none", "figure layout: legend title text must stay hidden", failures)

    figure = Figure()
    editor = figure._plot_editor
    legend = figure._legend

    for name, panel in (
        ("plot editor panel", editor._panel),
        ("plot editor error panel", editor._error_panel),
        ("legend style dialog panel", legend._dialog_panel),
    ):
        _check_hosted_panel(name, panel, failures)

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

    editor.open_for_new(default_kind="cartesian")
    _require(editor._title.value == "Plot editor", "plot editor: title must stay plain text", failures)
    _require("<b>" not in editor._title.value.lower(), "plot editor: title must not use raw <b>", failures)
    _require(editor._title_chip.layout.display == "none", "plot editor: create mode chip must stay hidden", failures)
    _require(editor._expression_tab_button.description == "Expression", "plot editor: first tab must be Expression", failures)
    _require(editor._style_tab_button.description == "Style", "plot editor: second tab must be Style", failures)
    _require(editor._settings_tab_button.description == "Advanced", "plot editor: third tab must be Advanced", failures)
    _require(editor._views_field.layout.display == "flex", "plot editor: single-view mode should keep the view selector available", failures)
    _require(editor._views_note.layout.display == "none", "plot editor: single-view mode should not replace the view selector with note text", failures)
    _require("gu-boolean-field" in editor._visibility_field._dom_classes, "plot editor: visibility must use boolean-field layout", failures)
    _require("gu-control-checkbox" in editor._visible_toggle._dom_classes, "plot editor: visibility toggle must use checkbox family", failures)
    _require("gu-control-dropdown" in editor._kind._dom_classes, "plot editor: plot type must use single-select dropdown family", failures)
    _require("gu-control-multiselect" in editor._views._dom_classes, "plot editor: target views must use multi-select family", failures)
    _require(
        ".gu-plot-editor-kind-control" in editor._style.value,
        "plot editor: local CSS must include plot-editor-specific selectors",
        failures,
    )
    for snippet in FORBIDDEN_GENERIC_CSS_SNIPPETS:
        _require(
            snippet not in editor._style.value,
            f"plot editor: local CSS must not duplicate base theme snippet {snippet!r}",
            failures,
        )

    figure_with_alt = Figure()
    figure_with_alt.add_view("alt")
    editor_with_alt = figure_with_alt._plot_editor
    editor_with_alt.open_for_new(default_kind="cartesian")
    _require(editor_with_alt._views_field.layout.display == "flex", "plot editor: multi-view mode should show view selector", failures)
    _require(editor_with_alt._views_note.layout.display == "none", "plot editor: multi-view mode should keep lightweight view note hidden", failures)

    editor_with_alt._cartesian_expression.value = "x"
    editor_with_alt._cartesian_variable.value = "x"
    editor_with_alt._views.value = ()
    editor_with_alt._apply_button.click()
    _require(editor_with_alt.panel_visible is True, "plot editor: validation must keep dialog open", failures)
    _require(editor_with_alt._error_open is False, "plot editor: routine validation must stay inline", failures)
    _require(editor_with_alt._active_tab == "advanced", "plot editor: missing view errors must route to advanced tab", failures)
    _require(editor_with_alt._settings_alert.layout.display == "flex", "plot editor: missing view errors must show inline alert", failures)

    x = sp.symbols("x")
    figure.plot(x, x, id="curve", label="Curve")
    editor.open_for_plot("curve")
    _require(editor._title.value == "Plot editor", "plot editor: edit title must stay plain", failures)
    _require(editor._title_chip.layout.display == "block", "plot editor: edit mode must show plain context text", failures)
    _require(editor._id_text.layout.display == "none", "plot editor: edit mode should hide editable plot id field", failures)
    _require(editor._id_readonly.layout.display == "block", "plot editor: edit mode should show readonly plot id presentation", failures)

    _require(
        figure._layout.legend_header_toolbar.children == (figure._legend._plot_add_button,),
        "legend panel: add-plot button must live in the legend header toolbar",
        failures,
    )
    _require(legend._style_widget.value != "", "legend: local legend CSS must be attached", failures)
    _require(".gu-legend-toggle::before" in legend._style_widget.value, "legend: local CSS must style the circular marker", failures)
    _require(".gu-action-button" not in legend._style_widget.value, "legend: local CSS must stay local", failures)

    row = figure._legend._rows["curve"]
    _require(row.toggle.icon == "", "legend: visibility marker must be rendered by CSS rather than text glyphs", failures)
    _require("mod-visible" in row.toggle._dom_classes, "legend: visible plots must keep mod-visible class", failures)
    row.toggle.value = False
    _require(row.toggle.icon == "", "legend: hidden marker must continue using CSS-driven iconography", failures)
    _require("mod-hidden" in row.toggle._dom_classes, "legend: hidden plots must keep mod-hidden class", failures)

    slider = FloatSlider(description="x")
    _require(slider.settings_title_text.value == "Parameter settings", "slider: title must use parameter wording", failures)
    _require("<b>" not in slider.settings_title_text.value.lower(), "slider: title must not use raw <b>", failures)
    _require(slider.btn_done_settings.description == "Done", "slider: live settings dialog must use Done action", failures)
    _require(".smart-slider-top-row" in slider._limit_style.value, "slider: local CSS must style the top row", failures)
    _require("--gu-space-1" not in slider._limit_style.value, "slider: local CSS must not duplicate the base theme", failures)
    _require("--gu-space-1" in slider._theme_style.value, "slider: standalone sliders must load the base theme", failures)
    slider.set_modal_host(figure._layout.root_widget)
    _require(slider._theme_style.value == "", "slider: hosted sliders inside a themed figure should not duplicate base theme CSS", failures)
    slider.set_modal_host(None)
    _require("--gu-space-1" in slider._theme_style.value, "slider: removing the host should restore the base theme", failures)

    math_field = MathLiveField()
    _require("gu-control" in math_field._dom_classes, "MathLive: field must opt into shared control family", failures)
    _require("gu-control-math" in math_field._dom_classes, "MathLive: field must opt into shared math control family", failures)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    failures: list[str] = []
    _check_css_resources(repo_root, failures)
    _check_source_guardrails(repo_root, failures)
    _check_runtime(failures)

    if failures:
        print("Widget layout guardrails failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print("Widget layout guardrails passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
