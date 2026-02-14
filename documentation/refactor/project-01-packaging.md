# Project 01: Add Python Packaging Configuration

**Priority:** High
**Effort:** Low
**Impact:** Enables pip install, dependency management, CI/CD, and reproducible environments

---

## Problem

The toolkit has no `pyproject.toml`, `setup.py`, or `requirements.txt`. Users must manually install an unknown set of dependencies, and there is no way to version or distribute the package.

## Current State

- Dependencies are only discoverable by reading import statements across 18 source files.
- No version number is declared anywhere.
- The package cannot be installed in editable mode (`pip install -e .`), which is the standard developer workflow.

## Recommended Changes

### 1. Create `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "gu-toolkit"
version = "0.1.0"
description = "Interactive symbolic math plotting for Jupyter notebooks"
requires-python = ">=3.10"
dependencies = [
    "sympy>=1.12",
    "numpy>=1.24",
    "plotly>=5.18",
    "ipywidgets>=8.0",
    "anywidget>=0.9",
    "traitlets>=5.0",
    "pandas>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]
latex = [
    "lark>=1.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### 2. Move source files into `src/gu_toolkit/` layout

The current layout has source files directly in the repo root alongside tests and docs. The `src/` layout is the modern standard and prevents accidental imports from the working directory:

```
gu_toolkit/
  src/
    gu_toolkit/
      __init__.py
      Figure.py
      ...
  tests/
  documentation/
  pyproject.toml
```

Alternatively, keep the current flat layout but add `pyproject.toml` pointing to it. This is lower risk.

### 3. Expand `.gitignore`

Add standard Python ignores:

```
*.pyc
*.pyo
__pycache__/
.ipynb_checkpoints/
*.egg-info/
dist/
build/
.eggs/
.venv/
.pytest_cache/
htmlcov/
.coverage
.mypy_cache/
```

### 4. Pin dependency ranges

Use minimum version pins (`>=`) rather than exact pins to allow flexibility while preventing known-incompatible versions.

## Acceptance Criteria

- [ ] `pip install -e .` works from the project root
- [ ] `pip install -e ".[dev]"` installs test dependencies
- [ ] All existing imports continue to work
- [ ] `.gitignore` covers standard Python artifacts
