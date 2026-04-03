"""Compatibility re-export for the semantic MathLive context subpackage.

Prefer ``gu_toolkit.mathlive`` or ``gu_toolkit.mathlive.context`` for
new code. This module remains to avoid breaking existing imports.
"""

from .mathlive.context import *
from .mathlive.context import __all__
