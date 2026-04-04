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


def _cell_source(cell: dict[str, object]) -> str:
    return "".join(cell.get("source", []))


def _is_comment_only_code_cell(cell: dict[str, object]) -> bool:
    if cell.get("cell_type") != "code":
        return False
    lines = [line.strip() for line in _cell_source(cell).splitlines() if line.strip()]
    return bool(lines) and all(line.startswith("#") for line in lines)


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
    assert not any(_is_comment_only_code_cell(cell) for cell in code_cells)
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


def test_mathlive_showcase_places_working_widgets_before_transport_internals() -> None:
    """The tutorial should demonstrate successful widget workflows before raw transport details."""

    raw = json.loads(MATHLIVE_NOTEBOOK.read_text(encoding="utf-8"))
    cells = raw["cells"]
    widget_cells = [
        index
        for index, cell in enumerate(cells)
        if cell["cell_type"] == "code"
        and ("IdentifierInput(" in _cell_source(cell) or "ExpressionInput(" in _cell_source(cell))
    ]
    manifest_cells = [
        index
        for index, cell in enumerate(cells)
        if cell["cell_type"] == "code" and "transport_manifest(" in _cell_source(cell)
    ]
    text = "\n".join(_cell_source(cell) for cell in cells)

    assert widget_cells
    assert manifest_cells
    assert min(widget_cells) < min(manifest_cells)
    assert ".get_state(" not in text
    for token in ("fieldRole", "latexHead", "template"):
        assert token in text


def test_mathlive_showcase_separates_identifier_manual_demo_from_regression_checks() -> None:
    """The manual IdentifierInput walkthrough should remain visible and distinct from the kernel-side regression path."""

    raw = json.loads(MATHLIVE_NOTEBOOK.read_text(encoding="utf-8"))
    cells = raw["cells"]

    manual_widget_cell = next(
        index
        for index, cell in enumerate(cells)
        if cell["cell_type"] == "code" and "display(identifier_widget)" in _cell_source(cell)
    )
    injection_cell = next(
        index
        for index, cell in enumerate(cells)
        if cell["cell_type"] == "code"
        and "display(Javascript(" in _cell_source(cell)
        and "Identifier demo input" in _cell_source(cell)
    )
    feedback_cell = next(
        index
        for index, cell in enumerate(cells)
        if cell["cell_type"] == "code" and "Current canonical identifier" in _cell_source(cell)
    )
    regression_cell = next(
        index
        for index, cell in enumerate(cells)
        if cell["cell_type"] == "code" and "identifier_regression_widget = IdentifierInput" in _cell_source(cell)
    )
    text = "\n".join(_cell_source(cell) for cell in cells)

    assert manual_widget_cell < injection_cell < feedback_cell < regression_cell
    assert "assert" not in _cell_source(cells[manual_widget_cell])
    assert "kernel-side" in text
    assert "Current canonical identifier" in text
    assert "identifier_widget.math_json =" not in _cell_source(cells[regression_cell])


def test_mathlive_showcase_uses_fresh_widgets_for_transport_regressions() -> None:
    """The MathJSON regression cells should not mutate the earlier visible teaching widgets."""

    raw = json.loads(MATHLIVE_NOTEBOOK.read_text(encoding="utf-8"))
    cells = raw["cells"]

    identifier_regression_cell = next(
        cell
        for cell in cells
        if cell["cell_type"] == "code" and "identifier_regression_widget = IdentifierInput" in _cell_source(cell)
    )
    expression_regression_cell = next(
        cell
        for cell in cells
        if cell["cell_type"] == "code" and "expression_mathjson_widget = ExpressionInput" in _cell_source(cell)
    )

    assert "identifier_widget.value =" not in _cell_source(identifier_regression_cell)
    assert "expression_widget.value =" not in _cell_source(expression_regression_cell)
    assert "expression_widget.math_json =" not in _cell_source(expression_regression_cell)


def test_mathlive_showcase_explains_sympy_rendering_and_empty_mathjson_behavior() -> None:
    """The notebook should explain the rendering boundary, stale-transport fallback, and the empty-input contract explicitly."""

    text = MATHLIVE_NOTEBOOK.read_text(encoding="utf-8")

    assert "SymPy is still the printer of record" in text
    assert "sp.latex(parsed_from_text, symbol_names=ctx.symbol_name_map(parsed_from_text))" in text
    assert "current visible field state" in text
    assert "stale" in text.lower()
    assert "number `0`" in text
    assert "identifier named `Nothing`" in text
