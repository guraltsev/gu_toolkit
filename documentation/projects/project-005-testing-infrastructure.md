# Project 005: Testing Infrastructure & CI

**Status:** Active

## Status Update (2026-02-15)

### Completed
- [x] `tox.ini` exists.
- [x] Pytest and coverage configuration exist in `pyproject.toml`.
- [x] GitHub Actions workflow exists at `.github/workflows/tests.yml`.

### Remaining TODO
- [ ] Remove stale guidance in this document that says CI/tox are missing.
- [ ] Standardize remaining non-pytest notebook/manual test patterns where practical.
- [ ] Raise coverage threshold once flaky/notebook-only tests are addressed.

---


## Problem

### No CI/CD Pipeline
There are no GitHub Actions workflows, no `tox.ini`, and no automated test execution. Tests are run manually, which means regressions can slip into merged PRs.

### Non-Standard Test Harness
Test files use inconsistent patterns:
- `test_Figure_module_params.py` uses a custom `main()` function and manual `_assert_raises` helper.
- `test_info_cards.py` assumes pytest discovery (no `main()`).
- `test_NamedFunction.py`, `test_numpify_refactor.py`, `test_numpify_cache_behavior.py` use `importlib.util.spec_from_file_location` with hardcoded relative paths like `Path("NamedFunction.py")`.

### Fragile Test Imports
The `spec_from_file_location` pattern breaks if tests are run from any directory other than the project root. With proper packaging (`pip install -e .`), tests can simply `import gu_toolkit` and all path issues disappear.

### No Coverage Reporting
There is no visibility into which code paths are tested.

## Recommended Changes

### 1. Standardize All Tests to pytest

Convert custom test harnesses to standard pytest:

**Before (custom harness):**
```python
def main():
    tests = [test_foo, test_bar]
    for t in tests:
        t()
        print(f"  PASS: {t.__name__}")
```

**After (pytest-native):**
```python
def test_foo():
    ...

def test_bar():
    ...
```

Remove all `main()` entry points, `_assert_raises` helpers, and manual test lists.

### 2. Fix Test Imports

**Before (fragile):**
```python
import importlib.util
spec = importlib.util.spec_from_file_location("numpify", Path("numpify.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
numpify = mod.numpify
```

**After (standard):**
```python
from gu_toolkit.numpify import numpify
```

To be compatible with no packaging use the following custom load code:

```python
import sys
from pathlib import Path

try:
    _start = Path(__file__).resolve().parent
except NameError:
    _start = Path.cwd().resolve()

_pkg_root = _start
while _pkg_root != _pkg_root.parent and not (_pkg_root / "__init__.py").exists():
    _pkg_root = _pkg_root.parent
sys.path.insert(0, str(_pkg_root.parent))


from gu_toolkit import ...
```

### 3. Add pytest Configuration

In `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

### 4. Add Coverage Configuration

```toml
[tool.coverage.run]
source = ["gu_toolkit"]
omit = ["*/tests/*"]

[tool.coverage.report]
show_missing = true
fail_under = 50
```

### 5. Add GitHub Actions Workflow

Create `.github/workflows/tests.yml`:
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest --cov --cov-report=term-missing
```

### 6. Add Missing Test Coverage

Priority areas for new tests:

| Area | Current Tests | Needed |
|------|--------------|--------|
| ParseLaTeX ambiguous tree (bug-002) | 0 | Regression test for Tree return type |
| Slider widget value parsing | 0 | Test expression parsing, error recovery |
| PlotlyPane resize behavior | 0 (notebook only) | At minimum, test Python-side logic |
| Figure render pipeline | 0 | End-to-end: create figure, add plot, trigger render |
| Context stack thread safety | 0 | Test concurrent push/pop |
| QueuedDebouncer error handling | 0 | Test callback that raises exception |

## Acceptance Criteria

- [ ] All test files use standard pytest patterns when possible (custom harnesses only when strictly needed).  Avoid fragile approaches
- [ ] `pytest` runs all tests from any working directory
- [ ] Coverage report is generated on each run
- [ ] GitHub Actions runs tests on PR and push
- [ ] New tests for each gap area listed above
