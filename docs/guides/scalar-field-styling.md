# Scalar-field styling guide

The scalar-field API used by `Figure.contour(...)`, `Figure.density(...)`,
and `Figure.temperature(...)` now exposes a richer styling surface for
scientific visualization workflows such as wave propagation, diffraction,
interference, and potential maps.

## Discoverability helpers

Use the built-in helpers to inspect the supported knobs at runtime:

```python
import gu_toolkit as gt

print(gt.field_style_options()["level_step"])
print(gt.field_palette_options()["diffraction"])
```

`field_style_options()` describes the public contour/heatmap style keywords.
`field_palette_options()` documents the curated named palettes and their
aliases.

## Curated palette names

The toolkit accepts Plotly named color scales directly, and also ships a
curated layer of field-oriented aliases:

- `thermal` / `temperature`
- `hot` / `heat`
- `viridis` / `amplitude`
- `plasma`
- `magma`
- `cividis`
- `ice`
- `icefire` / `diffraction`
- `phase` / `twilight`
- `potential` / `balance`
- `grayscale` / `greyscale` / `gray` / `grey`
- `turbo`

These are especially useful for diffraction work:

- `diffraction`: interference and diffraction intensity maps
- `phase`: wrapped phase fields and angle-like quantities
- `potential`: signed potentials around a neutral midpoint
- `thermal`: energy-density style heatmaps

## Contour-line spacing and style

Contours can be requested by approximate count or by exact value spacing.

```python
fig.contour(
    psi.real,
    x,
    y,
    level_step=0.05,
    level_start=-0.5,
    level_end=0.5,
    line_color="white",
    line_width=1.2,
    line_dash="dash",
)
```

Useful contour options:

- `levels`: approximate number of contours
- `level_step`: exact contour spacing in scalar-value units
- `level_start`, `level_end`: clamp the contour family to a chosen value window
- `line_color`, `line_width`
- `line_dash` or `dash`: Plotly dash style for contour lines
- `show_labels`: label contour lines
- `filled`: fill contour bands

`level_step` is usually the better choice when you want physically meaningful
contour spacing, for example equally spaced iso-potential lines.

## Temperature and density range control

Heatmap-like plots can either infer the scalar range from the sampled data or
use an explicit plotting window.

### Automatic range

```python
fig.temperature(intensity, x, y, colorscale="diffraction")
```

When `z_range=None` (the default), the color scale tracks the current data.

### Manual range with discrete bands

```python
fig.temperature(
    intensity,
    x,
    y,
    colorscale="diffraction",
    z_range=(0.0, 1.0),
    z_step=0.05,
    under_color="black",
    over_color="white",
    alpha=0.75,
)
```

Useful heatmap/temperature options:

- `z_range=(zmin, zmax)`: manual visible scalar range
- `z_step`: quantize the heatmap into discrete scalar bands
- `under_color`: color applied below `zmin`
- `over_color`: color applied above `zmax`
- `alpha` or `opacity`: overall heatmap opacity
- `show_colorbar`, `colorbar`
- `reversescale`

This is useful when you want a stable legend across parameter sweeps or want to
highlight numerical blow-up / clipped regions outside the trusted range.

## Example: diffraction on a potential barrier

```python
fig = gt.Figure()

fig.temperature(
    intensity,
    x,
    y,
    colorscale="diffraction",
    z_range=(0.0, 1.0),
    z_step=0.05,
    under_color="#081018",
    over_color="#fff7cc",
    alpha=0.82,
)

fig.contour(
    potential,
    x,
    y,
    colorscale="potential",
    level_step=0.1,
    line_color="white",
    line_dash="dot",
    line_width=1.0,
)
```

A common pattern is:

1. render wave intensity with `temperature(..., colorscale="diffraction")`
2. render the potential landscape with `contour(..., colorscale="potential")`
3. use fixed `z_range` and `level_step` for reproducible comparison across runs

## Snapshot and code generation

The new contour and heatmap style fields round-trip through snapshotting and
code generation, so `line_dash`, `level_step`, `z_step`, `under_color`, and
`over_color` survive save/restore flows.
