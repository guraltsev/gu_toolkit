"""Figure subsystem public surface.

Phase 2 structural split: this package provides focused module entry points for
figure context, plotting, parameters, layout, and compatibility helpers while
preserving the existing SmartFigure API.
"""

from .context import current_figure
from .core import Figure, SmartFigure
from .layout import FigureLayout, SmartFigureLayout
from .parameters import ParameterManager
from .plots import Plot, SmartPlot
from .compat import (
    add_info_component,
    get_info_output,
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

__all__ = [
    "Figure",
    "SmartFigure",
    "Plot",
    "SmartPlot",
    "FigureLayout",
    "SmartFigureLayout",
    "ParameterManager",
    "current_figure",
    "set_title",
    "get_title",
    "render",
    "get_info_output",
    "add_info_component",
    "set_x_range",
    "get_x_range",
    "set_y_range",
    "get_y_range",
    "set_sampling_points",
    "get_sampling_points",
    "plot_style_options",
    "parameter",
    "parameters",
    "params",
    "plots",
    "plot",
]
