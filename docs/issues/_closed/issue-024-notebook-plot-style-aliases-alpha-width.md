# Issue 024: Example notebook requests unsupported plot style aliases `alpha` and `width`

## Status
Closed

## Summary
State-of-completion checklist:
- [x] API behavior for style aliases (`alpha`, `width`) and canonical conflict handling is specified.
- [x] Alias mapping is implemented in plot normalization/update paths (`width`→`thickness`, `alpha`→`opacity`).
- [x] Automated tests cover alias acceptance and conflict errors in both create and update flows.
- [x] Notebook style example documents aliases directly instead of the original bug marker.
- [x] Public docs/discoverability now include alias options (`plot_style_options`, Plot.update docs).

## Evidence
- `tests/test_Figure_module_params.py` contains alias regression tests for create/update and conflict validation.
- `figure_plot.py` includes alias handling and explicit conflict errors for `thickness`/`width` and `opacity`/`alpha`.
- `docs/notebooks/Toolkit_overview.ipynb` now demonstrates `alpha` and `width` as supported aliases.

## TODO
- [x] Specify API behavior for style aliases (`alpha`, `width`) and conflict rules when canonical args are also provided.
- [x] Implement alias mapping in plot argument normalization with conflict validation.
- [x] Add tests for alias acceptance and precedence.
- [x] Add negative tests for ambiguous alias/canonical combinations.
- [x] Update notebook example to remove BUG marker and reference supported aliases.

## Exit criteria
- [x] Alias behavior is deterministic, documented, and covered by automated tests.
- [x] Example notebook style examples no longer carry this BUG marker.
