"""Canonical identifier rules, rendering helpers, and reversible parsing.

This module centralizes the toolkit's identifier semantics so symbolic identity
stays separate from presentation. Canonical identifiers are plain validated
strings (for example ``velocity``, ``a_1_2`` or ``theta__x``); display LaTeX is
always derived from those names rather than stored in ``Symbol.name``.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from typing import Any, Iterable

import sympy as sp

__all__ = [
    "CANONICAL_IDENTIFIER_RE",
    "ExpressionRenderContext",
    "IdentifierError",
    "build_symbol_names",
    "encode_identifier_atoms",
    "function_head_to_latex",
    "function_latex_method",
    "identifier_to_latex",
    "parse_identifier",
    "register_symbol_latex",
    "render_latex",
    "rewrite_wrapped_identifier_calls",
    "semantic_function",
    "split_identifier_atoms",
    "strip_math_delimiters",
    "symbol",
    "symbol_latex_override",
    "validate_identifier",
]


CANONICAL_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_ATOM_TEXT_RE = re.compile(r"^[A-Za-z0-9_]+$")
_ALPHA_ATOM_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_DIGIT_ATOM_RE = re.compile(r"^[0-9]+$")


_GREEK_NAME_TO_LATEX: dict[str, str] = {
    "alpha": r"\alpha",
    "beta": r"\beta",
    "gamma": r"\gamma",
    "delta": r"\delta",
    "epsilon": r"\epsilon",
    "varepsilon": r"\varepsilon",
    "zeta": r"\zeta",
    "eta": r"\eta",
    "theta": r"\theta",
    "vartheta": r"\vartheta",
    "iota": r"\iota",
    "kappa": r"\kappa",
    "lambda": r"\lambda",
    "mu": r"\mu",
    "nu": r"\nu",
    "xi": r"\xi",
    "omicron": r"o",
    "pi": r"\pi",
    "rho": r"\rho",
    "sigma": r"\sigma",
    "tau": r"\tau",
    "upsilon": r"\upsilon",
    "phi": r"\phi",
    "varphi": r"\varphi",
    "chi": r"\chi",
    "psi": r"\psi",
    "omega": r"\omega",
    "Gamma": r"\Gamma",
    "Delta": r"\Delta",
    "Theta": r"\Theta",
    "Lambda": r"\Lambda",
    "Xi": r"\Xi",
    "Pi": r"\Pi",
    "Sigma": r"\Sigma",
    "Upsilon": r"\Upsilon",
    "Phi": r"\Phi",
    "Psi": r"\Psi",
    "Omega": r"\Omega",
}

_GREEK_LATEX_TO_NAME = {value: key for key, value in _GREEK_NAME_TO_LATEX.items()}
_IDENTIFIER_LATEX_COMMANDS: dict[str, str] = {
    **{name: name for name in _GREEK_NAME_TO_LATEX},
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "cot": "cot",
    "sec": "sec",
    "csc": "csc",
    "sinh": "sinh",
    "cosh": "cosh",
    "tanh": "tanh",
    "log": "log",
    "ln": "ln",
    "exp": "exp",
}

_EXPLICIT_MACRO_IDENTIFIERS = {"lambda", "Lambda"}
_SYMBOL_LATEX_OVERRIDES: dict[str, str] = {}
_SEMANTIC_FUNCTION_CACHE: dict[str, type[sp.Function]] = {}


class IdentifierError(ValueError):
    """Public semantic-math helper class for IdentifierError.
    
    Full API
    --------
    ``IdentifierError``
    
    Parameters
    ----------
    Constructor parameters follow the Python signature for this class.
    
    Returns
    -------
    IdentifierError
        New ``IdentifierError`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        obj = IdentifierError(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(IdentifierError)`` and inspect neighboring APIs in the same module.
    """


@dataclass(frozen=True)
class IdentifierScanResult:
    """Public semantic-math helper class for IdentifierScanResult.
    
    Full API
    --------
    ``IdentifierScanResult``
    
    Parameters
    ----------
    Constructor parameters follow the Python signature for this class.
    
    Returns
    -------
    IdentifierScanResult
        New ``IdentifierScanResult`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        obj = IdentifierScanResult(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(IdentifierScanResult)`` and inspect neighboring APIs in the same module.
    """

    canonical: str
    end: int
    explicit: bool


@dataclass(frozen=True)
class ExpressionRenderContext:
    """Public semantic-math helper class for ExpressionRenderContext.
    
    Full API
    --------
    ``ExpressionRenderContext``
    
    Parameters
    ----------
    Constructor parameters follow the Python signature for this class.
    
    Returns
    -------
    ExpressionRenderContext
        New ``ExpressionRenderContext`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        obj = ExpressionRenderContext(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(ExpressionRenderContext)`` and inspect neighboring APIs in the same module.
    """

    symbol_names: dict[sp.Symbol, str]


def strip_math_delimiters(text: str) -> str:
    """Public semantic-math helper callable for strip_math_delimiters.
    
    Full API
    --------
    ``strip_math_delimiters(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = strip_math_delimiters(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(strip_math_delimiters)`` and inspect neighboring APIs in the same module.
    """

    stripped = str(text or "").strip()
    if len(stripped) >= 2 and stripped[0] == "$" and stripped[-1] == "$":
        return stripped[1:-1].strip()
    if stripped.startswith(r"\(") and stripped.endswith(r"\)"):
        return stripped[2:-2].strip()
    if stripped.startswith(r"\[") and stripped.endswith(r"\]"):
        return stripped[2:-2].strip()
    return stripped


def validate_identifier(name: str, *, role: str = "identifier") -> str:
    """Public semantic-math helper callable for validate_identifier.
    
    Full API
    --------
    ``validate_identifier(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = validate_identifier(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(validate_identifier)`` and inspect neighboring APIs in the same module.
    """

    text = str(name or "").strip()
    if not CANONICAL_IDENTIFIER_RE.match(text):
        raise IdentifierError(
            f"{role.capitalize()} must match {CANONICAL_IDENTIFIER_RE.pattern!r}, got {text!r}."
        )
    split_identifier_atoms(text, _validated=True)
    return text


def split_identifier_atoms(name: str, *, _validated: bool = False) -> tuple[str, ...]:
    """Public semantic-math helper callable for split_identifier_atoms.
    
    Full API
    --------
    ``split_identifier_atoms(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = split_identifier_atoms(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(split_identifier_atoms)`` and inspect neighboring APIs in the same module.
    """

    text = str(name or "").strip()
    if not _validated:
        validate_identifier(text)

    atoms: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char != "_":
            current.append(char)
            index += 1
            continue

        if index + 1 < len(text) and text[index + 1] == "_":
            current.append("_")
            index += 2
            continue

        if not current:
            raise IdentifierError(f"Invalid identifier {text!r}: empty atom before '_' .")
        atoms.append("".join(current))
        current = []
        index += 1

    if not current:
        raise IdentifierError(f"Invalid identifier {text!r}: trailing '_' is not allowed.")
    atoms.append("".join(current))
    return tuple(atoms)


def encode_identifier_atoms(atoms: Iterable[str], *, role: str = "identifier") -> str:
    """Public semantic-math helper callable for encode_identifier_atoms.
    
    Full API
    --------
    ``encode_identifier_atoms(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = encode_identifier_atoms(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(encode_identifier_atoms)`` and inspect neighboring APIs in the same module.
    """

    pieces = [str(atom).strip() for atom in atoms]
    if not pieces or not pieces[0]:
        raise IdentifierError(f"{role.capitalize()} must contain at least one atom.")

    encoded = []
    for index, atom in enumerate(pieces):
        if not atom:
            raise IdentifierError(f"{role.capitalize()} cannot contain empty atoms.")
        if not _ATOM_TEXT_RE.match(atom):
            raise IdentifierError(
                f"{role.capitalize()} atom {atom!r} may only contain letters, digits, and underscores."
            )
        if index == 0 and atom[0].isdigit():
            raise IdentifierError(f"{role.capitalize()} must start with a letter, got {atom!r}.")
        encoded.append(atom.replace("_", "__"))

    return validate_identifier("_".join(encoded), role=role)


def _escape_math_text_atom(atom: str) -> str:
    return atom.replace("_", r"\_")


def _render_atom(atom: str, *, text_command: str = "mathrm") -> str:
    if "_" in atom:
        return rf"\{text_command}{{{_escape_math_text_atom(atom)}}}"
    if atom in _GREEK_NAME_TO_LATEX:
        return _GREEK_NAME_TO_LATEX[atom]
    if atom.isdigit():
        return atom
    if len(atom) == 1:
        return atom
    return rf"\{text_command}{{{atom}}}"


def _render_identifier(name: str, *, text_command: str, role: str) -> str:
    atoms = split_identifier_atoms(validate_identifier(name, role=role))
    base = _render_atom(atoms[0], text_command=text_command)
    if len(atoms) == 1:
        return base
    subscript = ",".join(_render_atom(atom, text_command=text_command) for atom in atoms[1:])
    return f"{base}_{{{subscript}}}"


def identifier_to_latex(name: str, *, latex_expr: str | None = None) -> str:
    """Public semantic-math helper callable for identifier_to_latex.
    
    Full API
    --------
    ``identifier_to_latex(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = identifier_to_latex(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(identifier_to_latex)`` and inspect neighboring APIs in the same module.
    """

    if latex_expr is not None:
        text = str(latex_expr).strip()
        if text:
            return text
    return _render_identifier(name, text_command="mathrm", role="identifier")


def symbol(name: str, *, latex_expr: str | None = None, **kwargs: Any) -> sp.Symbol:
    """Public semantic-math helper callable for symbol.
    
    Full API
    --------
    ``symbol(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = symbol(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(symbol)`` and inspect neighboring APIs in the same module.
    """

    canonical = validate_identifier(name, role="symbol")
    if latex_expr is not None:
        register_symbol_latex(canonical, latex_expr)
    return sp.Symbol(canonical, **kwargs)


def register_symbol_latex(symbol_or_name: str | sp.Symbol, latex_expr: str) -> None:
    """Public semantic-math helper callable for register_symbol_latex.
    
    Full API
    --------
    ``register_symbol_latex(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = register_symbol_latex(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(register_symbol_latex)`` and inspect neighboring APIs in the same module.
    """

    if isinstance(symbol_or_name, sp.Symbol):
        name = symbol_or_name.name
    else:
        name = str(symbol_or_name)
    canonical = validate_identifier(name, role="symbol")
    text = str(latex_expr or "").strip()
    if not text:
        _SYMBOL_LATEX_OVERRIDES.pop(canonical, None)
        return
    _SYMBOL_LATEX_OVERRIDES[canonical] = text


def symbol_latex_override(symbol_or_name: str | sp.Symbol) -> str | None:
    """Public semantic-math helper callable for symbol_latex_override.
    
    Full API
    --------
    ``symbol_latex_override(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = symbol_latex_override(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(symbol_latex_override)`` and inspect neighboring APIs in the same module.
    """

    if isinstance(symbol_or_name, sp.Symbol):
        name = symbol_or_name.name
    else:
        name = str(symbol_or_name)
    return _SYMBOL_LATEX_OVERRIDES.get(name)


def build_symbol_names(
    expr: Any,
    *,
    explicit: dict[sp.Symbol, str] | None = None,
) -> dict[sp.Symbol, str]:
    """Public semantic-math helper callable for build_symbol_names.
    
    Full API
    --------
    ``build_symbol_names(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = build_symbol_names(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(build_symbol_names)`` and inspect neighboring APIs in the same module.
    """

    mapping: dict[sp.Symbol, str] = {}
    if explicit:
        mapping.update(explicit)

    free_symbols = set(getattr(expr, "free_symbols", set()))
    if isinstance(expr, sp.Symbol):
        free_symbols.add(expr)

    for sym in free_symbols:
        if not isinstance(sym, sp.Symbol):
            continue
        if sym in mapping:
            continue
        override = symbol_latex_override(sym)
        if override is not None:
            mapping[sym] = override
            continue
        try:
            mapping[sym] = identifier_to_latex(sym.name)
        except IdentifierError:
            continue
    return mapping


def render_latex(
    expr: Any,
    *,
    symbol_names: dict[sp.Symbol, str] | None = None,
) -> str:
    """Public semantic-math helper callable for render_latex.
    
    Full API
    --------
    ``render_latex(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = render_latex(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(render_latex)`` and inspect neighboring APIs in the same module.
    """

    if isinstance(expr, str):
        return expr
    try:
        sym_expr = sp.sympify(expr)
    except Exception:
        return str(expr)
    mapping = build_symbol_names(sym_expr, explicit=symbol_names)
    if mapping:
        return sp.latex(sym_expr, symbol_names=mapping)
    return sp.latex(sym_expr)


def function_head_to_latex(name: str, *, latex_head: str | None = None) -> str:
    """Public semantic-math helper callable for function_head_to_latex.
    
    Full API
    --------
    ``function_head_to_latex(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = function_head_to_latex(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(function_head_to_latex)`` and inspect neighboring APIs in the same module.
    """

    if latex_head is not None:
        text = str(latex_head).strip()
        if text:
            return text
    return _render_identifier(name, text_command="operatorname", role="function")


def function_latex_method(self: sp.Function, printer: Any) -> str:
    """Public semantic-math helper callable for function_latex_method.
    
    Full API
    --------
    ``function_latex_method(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = function_latex_method(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(function_latex_method)`` and inspect neighboring APIs in the same module.
    """

    func = self.func
    name = getattr(func, "__gu_name__", getattr(func, "__name__", str(func)))
    latex_head = getattr(func, "__gu_latex__", None)
    head = function_head_to_latex(str(name), latex_head=latex_head)
    args = ", ".join(printer._print(arg) for arg in self.args)
    return f"{head}({args})"


def semantic_function(name: str, *, latex_head: str | None = None) -> type[sp.Function]:
    """Public semantic-math helper callable for semantic_function.
    
    Full API
    --------
    ``semantic_function(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = semantic_function(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(semantic_function)`` and inspect neighboring APIs in the same module.
    """

    canonical = validate_identifier(name, role="function")
    cached = _SEMANTIC_FUNCTION_CACHE.get(canonical)
    if cached is not None:
        if latex_head is not None:
            cached.__gu_latex__ = function_head_to_latex(canonical, latex_head=latex_head)
        return cached

    cls = sp.Function(
        canonical,
        __dict__={
            "__gu_name__": canonical,
            "__gu_latex__": function_head_to_latex(canonical, latex_head=latex_head),
            "_latex": function_latex_method,
        },
    )
    _SEMANTIC_FUNCTION_CACHE[canonical] = cls
    return cls


def _skip_spaces(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _extract_braced_group(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise IdentifierError("Expected '{' while parsing LaTeX input.")
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise IdentifierError("Unbalanced braces in LaTeX input.")


def _decode_mathrm_atom(text: str) -> str:
    decoded = text.replace(r"\_", "_").strip()
    if not decoded or not _ATOM_TEXT_RE.match(decoded):
        raise IdentifierError(f"Unsupported \\mathrm atom: {text!r}.")
    return decoded


def _parse_display_atom(text: str, start: int) -> tuple[str, int]:
    index = _skip_spaces(text, start)
    if index >= len(text):
        raise IdentifierError("Expected identifier atom.")

    if text.startswith(r"\mathrm", index) or text.startswith(r"\operatorname", index):
        command = r"\mathrm" if text.startswith(r"\mathrm", index) else r"\operatorname"
        index += len(command)
        index = _skip_spaces(text, index)
        group, index = _extract_braced_group(text, index)
        return _decode_mathrm_atom(group), index

    if text[index] == "\\":
        command_match = re.match(r"\\([A-Za-z]+)", text[index:])
        if command_match is None:
            raise IdentifierError(f"Unsupported LaTeX command near {text[index:index + 12]!r}.")
        command = command_match.group(1)
        if command not in _IDENTIFIER_LATEX_COMMANDS:
            raise IdentifierError(f"Unsupported identifier command \\{command}.")
        return _IDENTIFIER_LATEX_COMMANDS[command], index + len(command_match.group(0))

    digit_match = re.match(r"[0-9]+", text[index:])
    if digit_match is not None:
        return digit_match.group(0), index + len(digit_match.group(0))

    word_match = re.match(r"[A-Za-z][A-Za-z0-9]*", text[index:])
    if word_match is not None:
        return word_match.group(0), index + len(word_match.group(0))

    raise IdentifierError(f"Could not parse identifier atom near {text[index:index + 12]!r}.")


def _parse_display_subscript_atoms(text: str) -> tuple[str, ...]:
    index = 0
    atoms: list[str] = []
    while True:
        index = _skip_spaces(text, index)
        atom, index = _parse_display_atom(text, index)
        atoms.append(atom)
        index = _skip_spaces(text, index)
        if index >= len(text):
            break
        if text[index] != ",":
            raise IdentifierError(f"Expected ',' in identifier subscript list, got {text[index]!r}.")
        index += 1
    return tuple(atoms)


def _parse_display_identifier(text: str, start: int) -> tuple[tuple[str, ...], int]:
    index = _skip_spaces(text, start)
    base, index = _parse_display_atom(text, index)
    atoms = [base]
    index = _skip_spaces(text, index)

    if index < len(text) and text[index] == "_":
        index += 1
        index = _skip_spaces(text, index)
        if index < len(text) and text[index] == "{":
            group, index = _extract_braced_group(text, index)
            atoms.extend(_parse_display_subscript_atoms(group))
        else:
            atom, index = _parse_display_atom(text, index)
            atoms.append(atom)
    return tuple(atoms), index


def _looks_like_call_remainder(text: str) -> bool:
    remainder = text.lstrip()
    return remainder.startswith(("(", "[", r"\left"))


def _split_mathrm_atom_prefix(text: str) -> tuple[str, str] | None:
    index = 0
    while index < len(text):
        if text.startswith(r"\_", index):
            index += 2
            continue
        if text[index].isalnum():
            index += 1
            continue
        break

    if index == 0:
        return None

    prefix = text[:index]
    try:
        canonical = encode_identifier_atoms((_decode_mathrm_atom(prefix),))
    except IdentifierError:
        return None
    return canonical, text[index:]


def _rewrite_wrapped_text_group(group: str) -> str | None:
    try:
        _decode_mathrm_atom(group)
    except IdentifierError:
        pass
    else:
        return None

    try:
        atoms, end = _parse_display_identifier(group, 0)
        canonical = encode_identifier_atoms(atoms)
    except IdentifierError:
        canonical = None
        end = 0
    else:
        remainder = group[end:]
        if _looks_like_call_remainder(remainder):
            return f"{function_head_to_latex(canonical)}{remainder}"

    atom_prefix = _split_mathrm_atom_prefix(group)
    if atom_prefix is not None:
        canonical, remainder = atom_prefix
        if _looks_like_call_remainder(remainder):
            return f"{function_head_to_latex(canonical)}{remainder}"

    return None


def rewrite_wrapped_identifier_calls(text: str) -> str:
    r"""Public semantic-math helper callable for rewrite_wrapped_identifier_calls.
    
    Full API
    --------
    ``rewrite_wrapped_identifier_calls(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = rewrite_wrapped_identifier_calls(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(rewrite_wrapped_identifier_calls)`` and inspect neighboring APIs in the same module.
    """

    source = str(text or "")
    if not source:
        return source

    result: list[str] = []
    index = 0
    while index < len(source):
        if source.startswith(r"\mathrm", index):
            command = r"\mathrm"
        elif source.startswith(r"\operatorname", index):
            command = r"\operatorname"
        else:
            result.append(source[index])
            index += 1
            continue

        cursor = _skip_spaces(source, index + len(command))
        if cursor >= len(source) or source[cursor] != "{":
            result.append(source[index])
            index += 1
            continue

        try:
            group, end = _extract_braced_group(source, cursor)
        except IdentifierError:
            result.append(source[index])
            index += 1
            continue

        rewritten_group = rewrite_wrapped_identifier_calls(group)
        replacement = _rewrite_wrapped_text_group(rewritten_group)
        if replacement is None:
            result.append(command)
            result.append("{")
            result.append(rewritten_group)
            result.append("}")
        else:
            result.append(replacement)
        index = end

    return "".join(result)


def parse_identifier(text: str) -> str:
    """Public semantic-math helper callable for parse_identifier.
    
    Full API
    --------
    ``parse_identifier(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = parse_identifier(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(parse_identifier)`` and inspect neighboring APIs in the same module.
    """

    source = strip_math_delimiters(str(text or "")).strip()
    if not source:
        raise IdentifierError("Identifier is required.")

    try:
        return validate_identifier(source)
    except IdentifierError:
        pass

    atoms, index = _parse_display_identifier(source, 0)
    index = _skip_spaces(source, index)
    if index != len(source):
        raise IdentifierError(f"Unexpected trailing text in identifier: {source[index:]!r}.")
    return encode_identifier_atoms(atoms)


def _scan_command_identifier(text: str, start: int) -> IdentifierScanResult | None:
    if text[start] != "\\":
        return None

    if text.startswith(r"\mathrm", start) or text.startswith(r"\operatorname", start):
        atoms, end = _parse_display_identifier(text, start)
        canonical = encode_identifier_atoms(atoms)
        return IdentifierScanResult(canonical=canonical, end=end, explicit=True)

    command_match = re.match(r"\\([A-Za-z]+)", text[start:])
    if command_match is None:
        return None
    command = command_match.group(1)
    if command not in _IDENTIFIER_LATEX_COMMANDS:
        return None

    base = _IDENTIFIER_LATEX_COMMANDS[command]
    end = start + len(command_match.group(0))
    explicit = command in _EXPLICIT_MACRO_IDENTIFIERS
    end = _skip_spaces(text, end)
    if end < len(text) and text[end] == "_":
        atoms, end = _parse_display_identifier(text, start)
        return IdentifierScanResult(
            canonical=encode_identifier_atoms(atoms),
            end=end,
            explicit=True,
        )
    return IdentifierScanResult(canonical=base, end=end, explicit=explicit)


def _scan_word_identifier(text: str, start: int) -> IdentifierScanResult | None:
    if not text[start].isalpha():
        return None

    raw_match = re.match(r"[A-Za-z][A-Za-z0-9_]*", text[start:])
    if raw_match is None:
        return None
    raw = raw_match.group(0)
    end = start + len(raw)

    if "_" in raw:
        try:
            canonical = validate_identifier(raw)
        except IdentifierError:
            canonical = ""
        else:
            return IdentifierScanResult(canonical=canonical, end=end, explicit=True)

    base_match = re.match(r"[A-Za-z][A-Za-z0-9]*", text[start:])
    if base_match is None:
        return None
    base = base_match.group(0)
    base_end = start + len(base)
    probe = _skip_spaces(text, base_end)
    if probe < len(text) and text[probe] == "_":
        atoms, end = _parse_display_identifier(text, start)
        return IdentifierScanResult(
            canonical=encode_identifier_atoms(atoms),
            end=end,
            explicit=True,
        )
    return IdentifierScanResult(canonical=base, end=base_end, explicit=False)


def scan_identifier_segment(text: str, start: int) -> IdentifierScanResult | None:
    """Public semantic-math helper callable for scan_identifier_segment.
    
    Full API
    --------
    ``scan_identifier_segment(...)``
    
    Parameters
    ----------
    This API accepts the parameters declared in its Python signature.
    
    Returns
    -------
    object
        Result produced by this API.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifier_policy`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = scan_identifier_segment(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(scan_identifier_segment)`` and inspect neighboring APIs in the same module.
    """

    if start >= len(text):
        return None
    if text[start] == "\\":
        return _scan_command_identifier(text, start)
    if text[start].isalpha():
        return _scan_word_identifier(text, start)
    return None
