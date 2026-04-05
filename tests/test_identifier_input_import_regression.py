from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"


def test_identifier_input_imports_when_anywidget_wraps_base_assets() -> None:
    script = r'''
import sys
import types
import traitlets

sys.path.insert(0, r"__SRC_DIR__")

class _WrappedAsset:
    def __init__(self, value):
        self.value = value


class _FakeAnyWidget(traitlets.HasTraits):
    layout = traitlets.Any()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for key in ("_esm", "_css"):
            if key in cls.__dict__:
                setattr(cls, key, _WrappedAsset(getattr(cls, key)))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


fake_anywidget = types.ModuleType("anywidget")
fake_anywidget.AnyWidget = _FakeAnyWidget
sys.modules["anywidget"] = fake_anywidget

from gu_toolkit import IdentifierInput, MathInput

assert hasattr(MathInput._esm, "value")
assert hasattr(IdentifierInput._esm, "value")
'''.replace("__SRC_DIR__", str(SRC_DIR))

    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
