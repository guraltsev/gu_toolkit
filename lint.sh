#!/bin/bash
# Lint and format check script for local development
# Run this before committing to ensure code quality

echo "=== Running ruff format check ==="
if ! ruff format --check .; then
    echo ""
    echo "ERROR: Formatting issues found. Run 'ruff format .' to fix them."
    exit 1
fi

echo ""
echo "=== Running ruff check ==="
if ! ruff check .; then
    echo ""
    echo "ERROR: Linting issues found. Run 'ruff check --fix .' to auto-fix some of them."
    exit 1
fi

echo ""
echo "=== Running mypy (informational) ==="
mypy . || {
    echo ""
    echo "Note: mypy found type errors. These are informational and don't block commits."
    echo "Please review and fix when possible."
}

echo ""
echo "=== Pre-commit checks complete! ==="
