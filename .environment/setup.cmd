@echo off
setlocal

if exist requirements.txt (
  python -m pip install -r requirements.txt
) else (
  echo requirements.txt not found; skipping dependency installation.
)
