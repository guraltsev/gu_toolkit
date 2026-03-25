# Parametric plotting

## Public API

Use `Figure.parametric_plot(...)` or the module-level `parametric_plot(...)`
helper to render a curve defined by `(x(t), y(t))` over an explicit parameter
interval:

```python
import sympy as sp
from gu_toolkit import Figure

fig = Figure(samples=600)
t, a, b = sp.symbols("t a b")
fig.parameter(a, value=2.0, min=0.5, max=3.0)
fig.parameter(b, value=1.0, min=0.5, max=2.0)
fig.parametric_plot(
    (a * sp.cos(t), b * sp.sin(t)),
    (t, 0, 2 * sp.pi),
    id="ellipse",
    label="ellipse",
    color="royalblue",
)
```

The helper accepts the same styling and view-routing keywords as `plot(...)`
(`id`, `label`, `visible`, `samples`, `color`, `thickness`, `dash`, `opacity`,
`line`, `trace`, `view`, `vars`). The parameter interval is always supplied by
`(t, min, max)`, so there is no `x_domain=` keyword for parametric curves.

## Semantics

- Parametric plots sample the full parameter interval on every render.
- Viewport pan/zoom changes only what is visible, not the sampled interval.
- Coordinate components may be constant (for example, vertical or horizontal
  curves).
- Parameter inference merges free symbols from both coordinate components.

## Internal ownership

- `figure_parametric_plot.py` owns the `ParametricPlot` runtime and the
  create/update helper used by `Figure.parametric_plot(...)`.
- `figure_plot_normalization.py` normalizes `(xexpr, yexpr)` inputs.
- `PlotSnapshot` + `codegen.py` preserve parametric curves for
  snapshot/code-generation round trips.
