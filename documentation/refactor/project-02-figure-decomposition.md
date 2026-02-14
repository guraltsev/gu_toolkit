# Project 02: Decompose Figure.py

**Priority:** Medium
**Effort:** Medium
**Impact:** Improves navigability, reduces cognitive load, clarifies module responsibilities

---

## Problem

`Figure.py` is 1,486 lines and contains three distinct concerns:

1. **The `Figure` class** — the coordinator that owns the rendering lifecycle.
2. **Module-level helper functions** — `plot()`, `parameter()`, `render()`, `info()`, etc. (~15 thin wrappers that delegate to the current figure).
3. **Module-level proxy objects** — `parameters`, `plots`, `params` (mapping proxies that read from the current figure context).

It also has stale artifacts:
- A duplicate module docstring (lines 1-6 and lines 12-28).
- A stale comment at line 10 referencing a "drop-in replacement" history.

## Current Coupling

The module-level helpers all follow the same pattern:

```python
def plot(var, expr, **kwargs):
    return _require_current_figure().plot(var, expr, **kwargs)
```

These ~15 functions add ~150 lines to Figure.py that are pure delegation. They also pull in `figure_context` imports that are only needed for the helpers, not for the `Figure` class itself.

## Recommended Changes

### Option A: Extract helpers to `figure_api.py` (Recommended)

Create a new file `figure_api.py` containing:
- All module-level helper functions (`plot()`, `parameter()`, `render()`, `info()`, etc.)
- All module-level proxy objects (`parameters`, `plots`, `params`)
- The `current_figure()` public function

Update `__init__.py` to import from `figure_api` instead of `Figure`.

**Benefits:**
- `Figure.py` shrinks to ~1,300 lines (just the class).
- The "what is the Figure class?" question is answered by one file.
- The "what convenience helpers exist?" question is answered by another.
- No changes to public API.

### Option B: Leave as-is, clean up stale artifacts only

If decomposition is deferred, at minimum:
- Remove the duplicate docstring (keep only the first one).
- Remove the stale "drop-in replacement" comment.
- Add a clear section header separating the class from the helpers.

## Stale Code to Remove Regardless of Choice

1. **Line 10:** `# NOTE: This file is Figure.py with the Info Components API implemented. It is intended as a drop-in replacement.`
2. **Lines 12-97:** The second module docstring block (everything between the two `"""`-delimited blocks).
3. **`prelude.py:26`:** `# print("__all__ (from prelude):",__all__)`
4. **`prelude.py:27`:** Duplicate `import sympy as sp` (already imported on line 13).

## Acceptance Criteria

- [ ] `Figure.py` contains only the `Figure` class and its internal helpers
- [ ] Module-level helpers are importable from the same paths as before
- [ ] No stale comments or duplicate docstrings remain
- [ ] All existing tests pass without modification
