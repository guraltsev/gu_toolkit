# Issue 018: `figure_plot.Plot` uses mutable defaults and malformed type hints

## Status
Closed (Resolved 2026-02-15)

## Summary
`figure_plot.py` previously used mutable list defaults and malformed type syntax in `Plot` APIs. Those signatures have been corrected to use immutable defaults and valid union typing.

## Evidence
- `Plot.__init__`: `parameters: Sequence[Symbol] = ()`
- `Plot.set_func`: `parameters: Sequence[Symbol] = ()`
- `Plot.__init__`: `sampling_points: Optional[Union[int, str]] = None`

## TODO
- [x] Replace mutable list defaults with immutable defaults (`()` or `None`).
- [x] Fix malformed union typing for `sampling_points`.
- [x] Add/adjust regression tests around constructor defaults.

## Exit Criteria
- [x] No mutable default args remain in `Plot` public methods.
- [x] Type hints parse cleanly under static analysis.
