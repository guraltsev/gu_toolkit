from __future__ import annotations

import sys
from pathlib import Path


CSS_RESOURCE_FILES = (
    "tokens.css",
    "controls.css",
    "surfaces.css",
    "figure_layout.css",
    "legend.css",
    "slider.css",
)

FEATURE_MODULES = (
    "src/gu_toolkit/figure_layout.py",
    "src/gu_toolkit/figure_legend.py",
    "src/gu_toolkit/Slider.py",
    "src/gu_toolkit/ui_system.py",
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
    "src/gu_toolkit/figure_legend.py": (
        'load_ui_css("legend.css")',
        'family="color"',
        'family="numeric"',
        'toggle.icon = ""',
    ),
    "src/gu_toolkit/Slider.py": (
        'load_ui_css("slider.css")',
        'style_widget_value(',
        'self._theme_style',
        'family="checkbox"',
        'family="numeric"',
    ),
}

FORBIDDEN_GENERIC_CSS_SNIPPETS = (
    ".gu-action-button",
    ".gu-modal-panel",
    ".gu-panel",
    ".gu-tab-bar",
    ".gu-inline-alert",
    "--gu-space-1",
    "gu-control-math",
    "math-field",
)


def _read(repo_root: Path, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8")


def _require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _check_css_resources(repo_root: Path, failures: list[str]) -> None:
    css_dir = repo_root / "src" / "gu_toolkit" / "css"
    existing = {path.name for path in css_dir.iterdir() if path.is_file()}
    for filename in CSS_RESOURCE_FILES:
        _require(filename in existing, f"missing CSS resource {filename}", failures)
    _require("plot_editor.css" not in existing, "plot editor CSS should be removed in phase 0", failures)

    controls = _read(repo_root, "src/gu_toolkit/css/controls.css")
    tokens = _read(repo_root, "src/gu_toolkit/css/tokens.css")
    _require("gu-control-math" not in controls, "controls.css should not retain MathLive selectors", failures)
    _require("math-field" not in controls, "controls.css should not retain math-field selectors", failures)
    _require("--gu-math-font-size" not in tokens, "tokens.css should not retain MathLive font tokens", failures)


def _check_source_guardrails(repo_root: Path, failures: list[str]) -> None:
    for relative_path, snippets in SOURCE_REQUIREMENTS.items():
        source = _read(repo_root, relative_path)
        for snippet in snippets:
            _require(snippet in source, f"{relative_path}: missing expected snippet {snippet!r}", failures)

    for relative_path in FEATURE_MODULES:
        source = _read(repo_root, relative_path)
        for snippet in FORBIDDEN_GENERIC_CSS_SNIPPETS:
            _require(
                snippet not in source,
                f"{relative_path}: stale local snippet {snippet!r} should not remain",
                failures,
            )

    figure_source = _read(repo_root, "src/gu_toolkit/Figure.py")
    _require("figure_plot_editor" not in figure_source, "Figure.py should not import the removed plot editor", failures)
    _require("enable_plot_editor=False" in figure_source, "Figure.py should disable legend plot-editor wiring", failures)


def _check_runtime(failures: list[str]) -> None:
    import sympy as sp

    from gu_toolkit import Figure, FigureLayout
    from gu_toolkit.Slider import FloatSlider

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
    legend = figure._legend
    _require(not hasattr(figure, "_plot_editor"), "Figure should not expose a plot editor in phase 0", failures)
    _require(figure._layout.legend_header_toolbar.children == (), "legend toolbar should be empty in phase 0", failures)
    _require(legend.panel_visible is False, "legend panel should start hidden until plots exist", failures)

    x = sp.symbols("x")
    figure.plot(x, x, id="curve", label="Curve")
    row = figure._legend._rows["curve"]
    _require(row.toggle.icon == "", "legend: visibility marker must be rendered by CSS rather than text glyphs", failures)
    _require("mod-visible" in row.toggle._dom_classes, "legend: visible plots must keep mod-visible class", failures)
    _require(legend._style_widget.value != "", "legend: local legend CSS must be attached", failures)
    _require(".gu-legend-toggle::before" in legend._style_widget.value, "legend: local CSS must style the circular marker", failures)
    _require(".gu-action-button" not in legend._style_widget.value, "legend: local CSS must stay local", failures)

    slider = FloatSlider(description="x")
    _require(slider.settings_title_text.value == "Parameter settings", "slider: title must use parameter wording", failures)
    _require("<b>" not in slider.settings_title_text.value.lower(), "slider: title must not use raw <b>", failures)
    _require(slider.btn_done_settings.description == "Done", "slider: live settings dialog must use Done action", failures)
    _require(".smart-slider-top-row" in slider._limit_style.value, "slider: local CSS must style the top row", failures)
    _require("--gu-space-1" not in slider._limit_style.value, "slider: local CSS must not duplicate the base theme", failures)
    _require("--gu-space-1" in slider._theme_style.value, "slider: standalone sliders must load the base theme", failures)
    slider.set_modal_host(figure._layout.root_widget)
    _require(slider._theme_style.value == "", "slider: hosted sliders inside a themed figure should not duplicate base theme CSS", failures)


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
