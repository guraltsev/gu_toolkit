"""SmartRegistry package.

This package implements a small reactive-parameter core intended for
Jupyter/JupyterLab usage.

Only **Stage 1 & Stage 2** of the project blueprint are implemented here:

* `SmartParameter`: typed/clamped parameter with callback notification.
* `CallbackToken`: opaque handle returned from callback registration.

Stages not implemented yet (by design): weakref-backed callbacks, error
aggregation, and the `SmartParameterRegistry` auto-vivifying mapping.

Public re-exports:
    - CallbackToken
    - SmartParameter
"""



from .SmartParameters import *
