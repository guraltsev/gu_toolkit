from __future__ import annotations

import re
from pathlib import Path

from gu_toolkit import Figure, FigureLayout
from gu_toolkit.Slider import FloatSlider
from gu_toolkit.ui_system import load_ui_css


CSS_DIR = Path(__file__).resolve().parents[1] / "src" / "gu_toolkit" / "css"


def test_css_resources_exist_and_expose_tunable_tokens() -> None:
    expected_files = {
        "tokens.css",
        "controls.css",
        "surfaces.css",
        "figure_layout.css",
        "legend.css",
        "plot_editor.css",
        "slider.css",
    }
    assert expected_files.issubset({path.name for path in CSS_DIR.iterdir() if path.is_file()})

    tokens = (CSS_DIR / "tokens.css").read_text(encoding="utf-8")
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
        "--gu-math-font-size",
    ):
        assert token in tokens


def test_shared_controls_css_uses_family_specific_selectors_without_blanket_input_rule() -> None:
    controls = load_ui_css("controls.css")

    assert ".gu-control :is(input, textarea, select)" not in controls
    assert '.gu-control-checkbox input[type="checkbox"]' in controls
    assert ".gu-control-dropdown select:not([multiple])" in controls
    assert ".gu-control-multiselect select[multiple]" in controls
    assert ".gu-control-targets select[multiple]" in controls
    assert '.gu-control-color :is(input[type="color"], input[type="text"])' in controls
    assert ".gu-control-color:is(.widget-colorpicker, .jupyter-widget-colorpicker)" in controls
    assert ".gu-control-color :is(.widget-colorpicker-input, .jupyter-widget-colorpicker-input)" in controls
    assert '.gu-control-color input[type="color"]::-webkit-scrollbar' in controls
    assert "overflow-y: hidden !important;" in controls
    assert "scrollbar-width: none !important;" in controls


def test_surfaces_css_uses_panel_variants_and_dedicated_tab_icon_tokens() -> None:
    surfaces = load_ui_css("surfaces.css")

    for snippet in (
        ".gu-panel-variant-minimal",
        ".gu-panel-variant-toolbar",
        ".gu-panel-title-variant-toolbar",
        ".gu-action-button-tab",
        "var(--gu-tab-height)",
        "var(--gu-tab-padding-x)",
        "var(--gu-icon-glyph-size)",
        ".gu-modal-row",
        "overflow-y: visible !important;",
    ):
        assert snippet in surfaces

    width_block_match = re.search(
        r"\.gu-panel,\s*\.gu-panel-body,[^}]+width:\s*100% !important;",
        surfaces,
        re.S,
    )
    assert width_block_match is not None
    assert ".gu-modal-panel" not in width_block_match.group(0)


def test_figure_layout_exposes_styled_title_hooks() -> None:
    layout = FigureLayout(title="Demo")

    assert "gu-figure-title" in layout.title_html._dom_classes
    assert "gu-figure-titlebar" in layout._titlebar._dom_classes


def test_runtime_figure_panels_use_surface_variants_and_hide_legend_title() -> None:
    layout = FigureLayout()

    assert "gu-panel-variant-toolbar" in layout.legend_panel.panel._dom_classes
    assert "gu-panel-variant-minimal" in layout.params_panel.panel._dom_classes
    assert "gu-panel-variant-minimal" in layout.info_panel.panel._dom_classes
    assert "gu-panel-variant-minimal" in layout.print_panel._dom_classes
    assert layout.legend_header.layout.display == "none"


def test_plot_editor_uses_boolean_field_and_local_css_only() -> None:
    editor = Figure()._plot_editor

    assert "gu-boolean-field" in editor._visibility_field._dom_classes
    assert "gu-control-checkbox" in editor._visible_toggle._dom_classes
    assert "gu-control-dropdown" in editor._kind._dom_classes
    assert "gu-control-multiselect" in editor._views._dom_classes

    css = editor._style.value
    assert ".gu-plot-editor-kind-control" in css
    assert ".gu-plot-editor-visibility-field" in css
    assert ".gu-action-button" not in css
    assert ".gu-modal-panel" not in css
    assert "--gu-space-1" not in css


def test_surfaces_css_does_not_force_inline_alert_visibility() -> None:
    surfaces = load_ui_css("surfaces.css")
    alert_block = surfaces.split(".gu-inline-alert", 1)[1].split("}", 1)[0]

    assert "display: flex !important;" not in alert_block


def test_legend_and_slider_keep_local_css_separate_from_base_theme() -> None:
    figure = Figure()
    legend = figure._legend
    slider = FloatSlider(description="x")

    assert ".gu-legend-toggle::before" in legend._style_widget.value
    assert ".gu-action-button" not in legend._style_widget.value
    assert ".smart-slider-top-row" in slider._limit_style.value
    assert "--gu-space-1" not in slider._limit_style.value
    assert "--gu-space-1" in slider._theme_style.value

    slider.set_modal_host(figure._layout.root_widget)
    assert slider._theme_style.value == ""

    slider.set_modal_host(None)
    assert "--gu-space-1" in slider._theme_style.value


def test_legend_marker_css_uses_plot_color_variable_and_mathlive_font_is_tuned() -> None:
    from gu_toolkit._mathlive_widget import MathLiveField

    legend_css = load_ui_css("legend.css")
    controls_css = load_ui_css("controls.css")
    tokens_css = load_ui_css("tokens.css")

    assert "--gu-legend-marker-color" in legend_css
    assert "var(--gu-legend-marker-color, currentColor)" in legend_css
    assert "--gu-math-font-size: 18px;" in tokens_css
    assert "font-size: var(--gu-math-font-size) !important;" in controls_css
    assert 'node.style.fontSize = "var(--gu-math-font-size, 18px)";' in MathLiveField._esm


def test_mathlive_frontend_defers_semantic_runtime_options_until_mount() -> None:
    from gu_toolkit._mathlive_widget import MathLiveField

    esm = MathLiveField._esm

    assert 'node.addEventListener("mount", handleMount, { once: true });' in esm
    assert 'if (!node.__guMounted) {' in esm
    assert 'node.__guBaseInlineShortcuts = { ...(node.inlineShortcuts || {}) };' in esm
    assert "requestAnimationFrame" in esm
    assert "el.appendChild(input);\n        scheduleSyncFromModel();" in esm


def test_mathlive_frontend_integrates_compute_engine_transport() -> None:
    from gu_toolkit._mathlive_widget import MathLiveField

    esm = MathLiveField._esm

    assert 'import("https://esm.run/@cortex-js/compute-engine")' in esm
    assert 'node.computeEngine = ce;' in esm
    assert 'model.set(key, snapshot[key]);' in esm
    assert 'transport_valid' in esm
    assert 'model.on("change:semantic_context", onSemantic);' in esm
    assert 'serialize: (serializer, expr) =>' in esm


def test_legend_runtime_style_widget_includes_row_specific_marker_colors() -> None:
    import sympy as sp

    figure = Figure()
    x = sp.symbols("x")
    figure.plot(sp.sin(x), x, id="sin", color="#123456")

    css = figure._legend._style_widget.value
    encoded_plot_id = figure._legend._rows["sin"].css_plot_id
    assert "--gu-legend-marker-color: #123456 !important;" in css
    assert ".gu-legend-toggle" in css
    assert "b64-c2lu" in css
    assert f".gu-legend-plot-id-{encoded_plot_id}.gu-legend-toggle" in css
    assert f".gu-legend-plot-id-{encoded_plot_id}.gu-legend-inline-button" not in css


def test_checkbox_css_keeps_hidden_description_label_collapsed() -> None:
    controls_css = load_ui_css("controls.css")
    plot_editor_css = load_ui_css("plot_editor.css")

    assert ".gu-control-checkbox .widget-label {" in controls_css
    assert "display: none !important;" in controls_css
    assert ".gu-control-checkbox .widget-label-basic {" in controls_css
    assert ".gu-plot-editor-visibility-field .gu-control-checkbox .widget-label {" in plot_editor_css
    assert ".gu-plot-editor-visibility-field .gu-control-checkbox .widget-label-basic {" in plot_editor_css
