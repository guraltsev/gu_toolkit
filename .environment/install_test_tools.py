#!/usr/bin/env python3
"""Install local fallback test tooling for restricted Codex environments.

If pytest-cov is unavailable and the environment cannot download from package
indexes, install a tiny local pytest plugin shim that accepts --cov flags so
existing commands keep working.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import subprocess
import sys
from pathlib import Path


def _has_module(name: str) -> bool:
    """Return True when *name* is importable in the active environment."""
    return importlib.util.find_spec(name) is not None


def _has_distribution(name: str) -> bool:
    """Return True when a distribution is installed in the active environment."""
    try:
        importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return False
    return True


def _pip_install(args: list[str]) -> None:
    cmd = [sys.executable, "-m", "pip", "install", *args]
    subprocess.check_call(cmd)


def _ensure_pytest_cov() -> bool:
    """Install pytest-cov when possible, returning True on success."""
    if _has_module("pytest_cov") and _has_distribution("pytest-cov"):
        print("pytest-cov is already available.")
        return True

    print("pytest-cov is unavailable; attempting to install pytest-cov...")
    try:
        _pip_install(["pytest-cov>=5"])
    except subprocess.CalledProcessError:
        print("Could not install pytest-cov from package indexes.")
        return False

    if _has_module("pytest_cov") and _has_distribution("pytest-cov"):
        print("Installed pytest-cov.")
        return True

    print("pytest-cov installation completed but module is still unavailable.")
    return False


def main() -> int:
    if _ensure_pytest_cov():
        return 0

    # Verify installed package/module, not just repository folder names.
    if _has_module("pytest_cov_shim.plugin") and _has_distribution("pytest-cov-shim"):
        print("pytest-cov shim is already available.")
        return 0

    repo_root = Path(__file__).resolve().parents[1]
    shim_dir = repo_root / ".environment" / "pytest_cov_shim"
    if not shim_dir.exists():
        print(f"pytest-cov shim directory not found: {shim_dir}")
        return 1

    print("pytest-cov is unavailable; installing local shim plugin...")
    _pip_install(["--no-build-isolation", "--no-deps", "-e", str(shim_dir)])
    print("Installed local pytest-cov shim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
