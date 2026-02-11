"""Top-level public API for the ``gu_toolkit`` package.

This module re-exports the notebook-facing convenience surface so users can
import from a single namespace, for example:

>>> from gu_toolkit import SmartFigure, parameter, plot  # doctest: +SKIP

It intentionally exposes both high-level plotting helpers and lower-level
building blocks (parameter events/references and numeric-expression wrappers)
for advanced integrations.
"""

from .prelude import *
from .NamedFunction import NamedFunction as NamedFunction
from .numpify import numpify as numpify, numpify_cached 
from .SmartFigure import SmartFigure as Figure, SmartFigure, plot, params, parameter, plot_style_options
from .SmartParseLaTeX import parse_latex
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
# from .SmartException import *
# from .SmartFigure import *

from .ParameterSnapshot import ParameterSnapshot
from .NumericExpression import LiveNumericExpression, DeadBoundNumericExpression, DeadUnboundNumericExpression
