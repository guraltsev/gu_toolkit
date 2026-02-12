"""Canonical slider API names.

Provides non-"Smart" aliases for slider widgets while keeping backwards
compatibility with existing ``SmartSlider`` imports.
"""

from .SmartSlider import SmartFloatSlider as FloatSlider, SmartFloatSlider

__all__ = ["FloatSlider", "SmartFloatSlider"]
