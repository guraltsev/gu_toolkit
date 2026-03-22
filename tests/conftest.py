from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_START = Path(__file__).resolve().parent
_repo_root = _START
while _repo_root != _repo_root.parent and not (_repo_root / "pyproject.toml").exists():
    _repo_root = _repo_root.parent

_src = _repo_root / "src"
sys.path.insert(0, str(_src if _src.exists() else _repo_root))

_widget_stubs_path = _src / "gu_toolkit" / "_widget_stubs.py"
if _widget_stubs_path.exists():
    spec = importlib.util.spec_from_file_location(
        "gu_toolkit._widget_stubs", _widget_stubs_path
    )
    if spec is not None and spec.loader is not None:
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("gu_toolkit._widget_stubs", module)
        spec.loader.exec_module(module)
        module.install_widget_stubs()
