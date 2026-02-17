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
# Run ruff check and capture output
RUFF_OUTPUT=$(ruff check . 2>&1)
RUFF_EXIT=$?
echo "$RUFF_OUTPUT"

# Extract error count from output
ERROR_COUNT=$(echo "$RUFF_OUTPUT" | grep -oP 'Found \K\d+(?= errors)' || echo "0")

# Allow up to 150 errors (current baseline is 147, mostly from notebooks)
if [ "$ERROR_COUNT" -gt "150" ]; then
    echo ""
    echo "ERROR: Too many linting issues ($ERROR_COUNT > 150 allowed)."
    echo "Run 'ruff check --fix .' to auto-fix some of them."
    exit 1
elif [ "$RUFF_EXIT" -eq "0" ]; then
    echo ""
    echo "All linting checks passed!"
else
    echo ""
    echo "Linting passed with $ERROR_COUNT known issues (within threshold of 150)."
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
