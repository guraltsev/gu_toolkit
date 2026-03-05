from __future__ import annotations

import sys
from pathlib import Path

_START = Path(__file__).resolve().parent
_repo_root = _START
while _repo_root != _repo_root.parent and not (_repo_root / "pyproject.toml").exists():
    _repo_root = _repo_root.parent

_src = _repo_root / "src"
sys.path.insert(0, str(_src if _src.exists() else _repo_root))