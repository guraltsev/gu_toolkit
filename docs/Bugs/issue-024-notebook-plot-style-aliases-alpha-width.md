# Issue 024: Example notebook requests unsupported plot style aliases `alpha` and `width`

## Status
Open

## Summary
The example notebook documents a bug requesting `alpha` as a synonym for `opacity` and `width` as a synonym for `thickness`.

Without alias support (or explicit rejection with clear errors), users porting from common plotting APIs may encounter confusing behavior.

## Evidence
- In the "Interacting sine waves" section of `docs/notebooks/Toolkit_overview.ipynb`, the notebook includes:
  - `#BUG: introduce alpha as a synonym for opacity, introduce width as a synonym for thickness`

## TODO
- [ ] Specify API behavior for style aliases (`alpha`, `width`) and conflict rules when canonical args are also provided.
- [ ] Implement alias mapping (or explicit validation errors) in plot argument normalization.
- [ ] Add tests for alias acceptance and precedence in `tests/test_figure_render_pipeline.py` (or new dedicated test module).
- [ ] Add negative tests that confirm clear error messages for ambiguous alias/canonical combinations if disallowed.
- [ ] Update notebook and docs examples to use either canonical names only or documented aliases consistently.

## Exit criteria
- Alias behavior is deterministic, documented, and covered by automated tests.
- Example notebook style examples no longer carry this BUG marker.
