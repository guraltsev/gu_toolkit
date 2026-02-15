#!/usr/bin/env python3
"""Install local fallback test tooling for restricted Codex environments.

If pytest-cov is unavailable and the environment cannot download from package
indexes, install a tiny local pytest plugin shim that accepts --cov flags so
existing commands keep working.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> int:
    if _has_module("pytest_cov"):
        print("pytest-cov is already available.")
        return 0

    if _has_module("pytest_cov_shim"):
        print("pytest-cov shim is already available.")
        return 0

    repo_root = Path(__file__).resolve().parents[1]
    shim_dir = repo_root / ".environment" / "pytest_cov_shim"
    if not shim_dir.exists():
        print(f"pytest-cov shim directory not found: {shim_dir}")
        return 1

    print("pytest-cov is unavailable; installing local shim plugin...")
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-build-isolation",
        "--no-deps",
        "-e",
        str(shim_dir),
    ]
    subprocess.check_call(cmd)
    print("Installed local pytest-cov shim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
