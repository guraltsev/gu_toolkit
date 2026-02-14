# Project 006: Fix Known Bugs & Clean Up Stale Code

**Priority:** Medium
**Effort:** Low
**Impact:** Eliminates known failure modes, reduces confusion for maintainers

---

## Bug Fixes

### BF1. Fix ParseLaTeX Ambiguous Tree Return (Bug-002)

**File:** `ParseLaTeX.py`
**Bug:** `parse_latex()` can return a `lark.Tree` object instead of a SymPy `Expr` when the lark backend parses an ambiguous expression (e.g., `\frac{1}{2}x` without explicit multiplication).

**Fix:**
```python
def parse_latex(latex_str: str) -> sp.Expr:
    try:
        result = sp_parse_latex(latex_str, backend="lark")
        if not isinstance(result, sp.Basic):
            raise TypeError(f"lark returned {type(result).__name__}, not a SymPy expression")
        return result
    except Exception:
        pass  # fall through to antlr

    try:
        return sp_parse_latex(latex_str, backend="ANTLR")
    except Exception as e2:
        raise LatexParseError(...) from e2
```

**Test:** Add a regression test with an input known to produce a `Tree` from lark.

### BF2. Fix Mutable Default Argument in Plot.__init__

**File:** `figure_plot.py:40`

**Before:**
```python
parameters: Sequence[Symbol] = [],
```

**After:**
```python
parameters: Sequence[Symbol] = (),
```

Using an immutable tuple as the default is the standard safe pattern.

### BF3. Fix Malformed Type Hint in Plot.__init__

**File:** `figure_plot.py:42`

**Before:**
```python
sampling_points: Optional[int,str] = None,
```

**After:**
```python
sampling_points: Optional[Union[int, str]] = None,
```

### BF4. Add Error Handling to QueuedDebouncer Callback

**File:** `debouncing.py:84`

**Before:**
```python
self._callback(*call.args, **call.kwargs)
```

**After:**
```python
try:
    self._callback(*call.args, **call.kwargs)
except Exception:
    import logging
    logging.getLogger(__name__).exception("Debounced callback failed")
```

This prevents silent callback failures from permanently stopping debounced updates.

---

## Stale Code Cleanup

### SC1. Remove duplicate module docstring in Figure.py

**File:** `Figure.py`
**Action:** Remove the second docstring block (lines 12-97). Keep only the first docstring (lines 1-6).

### SC2. Remove stale drop-in replacement comment

**File:** `Figure.py:10`
**Action:** Delete: `# NOTE: This file is Figure.py with the Info Components API implemented. It is intended as a drop-in replacement.`

### SC3. Remove commented debug print in prelude.py

**File:** `prelude.py:26`
**Action:** Delete: `# print("__all__ (from prelude):",__all__)`

### SC4. Remove duplicate import in prelude.py

**File:** `prelude.py:27`
**Action:** Delete the second `import sympy as sp` (already imported on line 13).

### SC5. Update developer guide file references

**File:** `documentation/develop_guide/smartfigure_developer_guide.md`
**Issue:** References to "SmartFigure.py" and "SmartSlider.py" — these files have been renamed to `Figure.py` and `Slider.py`. Update all file references in the developer guide to match current names.

---

## Acceptance Criteria

- [ ] `parse_latex()` always returns a SymPy expression (never a Tree)
- [ ] Regression test for bug-002 passes
- [ ] No mutable default arguments in any `__init__`
- [ ] All type hints are syntactically valid
- [ ] QueuedDebouncer logs callback errors instead of swallowing them
- [ ] No stale comments or duplicate docstrings in source files
- [ ] Developer guide uses current file names
