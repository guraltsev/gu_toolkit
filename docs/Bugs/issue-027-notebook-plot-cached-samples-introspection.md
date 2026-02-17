# Issue 027: Example notebook introspection references missing `Plot.cached_samples` attribute

## Status
Open

## Summary
The final notebook introspection example attempts to read `plot_obj.cached_samples`, but the `Plot` object has no such attribute, causing `AttributeError`.

This breaks the notebook's debugging/introspection walkthrough and indicates mismatch between public-facing examples and object API.

## Evidence
- In `docs/notebooks/Toolkit_overview.ipynb`, the captured traceback shows:
  - `AttributeError: 'Plot' object has no attribute 'cached_samples'`
- The failing line is in the introspection block after retrieving `plot_obj = fig3.plots["symbolic-wave"]`.

## TODO
- [ ] Decide intended public API: expose `cached_samples`, expose a replacement property, or update notebook to supported equivalent.
- [ ] Implement the chosen API/documentation behavior.
- [ ] Add regression tests for plot introspection attributes used in docs/notebooks.
- [ ] Add notebook parity tests to ensure documented introspection snippets remain executable.

## Exit criteria
- Introspection example runs without `AttributeError`.
- Automated tests lock down the supported introspection surface used by examples.
