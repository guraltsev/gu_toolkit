# Project 024: Type Annotation Completion

**Status:** Active  
**Priority:** Low

## Goal
Complete type annotations in remaining weakly-typed modules and fix malformed hints.

## Current Gaps
- `Slider.py`: many public methods/constructor params remain untyped.
- `prelude.py`: public helpers/classes have inconsistent type hints.
- `figure_plot.py`: malformed type hints still present.

## TODO
- [ ] Add full public-method annotations to `Slider.py`.
- [ ] Add public API annotations to `prelude.py`.
- [ ] Fix malformed `figure_plot.py` typing (`Optional[int,str]` -> proper union).
- [ ] Run a typing check pass (non-blocking initially).

## Exit Criteria
- [ ] No malformed type hints remain in active modules.
- [ ] Public APIs have consistent type annotations.
