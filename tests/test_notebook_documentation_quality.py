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

    placeholder_pattern = re.compile(r"(^|\s)(#\s*bug\b|bug\s*:|bug stack trace\s*:)", re.IGNORECASE)
    offenders: list[tuple[int, str]] = []

    for index, cell in enumerate(notebook.get("cells", [])):
        source_text = "".join(cell.get("source", []))
        if placeholder_pattern.search(source_text):
            offenders.append((index, source_text.strip().splitlines()[0]))

    assert offenders == [], f"Found placeholder BUG markers in notebook cells: {offenders}"


def test_toolkit_overview_callable_section_has_no_captured_missing_x_traceback() -> None:
    """Ensure the notebook does not publish historical issue-023 traceback output.

    The callable-first tutorial previously included a pasted ``KeyError`` stack trace
    describing missing ``x`` in ``parameter_context``. The rendered notebook should
    present runnable examples and guidance, not historical failure output.
    """
    notebook_path = Path("docs/notebooks/Toolkit_overview.ipynb")
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

    traceback_pattern = re.compile(
        r"KeyError\s*:.*parameter_context\s+is\s+missing\s+symbol\s+x",
        re.IGNORECASE | re.DOTALL,
    )

    offenders: list[tuple[int, str]] = []
    for index, cell in enumerate(notebook.get("cells", [])):
        source_text = "".join(cell.get("source", []))
        if traceback_pattern.search(source_text):
            offenders.append((index, source_text.strip().splitlines()[0]))

    assert offenders == [], (
        "Found stale issue-023 traceback content in notebook cells: "
        f"{offenders}"
    )
