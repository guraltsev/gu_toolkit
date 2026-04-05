# API discovery guide

This guide is the shortest path from “I know roughly what I want to do” to
“here is the exact function, class, notebook, guide, and test I should read
next.” It complements the source docstrings: every public API now points back
here, and this guide points back out to the most relevant source modules.

## Quick start

For notebook-first work, start from the package surface:

```python
from gu_toolkit import Figure, plot, parameter, render
```

Then use the runtime discovery tools that are available everywhere:

```python
help(Figure)
dir(Figure)
help(plot)
```

When you are already inside a notebook figure workflow, explore from an
instance as well:

```python
fig = Figure()
dir(fig)
dir(fig.views)
dir(fig.parameters)
```

## The most useful discovery pattern

1. Start with the task-oriented map below.
2. Open the cited guide or example notebook.
3. Use `help(...)` on the exact function/class you plan to call.
4. Read the matching regression test when you need the precise contract.

This order is intentional:
- guides explain the mental model,
- examples show the workflow,
- docstrings show the exact call surface,
- tests pin down edge cases and invariants.

## Task map

| Task | Start here | Runtime discovery helpers | Read next |
|---|---|---|---|
| Create and manage interactive figures | `Figure`, `render`, `current_figure`, `figure_api.py` | `help(Figure)`, `dir(fig)`, `with fig:` | `docs/guides/develop_guide.md`, `examples/Toolkit_overview.ipynb` |
| Plot regular curves | `Figure.plot`, `plot`, `Plot` | `plot_style_options()`, `help(Figure.plot)` | `tests/test_figure_alias_api.py`, `examples/Toolkit_overview.ipynb` |
| Plot parametric curves | `Figure.parametric_plot`, `parametric_plot`, `ParametricPlot` | `help(Figure.parametric_plot)` | `docs/guides/parametric-plotting.md`, `tests/test_parametric_plot_api.py` |
| Plot scalar fields / contour / density / temperature | `scalar_field`, `contour`, `density`, `temperature`, `ScalarFieldPlot` | `field_style_options()`, `field_palette_options()` | `docs/guides/scalar-field-styling.md`, `tests/test_scalar_field_api.py` |
| Create parameters and sliders | `parameter`, `ParameterManager`, `ParamRef`, `FloatSlider` | `dir(fig.parameters)`, `help(ParamRef)`, `help(FloatSlider)` | `docs/guides/parameter-key-semantics.md`, `tests/test_param_change_hook_api.py`, `tests/test_slider_parsing.py` |
| Animate parameters | `AnimationClock`, `AnimationController`, slider animation properties | `help(AnimationController)`, `help(FloatSlider.animation_mode)` | `docs/guides/parameter-animation.md`, `tests/test_parameter_animation.py`, `tests/test_animation_clock_runtime.py` |
| Work with multiple views and layout | `fig.views`, `Figure.add_view`, `View`, `FigureLayout` | `dir(fig.views)`, `help(View)`, `help(Figure.add_view)` | `docs/guides/develop_guide.md`, `docs/guides/ui-layout-system.md`, `examples/layout_debug.ipynb` |
| Add explanatory/info content | `Figure.info`, `info`, `InfoPanelManager` | `help(Figure.info)`, `dir(fig.info_manager)` | `examples/Toolkit_overview.ipynb`, `tests/test_info_cards.py` |
| Snapshot or export a figure | `Figure.snapshot`, `Figure.to_code`, `figure_to_code`, `FigureSnapshot`, `PlotSnapshot` | `help(Figure.snapshot)`, `help(figure_to_code)` | `docs/guides/render-batching-and-snapshots.md`, `tests/test_figure_snapshot_codegen.py` |
| Convert symbolic input to numeric callables | `numpify`, `numpify_cached`, `NumericFunction`, `NamedFunction` | `help(numpify)`, `help(NumericFunction)` | `tests/test_numeric_callable_api.py`, `examples/Toolkit_overview.ipynb` |
| Work with symbolic-family helpers | `symbols`, `SymbolFamily`, `FunctionFamily`, `ParseLaTeX.parse_latex` | `help(symbols)`, `help(parse_latex)` | `tests/test_parse_latex_regression.py`, `tests/test_symbolic_families_helper.py` |
| Generate or inspect sound output | `Figure.sound`, `FigureSoundManager`, `play` | `help(play)`, `help(Figure.sound)` | `examples/Fourier-Sounds.ipynb`, `tests/test_figure_sound.py` |
| Diagnose runtime, layout, or performance issues | `runtime_diagnostics`, `figure_runtime_diagnostics`, `layout_logging`, `PerformanceMonitor` | `help(runtime_diagnostics)`, `help(PerformanceMonitor)` | `docs/guides/ui-layout-system.md`, `examples/layout_debug.ipynb`, `tests/test_runtime_support_backends.py` |

## What to inspect in a notebook

### Style-key discovery

Use these instead of guessing keyword names:

```python
plot_style_options()
field_style_options()
field_palette_options()
```

These helpers are especially important because they stay aligned with the
structured metadata used by validation, rendering, and code generation.

### Figure-centric discovery

If you know you are in a figure workflow, inspect the owner objects rather than
searching randomly across modules:

```python
dir(fig)
dir(fig.views)
dir(fig.parameters)
dir(fig.info_manager)
```

That reflects the package architecture: `Figure` is the coordinator, while view,
parameter, info, layout, and rendering subsystems keep their own state.

### Test-driven discovery

When the guide and docstring answer “how do I call this?” but you still need
“what are the exact guarantees?”, read the matching test module. The tests are
high-value API references in this repository because they encode real contracts,
round-trip expectations, and bug regressions.

## Module families

- **Figure/core orchestration**: `Figure.py`, `figure_api.py`, `figure_view.py`, `figure_layout.py`, `figure_parameters.py`, `figure_info.py`, `figure_legend.py`
- **Curve plotting**: `figure_plot.py`, `figure_plot_style.py`, `figure_plot_normalization.py`
- **Parametric plotting**: `figure_parametric_plot.py`
- **Scalar fields**: `figure_field.py`, `figure_field_style.py`, `figure_field_normalization.py`
- **Parameters and animation**: `ParamRef.py`, `ParamEvent.py`, `Slider.py`, `animation.py`, `parameter_keys.py`
- **Snapshots and codegen**: `FigureSnapshot.py`, `PlotSnapshot.py`, `FieldPlotSnapshot.py`, `codegen.py`
- **Symbolic/numeric bridge**: `Symbolic.py`, `numpify.py`, `NamedFunction.py`, `InputConvert.py`, `ParseLaTeX.py`, `numeric_operations.py`
- **Canonical identifiers**: `identifiers/policy.py`
- **Runtime/UI infrastructure**: `PlotlyPane.py`, `ui_system.py`, `widget_chrome.py`, `runtime_support.py`, `layout_logging.py`, `performance_monitor.py`

## Public docstring contract

Every public function, class, and method now follows the same structure:

- summary line,
- `Full API`,
- `Parameters`,
- `Returns`,
- `Optional arguments`,
- `Architecture note`,
- `Examples`,
- `Learn more / explore`.

If you want the authoring rules for those sections, read
`docs/guides/public-api-documentation-structure.md`.
