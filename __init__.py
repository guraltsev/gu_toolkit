"""Top-level public API for the ``gu_toolkit`` package.

This module re-exports the notebook-facing convenience surface so users can
import from a single namespace, for example:

>>> from gu_toolkit import Figure, parameter, plot  # doctest: +SKIP

It intentionally exposes both high-level plotting helpers and lower-level
building blocks (parameter events/references and numeric-expression wrappers)
for advanced integrations.
"""

# Optional explicit module handle to avoid callable/module name ambiguity.
from . import numpify as numpify_module
from .codegen import CodegenOptions, figure_to_code, sympy_to_code
from .Figure import (
    Figure,
    FigureLayout,
    Plot,
    current_figure,
    get_sampling_points,
    get_title,
    get_x_range,
    get_y_range,
    info,
    parameter,
    parameters,
    params,
    plots,
    render,
    set_sampling_points,
    set_title,
    set_x_range,
    set_y_range,
)
from .Figure import (
    plot as toolkit_plot,
)
from .Figure import (
    plot_style_options as toolkit_plot_style_options,
)
from .FigureSnapshot import FigureSnapshot, InfoCardSnapshot, ViewSnapshot
from .NamedFunction import NamedFunction as NamedFunction
from .notebook_namespace import *
from .numeric_callable import (
    DYNAMIC_PARAMETER,
    UNFREEZE,
    NumericFunction,
    ParameterContext,
    numpify,
    numpify_cached,
)
from .ParameterSnapshot import ParameterSnapshot
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .ParseLaTeX import parse_latex
from .PlotSnapshot import PlotSnapshot
from .Slider import FloatSlider

# Keep toolkit helpers authoritative after notebook namespace wildcard imports.
# ``notebook_namespace`` intentionally exports SymPy's ``plot`` helper via
# ``from sympy import *`` for convenience, but package-level ``plot`` should
# resolve to gu_toolkit's module helper for notebook examples and docs.
plot = toolkit_plot
plot_style_options = toolkit_plot_style_options
