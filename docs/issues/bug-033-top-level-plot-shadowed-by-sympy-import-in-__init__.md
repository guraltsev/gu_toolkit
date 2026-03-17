# Issue 033: Top-level `gu_toolkit.plot` is shadowed by SymPy `plot` in package import order

## Status
Open (root cause fixed in code; retained open until import-surface contract coverage is complete)

## Summary
Assessment (2026-02-20): implementation is partially complete; runtime import rebinding is fixed, but import-surface contract coverage remains incomplete so the issue stays open.

State-of-completion checklist:
- [x] Package import order now preserves toolkit-level `plot` helper after wildcard notebook namespace imports.
- [ ] Dedicated import-surface contract tests are still missing for top-level helper names that can be shadowed by wildcard imports.
- [ ] Notebook/API documentation does not yet include a focused regression/quality guard for import-surface stability.

A notebook snippet that should call toolkit plotting helpers:

```python
fig = Figure(x_range=(-8, 8))
display(fig)
with fig:
    set_title("Quickstart: Interactive sine")
    plot(a * sin(b * x), x, id="wave", label=r"$a*\sin(bx)$")
```

can instead dispatch to `sympy.plotting.plot.plot`, producing:

- `ValueError: Too many free symbols.`
- `Expected 1 free symbols.`
- `Received 3: {a, x, b}`

This happens when users import `plot` from `gu_toolkit` (directly or indirectly) but package import order rebinds `plot` to SymPy's function.

## Evidence
- `__init__.py` previously imported toolkit `plot` from `Figure`, then executed `from .notebook_namespace import *`, where `notebook_namespace` performs `from sympy import *` and exports `plot`.
- The wildcard import therefore replaced the toolkit-level `plot` binding with SymPy's `plot` in package globals.
- A regression test reproduces this exact failure mode by importing `plot` from `gu_toolkit` and calling it inside `with fig:`.

## TODO
- [x] Ensure top-level package `plot` resolves to toolkit helper after wildcard namespace import.
- [x] Add regression test for expression parameter autodetection through `from gu_toolkit import plot` + context-managed `Figure`.
- [ ] Add dedicated notebook import-surface contract tests that assert toolkit helper names are not shadowed by convenience wildcard imports.

## Exit criteria
- [x] `from gu_toolkit import plot` resolves to toolkit `Figure.plot` helper semantics, not SymPy plotting module semantics.
- [x] The quickstart `with fig: plot(a*sin(b*x), x, ...)` path auto-detects `a`/`b` as parameters without raising SymPy free-symbol errors.
- [ ] Import-surface tests guard against future helper shadowing regressions.
