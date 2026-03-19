from __future__ import annotations

import sys
from pathlib import Path

try:
    _start = Path(__file__).resolve().parent
except NameError:
    _start = Path.cwd().resolve()

_repo_root = _start
while _repo_root != _repo_root.parent and not (_repo_root / ".root").exists():
    _repo_root = _repo_root.parent

sys.path.insert(0,str(_repo_root))

_src = _repo_root / "src"
if _src.exists():
    sys.path.insert(0, str(_src))

