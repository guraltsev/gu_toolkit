from __future__ import annotations

import sys
from pathlib import Path

_START = Path(__file__).resolve().parent
_pkg_root = _START
while _pkg_root != _pkg_root.parent and not (_pkg_root / "__init__.py").exists():
    _pkg_root = _pkg_root.parent

sys.path.insert(0, str(_pkg_root.parent))
