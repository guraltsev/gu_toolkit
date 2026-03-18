from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_NOTEBOOK = (
    Path(__file__).resolve().parents[1] / "docs" / "notebooks" / "layout_debug.ipynb"
)


def _load_notebook() -> dict[str, Any]:
    return json.loads(_NOTEBOOK.read_text(encoding="utf-8"))


def _code_sources(nb: dict[str, Any]) -> list[str]:
    return [
        "".join(cell.get("source", []))
        for cell in nb.get("cells", [])
        if cell.get("cell_type") == "code"
    ]


def _output_texts(nb: dict[str, Any]) -> list[str]:
    rendered: list[str] = []
    for cell in nb.get("cells", []):
        for output in cell.get("outputs", []):
            text = output.get("text")
            if isinstance(text, str):
                rendered.append(text)
            elif isinstance(text, list):
                rendered.append("".join(text))

            traceback = output.get("traceback")
            if isinstance(traceback, list):
                rendered.append("".join(traceback))

            for value in output.get("data", {}).values():
                if isinstance(value, str):
                    rendered.append(value)
                elif isinstance(value, list):
                    rendered.append("".join(value))
    return rendered


def test_layout_debug_tree_cell_uses_defined_figure_lab_variable() -> None:
    nb = _load_notebook()
    sources = _code_sources(nb)

    assert any("figure_lab = build_figure_lab()" in src for src in sources)
    assert any(
        'show_tree(figure_lab["figure"]._layout.root_widget, max_depth=4)' in src
        for src in sources
    )
    assert not any("smartfigure_lab" in src for src in sources)


def test_layout_debug_notebook_has_no_stale_sidebar_failure_or_nameerror() -> None:
    nb = _load_notebook()
    outputs = "\n".join(_output_texts(nb))

    assert "smartfigure_lab" not in outputs
    assert "failed: sidebar_visible, info_box_visible" not in outputs
