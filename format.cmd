@echo off
REM Auto-format and fix script for local development (Windows)
REM Run this to automatically fix formatting and some linting issues

echo === Running ruff format ===
ruff format .

echo.
echo === Running ruff check --fix ===
ruff check --fix .

echo.
echo === Formatting and auto-fixes complete! ===
echo Note: Some issues may require manual fixes. Run 'lint.cmd' to check.
