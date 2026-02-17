from __future__ import annotations

import json
import re
from pathlib import Path


def test_toolkit_overview_notebook_has_no_placeholder_bug_markers() -> None:
    """Ensure published notebook content does not ship with placeholder BUG notes.

    Issue-028 tracks regression where user-facing guidance cells were replaced by
    temporary ``# BUG ...`` markers. This test scans both code and markdown cell
    sources and fails if placeholder markers reappear.
    """
    notebook_path = Path("docs/notebooks/Toolkit_overview.ipynb")
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

    placeholder_pattern = re.compile(r"(^|\s)#\s*bug\b", re.IGNORECASE)
    offenders: list[tuple[int, str]] = []

    for index, cell in enumerate(notebook.get("cells", [])):
        source_text = "".join(cell.get("source", []))
        if placeholder_pattern.search(source_text):
            offenders.append((index, source_text.strip().splitlines()[0]))

    assert offenders == [], f"Found placeholder BUG markers in notebook cells: {offenders}"
