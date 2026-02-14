# Project 06: Type Annotation Completion

**Priority:** Low
**Effort:** Low
**Impact:** Better IDE support, catches type errors early, improves documentation

---

## Problem

Type annotation coverage is inconsistent across the codebase:

| Coverage Level | Files |
|---------------|-------|
| Excellent | `Figure.py`, `InputConvert.py`, `ParamRef.py`, `NamedFunction.py`, `numpify.py`, `ParamEvent.py` |
| Good | `ParameterSnapshot.py`, `debouncing.py`, `ParseLaTeX.py`, `figure_context.py`, `figure_parameters.py`, `figure_info.py`, `figure_plot.py`, `PlotlyPane.py` |
| Minimal | `Slider.py`, `prelude.py` |

The two files with minimal annotations are also among the most complex in the codebase.

## Specific Gaps

### Slider.py

The `FloatSlider.__init__` method (~300 lines) has no type annotations on its parameters:

```python
def __init__(
    self,
    value=0.0,       # should be: value: float = 0.0
    min=0.0,         # should be: min: float = 0.0
    max=1.0,         # should be: max: float = 1.0
    step=0.1,        # should be: step: float = 0.1
    description="Value:",  # should be: description: str = "Value:"
    **kwargs,
):
```

Internal methods (`_commit_text_value`, `_sync_number_from_slider`, `_commit_limit_value`, etc.) also lack annotations.

### prelude.py

Most functions and classes have minimal or no annotations:
- `SymbolFamily.__new__` and `__getitem__`: no return types
- `FunctionFamily`: no annotations
- `NIntegrate()`: parameter types are only in docstrings, not in the signature
- `NReal_Fourier_Series()`: same
- `play()`: same
- `_resolve_numeric_callable()`: partially annotated

### figure_plot.py

The malformed type hint at line 42 (`Optional[int,str]`) needs fixing to `Optional[Union[int, str]]`.

## Recommended Approach

1. **Start with `Slider.py`** — add type annotations to `__init__` and all public methods. This is the most-used widget and benefits most from IDE support.

2. **Then `prelude.py`** — annotate public functions (`NIntegrate`, `NReal_Fourier_Series`, `play`) and class methods (`SymbolFamily`, `FunctionFamily`). Internal helpers can remain less strictly typed.

3. **Fix the `figure_plot.py` malformed hint** — this is a one-line fix.

4. **Consider adding a `py.typed` marker** — if packaging is in place, adding `py.typed` signals to tools that the package provides type information.

## Optional: Add mypy Configuration

In `pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

This can be added to CI as a non-blocking check initially, then tightened over time.

## Acceptance Criteria

- [ ] `Slider.py` has type annotations on all public methods
- [ ] `prelude.py` has type annotations on all public functions
- [ ] `figure_plot.py:42` type hint is syntactically correct
- [ ] No mypy errors on annotated files (with `ignore_missing_imports`)
