# Project 005: Testing Infrastructure & CI

**Status:** Active

## Status Update (2026-02-15)

### Completed
- [x] `tox.ini` exists.
- [x] Pytest and coverage configuration exist in `pyproject.toml`.
- [x] GitHub Actions workflow exists at `.github/workflows/tests.yml`.
- [x] Legacy manual `main()` harness in `tests/test_parameter_snapshot_numeric_expression.py` was converted to pytest-native discovery.

### Remaining TODO
- [ ] Raise coverage threshold once flaky/notebook-only tests are addressed.
- [ ] Continue converting notebook/manual tests to fully automated pytest coverage where practical.

---


## Problem

### Remaining Non-Standard Test Harnesses
Most Python test modules now use direct pytest discovery. The remaining non-standard coverage is primarily notebook-based (`*.ipynb`) demos/tests that are not yet part of routine CI execution.

### Import Robustness
Most tests now import through the package root via `tests/conftest.py`, but this should remain the default for all newly added tests to avoid path-sensitive behavior.

### Coverage Bar Still Conservative
Coverage is reported in CI, but `fail_under = 50` is intentionally conservative while notebook-only and integration-heavy paths are still being stabilized.

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

| Area | Current Tests | Follow-up |
|------|--------------|--------|
| ParseLaTeX ambiguous tree (bug-002) | `tests/test_parse_latex_regression.py` | Expand parser edge-case corpus as bugs are found |
| Slider widget value parsing | `tests/test_slider_parsing.py` | Add integration coverage for notebook widget wiring |
| PlotlyPane resize behavior | `tests/test_plotlypane_behavior.py` | Add browser-level checks when CI browser coverage is added |
| Figure render pipeline | `tests/test_figure_render_pipeline.py` | Add more complex multi-plot scenarios |
| Context stack thread safety | `tests/test_figure_context_thread_safety.py` | Stress-test with higher concurrency once timing stabilized |
| QueuedDebouncer error handling | `tests/test_debouncing_error_handling.py` | Add timing-sensitive debounce race regressions as needed |

## TODO checklist
- [ ] Keep this checklist aligned with project milestones.

## Exit criteria
- [x] All test files use standard pytest patterns when possible (custom harnesses only when strictly needed).
- [x] `pytest` runs all tests from any working directory
- [x] Coverage report is generated on each run
- [x] GitHub Actions runs tests on PR and push
- [x] New tests for each gap area listed above


## Status
Active


## Goal/Scope
See existing context and scope sections below for detailed boundaries.

## Summary of design
The implementation/design details for this project are captured in the existing project-specific sections above (for example, context, proposed areas, implementation plan, or architecture notes). This section exists to keep the project format consistent across active project records.

## Open questions
- None currently beyond items already tracked in the TODO checklist.

## Challenges and mitigations
- **Challenge:** Scope drift as related cleanup and modernization work is discovered.
  **Mitigation:** Keep TODO items explicit and only add new work after triage.
- **Challenge:** Regressions while refactoring existing behavior.
  **Mitigation:** Require targeted tests and keep delivery phased so the toolkit remains usable between milestones.
