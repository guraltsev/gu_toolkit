"""Top-level public API for the ``gu_toolkit`` package.

This module re-exports the notebook-facing convenience surface so users can
import from a single namespace, for example:

>>> from gu_toolkit import Figure, parameter, plot  # doctest: +SKIP

It intentionally exposes both high-level plotting helpers and lower-level
building blocks (parameter events/references and numeric-expression wrappers)
for advanced integrations.
"""

from .notebook_namespace import *
from .NamedFunction import NamedFunction as NamedFunction
from .numeric_callable import (
    DYNAMIC_PARAMETER,
    NumericFunction,
    ParameterContext,
    UNFREEZE,
    numpify,
    numpify_cached,
)

from .Figure import Figure, FigureLayout, Plot
from .Slider import FloatSlider
from .Figure import (
    current_figure,
    info,
    get_sampling_points,
    get_title,
    get_x_range,
    get_y_range,
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
from .ParseLaTeX import parse_latex
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef

from .ParameterSnapshot import ParameterSnapshot

# Optional explicit module handle to avoid callable/module name ambiguity.
from . import numpify as numpify_module
from .PlotSnapshot import PlotSnapshot
from .FigureSnapshot import FigureSnapshot, InfoCardSnapshot, ViewSnapshot
from .codegen import CodegenOptions, sympy_to_code, figure_to_code
