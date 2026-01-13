"""SmartRegistry package.

This package implements a small reactive-parameter core intended for
Jupyter/JupyterLab usage.

Implemented blueprint stages:
* Stage 1–4: `SmartParameter` with typed/clamped values and weakref-backed,
  idempotent callback notification with error aggregation.
* Stage 5: `SmartParameterRegistry` auto-vivifying mapping for parameters.

Public re-exports:
    - CallbackToken
    - CallbackError
    - SmartParameter
    - SmartParameterRegistry
"""

from .SmartParameters import *  # noqa: F401,F403
