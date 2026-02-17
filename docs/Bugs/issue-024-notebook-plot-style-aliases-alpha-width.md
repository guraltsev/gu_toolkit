# Issue 024: Example notebook requests unsupported plot style aliases `alpha` and `width`

## Status
In Progress (implementation complete, pending external review)

## Summary
The example notebook documents a bug requesting `alpha` as a synonym for `opacity` and `width` as a synonym for `thickness`.

Without alias support (or explicit rejection with clear errors), users porting from common plotting APIs may encounter confusing behavior.

## Evidence
- Historically, the "Interacting sine waves" section in `docs/notebooks/Toolkit_overview.ipynb` carried the marker:
  - `#BUG: introduce alpha as a synonym for opacity, introduce width as a synonym for thickness`
- The notebook now documents the supported aliases directly (`width`/`thickness`, `alpha`/`opacity`).

## TODO
- [x] Specify API behavior for style aliases (`alpha`, `width`) and conflict rules when canonical args are also provided.
- [x] Implement alias mapping in plot argument normalization (`width`→`thickness`, `alpha`→`opacity`) with conflict validation.
- [x] Add tests for alias acceptance and precedence in `tests/test_Figure_module_params.py`.
- [x] Add negative tests that confirm clear error messages for ambiguous alias/canonical combinations.
- [x] Update notebook example to remove BUG marker and reference supported aliases.

## Implementation notes
- Canonical and alias pairs are both accepted when values are equal.
- Canonical and alias pairs raise `ValueError` when values differ to avoid ambiguity.
- Issue remains open until external review and sign-off.

## Exit criteria
- Alias behavior is deterministic, documented, and covered by automated tests.
- Example notebook style examples no longer carry this BUG marker.
