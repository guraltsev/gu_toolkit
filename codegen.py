"""Code generation engine for reproducing smart figures.

This module converts :class:`FigureSnapshot` objects into self-contained
Python source code that, when executed, recreates the figure with the same
plots, parameter values, styling, and info cards.

Two public helpers are provided:

- :func:`sympy_to_code` — Converts a single SymPy expression into a Python
  source fragment (assumes ``import sympy as sp`` and bare symbol locals).
- :func:`figure_to_code` — Converts a full :class:`FigureSnapshot` into a
  complete, runnable script.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal, Sequence

import sympy as sp
from sympy import Basic, Expr, Symbol
from sympy.core.numbers import (
    Float,
    Half,
    ImaginaryUnit,
    Integer,
    NegativeInfinity,
    NegativeOne,
    Number,
    One,
    Infinity,
    Rational,
    Zero,
)
from sympy.printing.str import StrPrinter

from .FigureSnapshot import FigureSnapshot, InfoCardSnapshot
from .PlotSnapshot import PlotSnapshot
from .ParameterSnapshot import ParameterSnapshot


# ---------------------------------------------------------------------------
# SymPy expression → Python source
# ---------------------------------------------------------------------------

class _SpPrefixedPrinter(StrPrinter):
    """StrPrinter variant that prefixes SymPy functions/constants with ``sp.``.

    Symbols are printed as bare names (they are expected to be defined as
    local variables in the generated script).  Everything else that requires
    SymPy is qualified with ``sp.`` so the output is valid with just
    ``import sympy as sp``.
    """

    # -- atoms / constants --------------------------------------------------

    def _print_Symbol(self, expr: Symbol) -> str:  # noqa: N802
        return expr.name

    def _print_Pi(self, expr: Basic) -> str:  # noqa: N802
        return "sp.pi"

    def _print_Exp1(self, expr: Basic) -> str:  # noqa: N802
        return "sp.E"

    def _print_ImaginaryUnit(self, expr: Basic) -> str:  # noqa: N802
        return "sp.I"

    def _print_Infinity(self, expr: Basic) -> str:  # noqa: N802
        return "sp.oo"

    def _print_NegativeInfinity(self, expr: Basic) -> str:  # noqa: N802
        return "-sp.oo"

    def _print_BooleanTrue(self, expr: Basic) -> str:  # noqa: N802
        return "sp.true"

    def _print_BooleanFalse(self, expr: Basic) -> str:  # noqa: N802
        return "sp.false"

    # -- numbers ------------------------------------------------------------

    def _print_Integer(self, expr: Integer) -> str:  # noqa: N802
        return str(int(expr))

    def _print_Rational(self, expr: Rational) -> str:  # noqa: N802
        if expr.q == 1:
            return str(int(expr.p))
        return f"sp.Rational({int(expr.p)}, {int(expr.q)})"

    def _print_Float(self, expr: Float) -> str:  # noqa: N802
        return repr(float(expr))

    def _print_NaN(self, expr: Basic) -> str:  # noqa: N802
        return "sp.nan"

    # -- generic function fallback ------------------------------------------

    def _print_Function(self, expr: Basic) -> str:  # noqa: N802
        func_name = type(expr).__name__
        args = ", ".join(self._print(a) for a in expr.args)
        return f"sp.{func_name}({args})"

    # -- common operations that the base printer handles but need care ------

    def _print_Pow(self, expr: Basic) -> str:  # noqa: N802
        base = self._print(expr.base)
        exp = self._print(expr.exp)

        # Wrap additions/subtractions in parens for the base
        if expr.base.is_Add:
            base = f"({base})"
        # Wrap negative or complex exponents in parens
        if expr.exp.is_Add or (expr.exp.is_Number and expr.exp < 0):
            exp = f"({exp})"

        # sqrt shortcut for readability
        if expr.exp == sp.Rational(1, 2):
            return f"sp.sqrt({self._print(expr.base)})"
        if expr.exp == sp.Rational(-1, 2):
            return f"1/sp.sqrt({self._print(expr.base)})"

        return f"{base}**{exp}"

    def _print_Abs(self, expr: Basic) -> str:  # noqa: N802
        return f"sp.Abs({self._print(expr.args[0])})"

    def _print_Piecewise(self, expr: Basic) -> str:  # noqa: N802
        pieces = ", ".join(
            f"({self._print(e)}, {self._print(c)})" for e, c in expr.args
        )
        return f"sp.Piecewise({pieces})"


_printer = _SpPrefixedPrinter()


@dataclass(frozen=True)
class CodegenOptions:
    """Configuration knobs for :func:`figure_to_code`.

    Parameters
    ----------
    include_imports : bool, optional
        Whether to emit the import preamble.
    include_symbol_definitions : bool, optional
        Whether to emit ``sp.Symbol`` declarations.
    interface_style : {"figure_methods", "context_manager"}, optional
        Emission style for figure operations.
    include_dynamic_info_as_commented_blocks : bool, optional
        Whether dynamic ``fig.info(...)`` cards should be rendered as commented
        code blocks with recovery guidance.
    """

    include_imports: bool = True
    include_symbol_definitions: bool = True
    interface_style: Literal["figure_methods", "context_manager"] = "context_manager"
    include_dynamic_info_as_commented_blocks: bool = True

    def __post_init__(self) -> None:
        """Validate option values for deterministic code generation."""
        if self.interface_style not in {"figure_methods", "context_manager"}:
            raise ValueError(
                "interface_style must be one of {'figure_methods', 'context_manager'}"
            )


def sympy_to_code(expr: Expr) -> str:
    """Convert a SymPy expression to a Python source fragment.

    The returned string is valid Python when evaluated in a scope where:
    - ``import sympy as sp`` has been executed, and
    - every :class:`~sympy.Symbol` appearing in *expr* is bound to a local
      variable of the same name.

    Parameters
    ----------
    expr : sympy.Expr
        The symbolic expression to convert.

    Returns
    -------
    str
        Python source fragment.

    Examples
    --------
    >>> import sympy as sp
    >>> x, a = sp.symbols("x a")
    >>> sympy_to_code(a * sp.sin(x) + 1)
    'a*sp.sin(x) + 1'
    """
    return _printer.doprint(expr)


# ---------------------------------------------------------------------------
# Full figure → Python script
# ---------------------------------------------------------------------------

def _collect_symbols(snapshot: FigureSnapshot) -> list[Symbol]:
    """Return all unique symbols (params + plot vars) in a deterministic order."""
    seen: OrderedDict[str, Symbol] = OrderedDict()

    # Parameters first (in snapshot iteration order)
    for sym in snapshot.parameters:
        seen[sym.name] = sym

    # Plot variables and parameter lists
    for ps in snapshot.plots.values():
        if ps.var.name not in seen:
            seen[ps.var.name] = ps.var
        for p in ps.parameters:
            if p.name not in seen:
                seen[p.name] = p

    return list(seen.values())


def _fmt_float(v: float) -> str:
    """Format a float for code output, dropping unnecessary trailing zeros."""
    if v == int(v):
        return f"{int(v)}.0"
    return repr(v)


def _symbol_definitions(symbols: list[Symbol]) -> str:
    """Emit ``x = sp.Symbol('x')`` lines (or a grouped form)."""
    if not symbols:
        return ""
    if len(symbols) == 1:
        s = symbols[0]
        return f'{s.name} = sp.Symbol("{s.name}")'
    names = ", ".join(s.name for s in symbols)
    quoted = " ".join(s.name for s in symbols)
    return f'{names} = sp.symbols("{quoted}")'


def _parameter_call(sym: Symbol, meta: dict, *, style: Literal["figure_methods", "context_manager"]) -> str:
    """Emit one parameter registration call."""
    parts = [sym.name]
    for key in ("value", "min", "max", "step"):
        if key in meta:
            parts.append(f"{key}={_fmt_float(float(meta[key]))}")
    if style == "context_manager":
        return f"parameter({', '.join(parts)})"
    return f"fig.parameter({', '.join(parts)})"


def _plot_call(ps: PlotSnapshot, *, style: Literal["figure_methods", "context_manager"]) -> str:
    """Emit one plot call."""
    expr_code = sympy_to_code(ps.func)

    args = [
        f"{expr_code}",
        f"{ps.var.name}",
        f"id={ps.id!r}",
        f"label={ps.label!r}",
    ]

    # Only emit non-default optional kwargs
    if ps.visible is not True:
        args.append(f"visible={ps.visible!r}")
    if ps.x_domain is not None:
        args.append(f"x_domain=({_fmt_float(ps.x_domain[0])}, {_fmt_float(ps.x_domain[1])})")
    if ps.sampling_points is not None:
        args.append(f"sampling_points={ps.sampling_points}")
    if ps.color is not None:
        args.append(f"color={ps.color!r}")
    if ps.thickness is not None:
        args.append(f"thickness={_fmt_float(ps.thickness)}")
    if ps.dash is not None:
        args.append(f"dash={ps.dash!r}")
    if ps.opacity is not None:
        args.append(f"opacity={_fmt_float(ps.opacity)}")
    if getattr(ps, "views", ()):
        if len(ps.views) == 1:
            args.append(f"view={ps.views[0]!r}")
        else:
            args.append(f"view={tuple(ps.views)!r}")

    # Format: single line if short, multi-line otherwise
    joined = ", ".join(args)
    callee = "plot" if style == "context_manager" else "fig.plot"
    call = f"{callee}({joined})"
    if len(call) <= 88:
        return call

    indent = "    "
    body = (",\n" + indent).join(args)
    return f"{callee}(\n{indent}{body},\n)"


def _info_card_lines(
    card: InfoCardSnapshot,
    *,
    style: Literal["figure_methods", "context_manager"],
    include_dynamic_comment_block: bool,
) -> list[str]:
    """Emit ``info(...)``/``fig.info(...)`` lines or dynamic info comments."""
    call = "info" if style == "context_manager" else "fig.info"
    has_dynamic = any(seg == "<dynamic>" for seg in card.segments)
    static_parts = [seg for seg in card.segments if seg != "<dynamic>"]

    view_suffix = f", view={card.view_id!r}" if card.view_id is not None else ""

    if has_dynamic:
        if not include_dynamic_comment_block:
            return ["# dynamic info omitted"]

        static_spec = repr(static_parts[0]) if len(static_parts) == 1 else repr(static_parts)
        suffix = f", id={card.id!r}" if card.id is not None else ""
        suffix += view_suffix
        lines = [
            f"# {call}({static_spec}{suffix})",
            "# NOTE: Dynamic info callable segments were omitted from this commented block.",
            "# NOTE: Define every callable referenced by this card in scope before enabling the line above.",
            "# import inspect",
            "# print(inspect.getsource(my_dynamic_func))",
        ]
        return lines

    if not static_parts:
        return []

    if len(static_parts) == 1:
        line = f"{call}({static_parts[0]!r}"
    else:
        parts_repr = ", ".join(repr(s) for s in static_parts)
        line = f"{call}([{parts_repr}]"

    if card.id is not None:
        line += f", id={card.id!r}"
    if card.view_id is not None:
        line += f", view={card.view_id!r}"
    line += ")"
    return [line]


def figure_to_code(snapshot: FigureSnapshot, options: CodegenOptions | None = None) -> str:
    """Generate a self-contained Python script from a :class:`FigureSnapshot`.

    The returned string, when executed in a Jupyter notebook or Python REPL
    with ``gu_toolkit`` installed, recreates the figure with identical plots,
    parameter values/ranges, styling, and static info cards.

    Parameters
    ----------
    snapshot : FigureSnapshot
        Immutable figure state captured via :meth:`Figure.snapshot`.
    options : CodegenOptions | None, optional
        Optional output-style and serialization policy configuration.

    Returns
    -------
    str
        Complete Python source code.
    """
    options = options or CodegenOptions()
    lines: list[str] = []

    # -- imports ------------------------------------------------------------
    if options.include_imports:
        lines.append("import sympy as sp")
        if options.interface_style == "context_manager":
            lines.append("from gu_toolkit import Figure, parameter, plot, info")
        else:
            lines.append("from gu_toolkit import Figure")
        lines.append("")

    # -- symbols ------------------------------------------------------------
    symbols = _collect_symbols(snapshot)
    if symbols and options.include_symbol_definitions:
        lines.append("# Symbols")
        lines.append(_symbol_definitions(symbols))
        lines.append("")

    # -- figure construction ------------------------------------------------
    lines.append("# Figure")
    lines.append(
        f"fig = Figure("
        f"x_range=({_fmt_float(snapshot.x_range[0])}, {_fmt_float(snapshot.x_range[1])}), "
        f"y_range=({_fmt_float(snapshot.y_range[0])}, {_fmt_float(snapshot.y_range[1])}), "
        f"sampling_points={snapshot.sampling_points})"
    )
    if snapshot.title:
        lines.append(f"fig.title = {snapshot.title!r}")
    if getattr(snapshot, "views", ()):
        for view in snapshot.views:
            if view.id == "main":
                continue
            lines.append(
                "fig.add_view("
                f"{view.id!r}, title={view.title!r}, x_range=({_fmt_float(view.x_range[0])}, {_fmt_float(view.x_range[1])}), "
                f"y_range=({_fmt_float(view.y_range[0])}, {_fmt_float(view.y_range[1])}), "
                f"x_label={view.x_label!r}, y_label={view.y_label!r})"
            )
        if snapshot.active_view_id != "main":
            lines.append(f"fig.set_active_view({snapshot.active_view_id!r})")
    lines.append("")

    # -- operation body -----------------------------------------------------
    body_lines: list[str] = []

    if len(snapshot.parameters) > 0:
        body_lines.append("# Parameters")
        for sym in snapshot.parameters:
            meta = dict(snapshot.parameters[sym])
            body_lines.append(_parameter_call(sym, meta, style=options.interface_style))
        body_lines.append("")

    if snapshot.plots:
        body_lines.append("# Plots")
        for ps in snapshot.plots.values():
            body_lines.append(_plot_call(ps, style=options.interface_style))
        body_lines.append("")

    info_lines: list[str] = []
    for card in snapshot.info_cards:
        info_lines.extend(
            _info_card_lines(
                card,
                style=options.interface_style,
                include_dynamic_comment_block=options.include_dynamic_info_as_commented_blocks,
            )
        )
    if info_lines:
        body_lines.append("# Info")
        body_lines.extend(info_lines)
        body_lines.append("")

    if options.interface_style == "context_manager":
        lines.append("with fig:")
        if not body_lines:
            lines.append("    pass")
            lines.append("")
        else:
            for line in body_lines:
                if not line:
                    lines.append("")
                else:
                    lines.append(f"    {line}")
    else:
        lines.extend(body_lines)

    # -- display ------------------------------------------------------------
    lines.append("fig")
    lines.append("")

    return "\n".join(lines)
