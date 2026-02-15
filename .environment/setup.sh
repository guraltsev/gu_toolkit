#!/usr/bin/env bash
set -euo pipefail

if [[ -f requirements.txt ]]; then
  python -m pip install -r requirements.txt
else
  echo "requirements.txt not found; skipping dependency installation."
fi
