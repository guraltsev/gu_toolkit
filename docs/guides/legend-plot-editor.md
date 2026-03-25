# Legend plot editor

The figure legend now doubles as the main plot-authoring surface.

## User workflow

When a `Figure` is displayed, the legend sidebar shows a `+` button even before
any plots exist. Clicking it opens a modal editor where the user can choose a
plot family, enter expressions, pick target views, and set a small number of
high-value options.

Each existing legend row also exposes an edit button. Editing keeps the plot id
stable and routes the change back through the normal figure APIs instead of a
separate mutation path.

```python
import sympy as sp
from gu_toolkit import Figure

fig = Figure(samples=500)
fig.add_view("alt", title="Alternate view")
fig
```

After displaying the figure:

1. Use the legend `+` button to add a plot.
2. Choose a plot type.
3. Enter the expression(s) and the free variable(s).
4. Pick one or more target views.
5. Apply the draft.

## Supported plot families

The editor currently exposes five explicit modes:

- function plots `y = f(x)`
- parametric curves `(x(t), y(t))`
- contour plots `z = f(x, y)`
- density heatmaps
- temperature heatmaps

Mode selection is manual by design. This keeps the UI predictable and avoids
fragile heuristics around whether an entered expression should become a curve,
a contour, or a heatmap.

## Separate variable fields

The editor does not try to infer the independent variable from the main
expression field. Instead it exposes separate entries for:

- the cartesian free variable,
- the parametric parameter,
- the scalar-field `x` and `y` variables.

That makes the symbolic contract explicit and avoids surprising behavior when
users type expressions like `a*t + b` or `f(u, v)`.

## Automatic parameter creation

Free symbols that are not used as the independent variable are treated as figure
parameters. If a draft references a symbol that does not yet have a control, the
editor previews that fact and applying the draft creates the corresponding
parameter automatically.

Examples:

- entering `a*x + b` in function mode creates or reuses parameters `a` and `b`
- entering `a*cos(t), b*sin(t)` in parametric mode creates or reuses `a` and `b`
- entering `x^2 + y^2 + c` in contour mode creates or reuses `c`

## Per-plot options exposed in the editor

The dialog intentionally exposes a short list of options that are broadly useful
across notebooks:

- plot id
- label
- target views
- sample count for cartesian and parametric plots
- grid resolution for contour/density/temperature plots

The editor is not meant to replace the full programmatic plotting API. It is a
convenient authoring surface for common cases, while styling and advanced
options still belong to the existing update/style APIs.

## Current limitation

Parametric parameter bounds are currently required to be numeric. Bounds such as
`0` to `2*pi` are supported, but symbolic bounds such as `0` to `2*pi*a` are
rejected for now because the runtime parametric domain is still coerced to
floats.

## Implementation ownership

The feature is intentionally split across three modules with clear roles:

- `src/gu_toolkit/figure_legend.py`
  - legend rows
  - toolbar and edit-button triggers
  - active-view filtering
- `src/gu_toolkit/figure_plot_editor.py`
  - modal form
  - draft parsing/validation
  - parameter preview
  - routing back through `Figure.plot(...)`, `Figure.parametric_plot(...)`,
    `Figure.contour(...)`, `Figure.density(...)`, and `Figure.temperature(...)`
- `src/gu_toolkit/_mathlive_widget.py`
  - the small MathLive-backed expression widget used by the editor

This split keeps the legend responsible for row lifecycle, the editor
responsible for form state and symbolic validation, and `Figure` responsible for
coordinating the two.
