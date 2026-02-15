@echo off
setlocal

python -m pip install --upgrade pip
if errorlevel 1 exit /b %errorlevel%

if exist requirements.txt (
  python -m pip install -r requirements.txt
) else (
  echo requirements.txt not found; skipping dependency installation.
)
if errorlevel 1 exit /b %errorlevel%

python .environment\install_test_tools.py
