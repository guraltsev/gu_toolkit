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
    plot,
    plot_style_options,
    plots,
    render,
    set_sampling_points,
    set_title,
    set_x_range,
    set_y_range,
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
