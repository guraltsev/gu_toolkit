"""Public entry point for the Phase 1 math-input rebuild surface.

This package intentionally exposes only one audited widget class,
:class:`gu_toolkit.math_input.widget.MathInput`. The frontend implementation uses
MathLive behind an AnyWidget bridge, but that backend detail stays private to
this subpackage so the user-facing Python API remains a small raw-value
contract.

Examples
--------
Basic use::

    from gu_toolkit.math_input import MathInput
    field = MathInput(value=r"x^2 + 1")
    field

Top-level package use::

    from gu_toolkit import MathInput
    MathInput(value=r"\\frac{1}{1+x}")

Learn more / explore
--------------------
- Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
- Guide: ``docs/guides/math-input.md``.
- Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
- Contract test: ``tests/test_math_input_widget.py``.
"""

from .widget import MathInput

__all__ = ["MathInput"]
