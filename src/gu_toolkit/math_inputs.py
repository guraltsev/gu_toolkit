"""Compatibility re-export for the semantic MathLive input widgets.

Prefer ``gu_toolkit.mathlive`` or ``gu_toolkit.mathlive.inputs`` for
new code. This module remains to avoid breaking existing imports.
"""

from .mathlive.inputs import *
from .mathlive.inputs import __all__
