from __future__ import annotations

# Find where the package root is
import sys
from pathlib import Path

try:
    _start = Path(__file__).resolve().parent
except NameError:
    _start = Path.cwd().resolve()

_pkg_root = _start
while _pkg_root != _pkg_root.parent and not (_pkg_root / "__init__.py").exists():
    _pkg_root = _pkg_root.parent
sys.path.insert(0, str(_pkg_root.parent))