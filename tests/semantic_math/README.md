# Semantic math test suite

This folder isolates the tests for the two refactoring targets in this change:

1. the canonical / robust identifier system
2. the figure-independent MathLive input widgets and transport layer

The goal is not only to catch regressions, but also to explain the intended
architecture. Each test module starts with a narrative docstring that states
what contract is being protected and why that contract matters.

## Contents

- `test_identifier_policy.py` — low-level canonical identifier grammar,
  rendering, parsing, and compatibility imports.
- `test_expression_context.py` — context-aware parsing and rendering rules that
  make known identifiers stay atomic.
- `test_mathlive_inputs.py` — widget-facing MathJSON transport, public MathLive
  boundaries, and compatibility imports.
- `test_symbolic_identifier_families.py` — higher-level symbolic helpers that
  must enforce the same identifier rules as the low-level layer.
- `test_showcase_notebooks.py` — executable checks that the showcase notebooks
  remain markdown-heavy, figure-free teaching artifacts.

## Running just this slice

```bash
PYTHONPATH=src pytest tests/semantic_math -q
```
