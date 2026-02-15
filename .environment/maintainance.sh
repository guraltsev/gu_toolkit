#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip

if [[ -f requirements.txt ]]; then
  python -m pip install -r requirements.txt
else
  echo "requirements.txt not found; skipping dependency installation."
fi

python ./.environment/install_test_tools.py
