# Issue 027: Example notebook introspection references missing `Plot.cached_samples` attribute

## Status
Open

## Summary
Assessment (2026-02-17): implementation is partially complete; coverage and/or documentation gaps listed below keep this issue open.

State-of-completion checklist:
- [x] Plot sample caches are exposed via `x_data` and `y_data` properties with regression tests.
- [x] Tests confirm sample buffers are read-only and replaced on re-render.
- [ ] `Plot.cached_samples` attribute requested by notebook docs is still not implemented.
- [ ] Notebook introspection example is still not aligned to current public API surface.
- [ ] No compatibility alias or docs migration note bridges `cached_samples` to `x_data`/`y_data`.

## Evidence
- `figure_plot.py` defines `_x_data`/`_y_data` storage and `x_data`/`y_data` accessors, but no `cached_samples` property.
- `tests/test_Figure_module_params.py` contains cache-introspection tests for `x_data` and `y_data`.
- Issue notebook text still references `cached_samples` and reports `AttributeError`.

## TODO
- [ ] Decide intended public API: add `cached_samples`, add a compatibility property, or update notebook to supported equivalent.
- [ ] Implement chosen API/documentation behavior.
- [ ] Add regression tests for whichever introspection attributes are documented.
- [ ] Add notebook parity tests to keep introspection snippets executable.

## Exit criteria
- [ ] Introspection example runs without `AttributeError`.
- [ ] Automated tests lock down the supported introspection surface used by examples.
