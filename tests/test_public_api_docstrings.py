from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / 'src' / 'gu_toolkit'

REQUIRED_HEADINGS = (
    'Full API',
    'Parameters',
    'Returns',
    'Optional arguments',
    'Architecture note',
    'Examples',
    'Learn more / explore',
)


def iter_public_api_nodes(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_'):
            yield node
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith('_'):
                yield node
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and not member.name.startswith('_'):
                    yield member



def test_every_source_module_has_a_module_docstring() -> None:
    for path in sorted(SRC_ROOT.glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        assert ast.get_docstring(tree), f'{path} is missing a module docstring'



def test_public_api_docstrings_use_the_uniform_structure() -> None:
    for path in sorted(SRC_ROOT.glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in iter_public_api_nodes(tree):
            doc = ast.get_docstring(node)
            assert doc, f'{path}:{getattr(node, "name", "<module>")} is missing a docstring'
            for heading in REQUIRED_HEADINGS:
                assert heading in doc, (
                    f'{path}:{getattr(node, "name", "<module>")} is missing the section '
                    f'{heading!r}'
                )
