"""MathLive/Compute Engine transport helpers.

This module is the semantic boundary between the notebook-facing math input
widgets and the rest of the toolkit. It does **not** depend on any figure-
centric modules. Its responsibilities are:

* build a JSON-safe context manifest for the MathLive frontend backend
* convert MathJSON payloads coming back from MathLive into canonical identifiers
* convert MathJSON payloads into SymPy expressions using an :class:`ExpressionContext`

LaTeX remains a useful display and fallback interchange format, but MathJSON is
our primary transport when the MathLive Compute Engine is available.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

import sympy as sp

from .identifier_policy import (
    IdentifierError,
    encode_identifier_atoms,
    split_identifier_atoms,
    symbol,
    semantic_function,
    validate_identifier,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for type checkers only
    from .expression_context import ExpressionContext

__all__ = [
    "MathJSONParseError",
    "build_mathlive_transport_manifest",
    "mathjson_to_identifier",
    "mathjson_to_sympy",
]


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

_STANDARD_SYMBOLS: dict[str, sp.Expr] = {
    "Pi": sp.pi,
    "ExponentialE": sp.E,
    "ImaginaryUnit": sp.I,
    "Infinity": sp.oo,
    "NegativeInfinity": -sp.oo,
    "ComplexInfinity": sp.zoo,
    "Nothing": sp.Integer(0),
    # Allow already-normalized toolkit spellings too.
    "pi": sp.pi,
    "E": sp.E,
    "I": sp.I,
}

_STANDARD_FUNCTIONS: dict[str, Any] = {
    "Sin": sp.sin,
    "Cos": sp.cos,
    "Tan": sp.tan,
    "Cot": sp.cot,
    "Sec": sp.sec,
    "Csc": sp.csc,
    "Sinh": sp.sinh,
    "Cosh": sp.cosh,
    "Tanh": sp.tanh,
    "Exp": sp.exp,
    "Log": sp.log,
    "Ln": sp.log,
    "Sqrt": sp.sqrt,
    "SquareRoot": sp.sqrt,
    "Abs": sp.Abs,
    "Min": sp.Min,
    "Max": sp.Max,
    # A few permissive aliases in case non-canonical MathJSON is transported.
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "cot": sp.cot,
    "sec": sp.sec,
    "csc": sp.csc,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "exp": sp.exp,
    "log": sp.log,
    "ln": sp.log,
    "sqrt": sp.sqrt,
    "abs": sp.Abs,
    "min": sp.Min,
    "max": sp.Max,
}

_RESERVED_HEADS = {
    "Add",
    "Multiply",
    "Power",
    "Divide",
    "Subtract",
    "Negate",
    "Rational",
    "Tuple",
    "List",
    "Sequence",
    "Complex",
    "Subscript",
    "Apply",
    "Hold",
    "Error",
    *set(_STANDARD_FUNCTIONS),
}


class MathJSONParseError(ValueError):
    """Public semantic-math helper class for MathJSONParseError.
    
    Full API
    --------
    ``MathJSONParseError``
    
    Parameters
    ----------
    Constructor parameters follow the Python signature for this class.
    
    Returns
    -------
    MathJSONParseError
        New ``MathJSONParseError`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    Optional arguments follow the defaults declared in the Python signature when present.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.mathlive_transport`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        obj = MathJSONParseError(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(MathJSONParseError)`` and inspect neighboring APIs in the same module.
    """


def _context_symbols(context: Any | None) -> dict[str, Any]:
    return getattr(context, "symbols", {}) if context is not None else {}


def _context_functions(context: Any | None) -> dict[str, Any]:
    return getattr(context, "functions", {}) if context is not None else {}


def _is_known_identifier(name: str, context: Any | None) -> bool:
    return name in _context_symbols(context) or name in _context_functions(context)


def _contains_ambiguous_single_underscore(text: str) -> bool:
    index = 0
    while index < len(text):
        if text[index] != "_":
            index += 1
            continue
        if index + 1 < len(text) and text[index + 1] == "_":
            index += 2
            continue
        return True
    return False


def _normalize_transport_name(name: str, *, context: Any | None, role: str) -> str:
    text = str(name)
    if _is_known_identifier(text, context):
        return text
    if _contains_ambiguous_single_underscore(text):
        raise MathJSONParseError(
            f"MathJSON name {text!r} is ambiguous without context-aware canonical registration."
        )
    try:
        return validate_identifier(text, role=role)
    except IdentifierError as exc:  # pragma: no cover - defensive narrowing
        raise MathJSONParseError(str(exc)) from exc


def _transport_trigger_for_name(name: str) -> dict[str, str]:
    atoms = split_identifier_atoms(name)
    if len(atoms) != 1:
        return {}

    atom = atoms[0]
    if atom in _GREEK_NAME_TO_LATEX:
        return {"triggerKind": "latex", "trigger": _GREEK_NAME_TO_LATEX[atom]}
    if len(atom) == 1:
        return {"triggerKind": "latex", "trigger": atom}
    return {"triggerKind": "symbol", "trigger": atom}


def build_mathlive_transport_manifest(
    context: Any,
    *,
    field_role: str = "math",
) -> dict[str, Any]:
    """Public semantic-math helper callable for build_mathlive_transport_manifest.
    
    Full API
    --------
    ``build_mathlive_transport_manifest(...)``
    
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
    This API lives in ``gu_toolkit.mathlive_transport`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = build_mathlive_transport_manifest(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(build_mathlive_transport_manifest)`` and inspect neighboring APIs in the same module.
    """

    manifest: dict[str, Any] = {
        "version": 1,
        "fieldRole": str(field_role),
        "symbols": [],
        "functions": [],
    }

    for spec in sorted(_context_symbols(context).values(), key=lambda item: item.name.lower()):
        entry = {
            "name": spec.name,
            "latex": spec.latex_expr,
            "atoms": list(split_identifier_atoms(spec.name)),
        }
        entry.update(_transport_trigger_for_name(spec.name))
        manifest["symbols"].append(entry)

    for spec in sorted(_context_functions(context).values(), key=lambda item: item.name.lower()):
        entry = {
            "name": spec.name,
            "latexHead": spec.latex_head,
            "atoms": list(split_identifier_atoms(spec.name)),
            "arity": spec.arity,
            "template": f"{spec.latex_head}(#0)",
        }
        entry.update(_transport_trigger_for_name(spec.name))
        manifest["functions"].append(entry)

    return manifest


def _coerce_mathjson_array(node: Any) -> list[Any] | None:
    if isinstance(node, list):
        return node
    if isinstance(node, tuple):
        return list(node)
    return None


def _collect_subscript_components(node: Any, *, context: Any | None) -> list[str]:
    array = _coerce_mathjson_array(node)
    if array is not None and array:
        head = array[0]
        if head in {"Tuple", "List", "Sequence"}:
            atoms: list[str] = []
            for item in array[1:]:
                atoms.extend(_collect_subscript_components(item, context=context))
            return atoms
        if head == "Subscript":
            canonical = mathjson_to_identifier(node, context=context, role="identifier")
            parts = split_identifier_atoms(canonical)
            if len(parts) == 1:
                return [parts[0]]
            return list(parts)

    if isinstance(node, bool):
        raise MathJSONParseError("Boolean values are not valid identifier atoms.")
    if isinstance(node, int):
        return [str(int(node))]
    if isinstance(node, float):
        if float(node).is_integer():
            return [str(int(node))]
        raise MathJSONParseError(f"Non-integer numeric subscript {node!r} is not supported.")
    if isinstance(node, str):
        canonical = _normalize_transport_name(node, context=context, role="identifier")
        parts = split_identifier_atoms(canonical)
        if len(parts) == 1:
            return [parts[0]]
        return list(parts)
    if isinstance(node, dict):
        if "sym" in node:
            return _collect_subscript_components(node["sym"], context=context)
        if "num" in node:
            return _collect_subscript_components(node["num"], context=context)

    raise MathJSONParseError(f"Unsupported MathJSON subscript component: {node!r}.")


def mathjson_to_identifier(
    math_json: Any,
    *,
    context: Any | None = None,
    role: str = "identifier",
) -> str:
    """Public semantic-math helper callable for mathjson_to_identifier.
    
    Full API
    --------
    ``mathjson_to_identifier(...)``
    
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
    This API lives in ``gu_toolkit.mathlive_transport`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = mathjson_to_identifier(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(mathjson_to_identifier)`` and inspect neighboring APIs in the same module.
    """

    if math_json is None:
        raise MathJSONParseError("MathJSON payload is empty.")

    if isinstance(math_json, bool):
        raise MathJSONParseError("Boolean values are not valid identifiers.")
    if isinstance(math_json, int):
        raise MathJSONParseError("Identifiers must start with a letter, not a number.")
    if isinstance(math_json, float):
        raise MathJSONParseError("Identifiers cannot be floating point values.")
    if isinstance(math_json, str):
        return _normalize_transport_name(math_json, context=context, role=role)

    if isinstance(math_json, dict):
        if "sym" in math_json:
            return mathjson_to_identifier(math_json["sym"], context=context, role=role)
        if "fn" in math_json:
            head = math_json["fn"]
            return mathjson_to_identifier(head, context=context, role=role)
        if "num" in math_json:
            raise MathJSONParseError("Numeric MathJSON objects are not valid identifiers.")

    array = _coerce_mathjson_array(math_json)
    if array is None or not array:
        raise MathJSONParseError(f"Unsupported MathJSON identifier payload: {math_json!r}.")

    head = array[0]
    if head == "Hold" and len(array) == 2:
        return mathjson_to_identifier(array[1], context=context, role=role)
    if head == "Subscript" and len(array) >= 3:
        base = mathjson_to_identifier(array[1], context=context, role=role)
        atoms = list(split_identifier_atoms(base))
        for item in array[2:]:
            atoms.extend(_collect_subscript_components(item, context=context))
        try:
            return encode_identifier_atoms(atoms, role=role)
        except IdentifierError as exc:
            raise MathJSONParseError(str(exc)) from exc

    if not isinstance(head, str):
        if len(array) >= 1:
            return mathjson_to_identifier(head, context=context, role=role)

    raise MathJSONParseError(f"Unsupported MathJSON identifier payload: {math_json!r}.")


def _resolve_symbol(name: str, context: Any | None) -> sp.Symbol:
    symbols = _context_symbols(context)
    if name in symbols:
        return symbols[name].symbol
    return symbol(name)


def _resolve_function(name: str, context: Any | None) -> Any:
    functions = _context_functions(context)
    if name in functions:
        return functions[name].function
    return semantic_function(name)


def _coerce_integer(value: Any) -> int:
    if isinstance(value, bool):
        raise MathJSONParseError(f"Boolean value {value!r} is not a valid integer.")
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) and float(value).is_integer():
        return int(value)
    raise MathJSONParseError(f"Expected integer, got {value!r}.")


def _build_function_application(head: Any, args: list[Any], *, context: Any | None) -> sp.Expr:
    converted_args = [mathjson_to_sympy(arg, context=context) for arg in args]

    if isinstance(head, str):
        if head in _context_functions(context):
            func = _resolve_function(head, context)
            return func(*converted_args)
        if head in _STANDARD_FUNCTIONS:
            func = _STANDARD_FUNCTIONS[head]
            return func(*converted_args)
        name = _normalize_transport_name(head, context=context, role="function")
        func = _resolve_function(name, context)
        return func(*converted_args)

    canonical = mathjson_to_identifier(head, context=context, role="function")
    func = _resolve_function(canonical, context)
    return func(*converted_args)


def mathjson_to_sympy(math_json: Any, *, context: Any | None = None) -> sp.Expr:
    """Public semantic-math helper callable for mathjson_to_sympy.
    
    Full API
    --------
    ``mathjson_to_sympy(...)``
    
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
    This API lives in ``gu_toolkit.mathlive_transport`` and participates in the toolkit's canonical identifier, parsing, or semantic math-input infrastructure.
    
    Examples
    --------
    Basic use::
    
        result = mathjson_to_sympy(...)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: inspect the targeted tests covering symbolic parsing and math widgets.
    - In a notebook or REPL, run ``help(mathjson_to_sympy)`` and inspect neighboring APIs in the same module.
    """

    if math_json is None:
        raise MathJSONParseError("MathJSON payload is empty.")

    if isinstance(math_json, bool):
        return sp.true if math_json else sp.false
    if isinstance(math_json, int):
        return sp.Integer(math_json)
    if isinstance(math_json, float):
        if float(math_json).is_integer():
            return sp.Integer(int(math_json))
        return sp.Float(math_json)
    if isinstance(math_json, str):
        if math_json in _context_symbols(context):
            return _resolve_symbol(math_json, context)
        if math_json in _STANDARD_SYMBOLS:
            return _STANDARD_SYMBOLS[math_json]
        name = _normalize_transport_name(math_json, context=context, role="identifier")
        return _resolve_symbol(name, context)

    if isinstance(math_json, dict):
        if "num" in math_json:
            return mathjson_to_sympy(math_json["num"], context=context)
        if "sym" in math_json:
            return mathjson_to_sympy(math_json["sym"], context=context)
        if "fn" in math_json:
            head = math_json["fn"]
            args = list(math_json.get("args", []))
            return _build_function_application(head, args, context=context)
        raise MathJSONParseError(f"Unsupported MathJSON object payload: {math_json!r}.")

    array = _coerce_mathjson_array(math_json)
    if array is None or not array:
        raise MathJSONParseError(f"Unsupported MathJSON payload: {math_json!r}.")

    head = array[0]
    args = array[1:]

    if head == "Hold" and len(args) == 1:
        return mathjson_to_sympy(args[0], context=context)
    if head == "Add":
        return sp.Add(*(mathjson_to_sympy(arg, context=context) for arg in args))
    if head == "Multiply":
        return sp.Mul(*(mathjson_to_sympy(arg, context=context) for arg in args))
    if head == "Power" and len(args) == 2:
        return mathjson_to_sympy(args[0], context=context) ** mathjson_to_sympy(args[1], context=context)
    if head == "Divide" and len(args) == 2:
        return mathjson_to_sympy(args[0], context=context) / mathjson_to_sympy(args[1], context=context)
    if head == "Subtract" and len(args) == 2:
        return mathjson_to_sympy(args[0], context=context) - mathjson_to_sympy(args[1], context=context)
    if head == "Negate" and len(args) == 1:
        return -mathjson_to_sympy(args[0], context=context)
    if head == "Rational" and len(args) == 2:
        return sp.Rational(_coerce_integer(args[0]), _coerce_integer(args[1]))
    if head == "Complex" and len(args) == 2:
        return mathjson_to_sympy(args[0], context=context) + sp.I * mathjson_to_sympy(args[1], context=context)
    if head == "Tuple":
        return sp.Tuple(*(mathjson_to_sympy(arg, context=context) for arg in args))
    if head == "List":
        return sp.Tuple(*(mathjson_to_sympy(arg, context=context) for arg in args))
    if head == "Sequence":
        return sp.Tuple(*(mathjson_to_sympy(arg, context=context) for arg in args))
    if head == "Subscript":
        canonical = mathjson_to_identifier(array, context=context, role="identifier")
        return _resolve_symbol(canonical, context)
    if head == "Error":
        raise MathJSONParseError(f"MathLive Compute Engine returned an error payload: {math_json!r}.")
    if isinstance(head, str) and head in _STANDARD_FUNCTIONS:
        func = _STANDARD_FUNCTIONS[head]
        return func(*(mathjson_to_sympy(arg, context=context) for arg in args))
    if head == "Apply" and len(args) >= 1:
        fn_head = args[0]
        fn_args = args[1:]
        return _build_function_application(fn_head, fn_args, context=context)

    return _build_function_application(head, args, context=context)
