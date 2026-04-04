"""Executable checks for the semantic math showcase notebooks.

The notebooks are part tutorial and part executable specification. These tests
ensure they stay:

- markdown-first teaching artifacts
- focused on the identifier + MathLive stack rather than on figures
- runnable as lightweight integration examples
"""

from __future__ import annotations

import json
from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient


REPO_ROOT = Path(__file__).resolve().parents[2]
MATHLIVE_NOTEBOOK = REPO_ROOT / "examples" / "MathLive_identifier_system_showcase.ipynb"
IDENTIFIER_NOTEBOOK = REPO_ROOT / "examples" / "Robust_identifier_system_showcase.ipynb"


@pytest.mark.parametrize(
    ("path", "required_phrases"),
    [
        (
            MATHLIVE_NOTEBOOK,
            ["ExpressionInput", "IdentifierInput", "transport_manifest", "MathJSON", "mathjson_to_identifier"],
        ),
        (
            IDENTIFIER_NOTEBOOK,
            ["validate_identifier", "identifier_to_latex", "parse_identifier", "IdentifierError", "gu_toolkit.Symbolic"],
        ),
    ],
)
def test_showcase_notebooks_are_markdown_first_and_cover_their_topic(path: Path, required_phrases: list[str]) -> None:
    """Each showcase notebook should explain more than it codes and cover its advertised surface area."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    markdown_cells = [cell for cell in raw["cells"] if cell["cell_type"] == "markdown"]
    code_cells = [cell for cell in raw["cells"] if cell["cell_type"] == "code"]
    text = "\n".join("".join(cell.get("source", [])) for cell in raw["cells"])

    assert len(markdown_cells) >= len(code_cells)
    assert len(markdown_cells) >= 6
    assert "#BUG" not in text
    assert "# BUG" not in text
    assert "%pip" not in text
    assert "from gu_toolkit import Figure" not in text
    assert "Figure(" not in text
    for phrase in required_phrases:
        assert phrase in text


@pytest.mark.parametrize("path", [MATHLIVE_NOTEBOOK, IDENTIFIER_NOTEBOOK])
def test_showcase_notebooks_execute_successfully(path: Path) -> None:
    """The notebooks should remain runnable, not just readable."""

    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(
        notebook,
        kernel_name="python3",
        timeout=120,
        resources={"metadata": {"path": str(path.parent)}},
    )
    client.execute()
