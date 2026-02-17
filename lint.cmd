@echo off
REM Lint and format check script for local development (Windows)
REM Run this before committing to ensure code quality

echo === Running ruff format check ===
ruff format --check .
if errorlevel 1 (
    echo.
    echo ERROR: Formatting issues found. Run 'ruff format .' to fix them.
    exit /b 1
)

echo.
echo === Running ruff check ===
ruff check .
if errorlevel 1 (
    echo.
    echo ERROR: Linting issues found. Run 'ruff check --fix .' to auto-fix some of them.
    exit /b 1
)

echo.
echo === Running mypy (informational) ===
mypy .
if errorlevel 1 (
    echo.
    echo Note: mypy found type errors. These are informational and don't block commits.
    echo Please review and fix when possible.
)

echo.
echo === Pre-commit checks complete! ===
