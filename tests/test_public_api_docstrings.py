from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "gu_toolkit"
GUIDES_ROOT = REPO_ROOT / "docs" / "guides"

REQUIRED_HEADINGS = (
    "Full API",
    "Parameters",
    "Returns",
    "Optional arguments",
    "Architecture note",
    "Examples",
    "Learn more / explore",
)

PLACEHOLDER_PHRASES = (
    "This API accepts the parameters declared in its Python signature.",
    "Result produced by this API.",
    "examples/Toolkit_overview.ipynb",
    "obj = ",
    "result = ",
)

SEMANTIC_MATH_FILES = (
    SRC_ROOT / "identifiers" / "policy.py",
    SRC_ROOT / "mathlive" / "context.py",
    SRC_ROOT / "mathlive" / "transport.py",
    SRC_ROOT / "mathlive" / "inputs.py",
)

REPRESENTATIVE_SEMANTIC_MATH_APIS = {
    SRC_ROOT / "identifiers" / "policy.py": (
        "identifier_to_latex",
        "symbol",
    ),
    SRC_ROOT / "mathlive" / "context.py": (
        "ExpressionContext",
        "ExpressionContext.from_symbols",
        "ExpressionContext.transport_manifest",
    ),
    SRC_ROOT / "mathlive" / "transport.py": (
        "build_mathlive_transport_manifest",
        "mathjson_to_identifier",
    ),
    SRC_ROOT / "mathlive" / "inputs.py": (
        "IdentifierInput",
        "IdentifierInput.parse_value",
        "ExpressionInput",
        "ExpressionInput.parse_value",
    ),
}

REQUIRED_SEMANTIC_LINKS = (
    "docs/guides/api-discovery.md",
    "docs/guides/semantic-math-refactoring-philosophy.md",
    "examples/MathLive_identifier_system_showcase.ipynb",
)


def iter_source_modules() -> list[Path]:
    return sorted(path for path in SRC_ROOT.rglob("*.py") if "__pycache__" not in path.parts)



def parse_module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))



def iter_public_api_nodes(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            yield node
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                yield node
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and not member.name.startswith("_"):
                    yield member



def docstrings_by_qualname(path: Path) -> dict[str, str]:
    tree = parse_module(path)
    docs = {"<module>": ast.get_docstring(tree) or ""}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docs[node.name] = ast.get_docstring(node) or ""
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        docs[f"{node.name}.{member.name}"] = ast.get_docstring(member) or ""
    return docs



def test_every_source_module_has_a_module_docstring() -> None:
    for path in iter_source_modules():
        tree = parse_module(path)
        assert ast.get_docstring(tree), f"{path} is missing a module docstring"



def test_public_api_docstrings_use_the_uniform_structure() -> None:
    for path in iter_source_modules():
        tree = parse_module(path)
        for node in iter_public_api_nodes(tree):
            doc = ast.get_docstring(node)
            assert doc, f"{path}:{getattr(node, 'name', '<module>')} is missing a docstring"
            for heading in REQUIRED_HEADINGS:
                assert heading in doc, (
                    f"{path}:{getattr(node, 'name', '<module>')} is missing the section "
                    f"{heading!r}"
                )



def test_recursive_docstring_scan_reaches_semantic_math_modules() -> None:
    scanned = set(iter_source_modules())
    assert set(SEMANTIC_MATH_FILES).issubset(scanned)



def test_semantic_math_docstrings_avoid_placeholders_and_link_to_targeted_resources() -> None:
    for path, qualnames in REPRESENTATIVE_SEMANTIC_MATH_APIS.items():
        docs = docstrings_by_qualname(path)
        for qualname in qualnames:
            doc = docs.get(qualname)
            assert doc, f"{path}:{qualname} is missing a docstring"
            for phrase in PLACEHOLDER_PHRASES:
                assert phrase not in doc, f"{path}:{qualname} still contains placeholder text {phrase!r}"
            for link in REQUIRED_SEMANTIC_LINKS:
                assert link in doc, f"{path}:{qualname} is missing semantic-math cross-reference {link!r}"
            assert "tests/semantic_math/" in doc, (
                f"{path}:{qualname} should point to focused semantic-math regression tests"
            )



def test_api_discovery_guide_includes_semantic_math_navigation_entry() -> None:
    guide = (GUIDES_ROOT / "api-discovery.md").read_text(encoding="utf-8")
    assert "Author semantic identifiers and MathLive-backed expressions" in guide
    for token in (
        "symbol",
        "ExpressionContext",
        "IdentifierInput",
        "ExpressionInput",
        "mathjson_to_identifier",
        "build_mathlive_transport_manifest",
        "docs/guides/semantic-math-refactoring-philosophy.md",
        "examples/MathLive_identifier_system_showcase.ipynb",
        "tests/semantic_math/test_identifier_policy.py",
        "tests/semantic_math/test_expression_context.py",
        "tests/semantic_math/test_mathlive_inputs.py",
        "**Semantic math / MathLive**",
    ):
        assert token in guide
