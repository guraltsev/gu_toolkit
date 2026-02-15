# Issue 018: `figure_plot.Plot` uses mutable defaults and malformed type hints

## Status
Open

## Summary
`figure_plot.py` still uses mutable list defaults for `parameters` and malformed typing for `sampling_points`, which increases maintenance risk and weakens tooling support.

## Evidence
- `Plot.__init__`: `parameters: Sequence[Symbol] = []`
- `Plot.set_func`: `parameters: Sequence[Symbol] = []`
- `sampling_points: Optional[int,str] = None`

## TODO
- [ ] Replace mutable list defaults with immutable defaults (`()` or `None`).
- [ ] Fix malformed union typing for `sampling_points`.
- [ ] Add/adjust regression tests around constructor defaults.

## Exit Criteria
- [ ] No mutable default args remain in `Plot` public methods.
- [ ] Type hints parse cleanly under static analysis.
