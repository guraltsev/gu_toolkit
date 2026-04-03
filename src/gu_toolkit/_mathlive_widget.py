"""Compatibility re-export for the MathLive widget backend.

Prefer ``gu_toolkit.mathlive.widget`` for new code. This module remains
to avoid breaking existing imports and tests that intentionally inspect
the widget backend.
"""

from .mathlive.widget import *
from .mathlive.widget import __all__
