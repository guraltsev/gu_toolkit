"""Compatibility re-export wrapper for the figure coordinator.

Full API
--------
This module preserves historical imports such as ``from gu_toolkit.Figure
import Figure`` while delegating the implementation to
:mod:`gu_toolkit.figure_coordinator`.
"""

import sys as _sys

from . import figure_coordinator as _impl

_sys.modules[__name__] = _impl
