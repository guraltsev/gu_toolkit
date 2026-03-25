"""Interactive plot-composer dialog used by the legend sidebar.

Purpose
-------
This module owns the notebook UI that lets users create and edit plots directly
from the legend area. The dialog is intentionally figure-centric: it reads the
current figure's views, infers parameters from entered expressions, and routes
successful submissions back through the existing public plotting methods.

Supported plot families
-----------------------
The composer currently supports five manual modes:

- cartesian curves ``y = f(x)``
- parametric curves ``(x(t), y(t))``
- contour plots ``z = f(x, y)``
- density plots (generic heatmaps)
- temperature plots (heatmaps with thermal defaults)

Architecture
------------
The module is split into two small layers:

- immutable :class:`PlotEditorDraft` values capture the form state in a
  testable, backend-friendly shape;
- :class:`PlotComposerDialog` manages widgets, validation messaging, and modal
  lifecycle.

The dialog deliberately avoids bypassing the public plotting API. Even editor-
created plots are applied through :meth:`Figure.plot`,
:meth:`Figure.parametric_plot`, :meth:`Figure.contour`,
:meth:`Figure.density`, and :meth:`Figure.temperature` so snapshotting,
codegen, legend updates, parameter inference, and render scheduling all stay
on the existing code paths.

Discoverability
---------------
See :mod:`gu_toolkit.figure_legend` for the toolbar/buttons that launch the
composer and :mod:`gu_toolkit._mathlive_widget` for the MathLive field wrapper.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import sympy as sp
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from ._mathlive_widget import MathLiveField
from ._widget_stubs import widgets
from .figure_field import ScalarFieldPlot
from .figure_parametric_plot import ParametricPlot
from .figure_plot import Plot
from .parameter_keys import parameter_name
from .ParseLaTeX import LatexParseError, parse_latex

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .Figure import Figure


PlotEditorKind = Literal[
    "cartesian",
    "parametric",
    "contour",
    "density",
    "temperature",
]


@dataclass(frozen=True)
class PlotEditorDraft:
    """Detached snapshot of the plot-composer form state.

    The draft keeps widget concerns out of parsing/apply helpers, which makes
    the behavior easy to test without constructing the modal UI.
    """

    kind: PlotEditorKind
    plot_id: str | None
    label: str
    view_ids: tuple[str, ...]
    cartesian_expression_latex: str
    cartesian_var_latex: str
    cartesian_samples: int
    parametric_x_latex: str
    parametric_y_latex: str
    parameter_var_latex: str
    parameter_min_latex: str
    parameter_max_latex: str
    parametric_samples: int
    field_expression_latex: str
    field_x_var_latex: str
    field_y_var_latex: str
    field_grid_x: int
    field_grid_y: int


@dataclass(frozen=True)
class ParameterPreview:
    """Parameter-inference summary shown in the composer dialog."""

    will_create: tuple[str, ...]
    will_reuse: tuple[str, ...]
    error: str | None = None



_PARSE_EXPR_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)
_LATEXISH_NAME_MAP: tuple[tuple[str, str], ...] = (
    (r"\alpha", "alpha"),
    (r"\beta", "beta"),
    (r"\gamma", "gamma"),
    (r"\delta", "delta"),
    (r"\epsilon", "epsilon"),
    (r"\varepsilon", "varepsilon"),
    (r"\theta", "theta"),
    (r"\vartheta", "vartheta"),
    (r"\lambda", "lambda"),
    (r"\mu", "mu"),
    (r"\nu", "nu"),
    (r"\phi", "phi"),
    (r"\varphi", "varphi"),
    (r"\psi", "psi"),
    (r"\omega", "omega"),
    (r"\rho", "rho"),
    (r"\sigma", "sigma"),
    (r"\tau", "tau"),
    (r"\pi", "pi"),
    (r"\sinh", "sinh"),
    (r"\cosh", "cosh"),
    (r"\tanh", "tanh"),
    (r"\sin", "sin"),
    (r"\cos", "cos"),
    (r"\tan", "tan"),
    (r"\cot", "cot"),
    (r"\sec", "sec"),
    (r"\csc", "csc"),
    (r"\log", "log"),
    (r"\ln", "log"),
    (r"\exp", "exp"),
)


def _extract_braced_group(text: str, start: int) -> tuple[str, int]:
    """Return the braced group that starts at ``start`` and the next index."""

    if start >= len(text) or text[start] != "{":
        raise ValueError("Expected '{' while parsing LaTeX input.")
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise ValueError("Unbalanced braces in LaTeX input.")


def _rewrite_group_command(text: str, command: str, *, arity: int) -> str:
    r"""Rewrite simple LaTeX group commands such as ``\frac`` and ``\sqrt``."""

    result: list[str] = []
    index = 0
    while index < len(text):
        if not text.startswith(command, index):
            result.append(text[index])
            index += 1
            continue

        cursor = index + len(command)
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1

        groups: list[str] = []
        try:
            for _ in range(arity):
                group_text, cursor = _extract_braced_group(text, cursor)
                groups.append(_normalize_latexish_text(group_text))
                while cursor < len(text) and text[cursor].isspace():
                    cursor += 1
        except ValueError:
            result.append(text[index])
            index += 1
            continue

        if command == r"\frac":
            result.append(f"(({groups[0]})/({groups[1]}))")
        elif command == r"\sqrt":
            result.append(f"sqrt({groups[0]})")
        else:  # pragma: no cover - defensive fallback
            result.append(" ".join(groups))
        index = cursor
    return "".join(result)


def _normalize_latexish_text(value: str) -> str:
    r"""Convert common MathLive/LaTeX-ish text into ``parse_expr`` input.

    The editor first tries the toolkit's dedicated LaTeX parser. This fallback
    exists for environments where that parser backend is unavailable or where
    MathLive emits lightweight LaTeX fragments such as ``2\pi`` or
    ``a\cos(t)`` that still map cleanly to SymPy syntax.
    """

    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace(r"\left", "").replace(r"\right", "")
    text = text.replace(r"\cdot", " * ").replace(r"\times", " * ").replace("·", " * ")
    text = _rewrite_group_command(text, r"\frac", arity=2)
    text = _rewrite_group_command(text, r"\sqrt", arity=1)
    for source, target in _LATEXISH_NAME_MAP:
        text = text.replace(source, f" {target}")
    text = text.replace("{", "(").replace("}", ")")
    text = re.sub(r"\\,|\\;|\\!|\\quad|\\qquad", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_plain_math_text(text: str) -> Expr:
    """Parse plain or lightly normalized mathematical text into SymPy."""

    parsed = parse_expr(
        text,
        transformations=_PARSE_EXPR_TRANSFORMS,
        evaluate=True,
    )
    if not isinstance(parsed, Expr):
        raise ValueError("Parsed value is not a SymPy expression.")
    return parsed


def _latex_to_expression(value: str, *, role: str) -> Expr:
    r"""Parse one MathLive/LaTeX field into a SymPy expression.

    Parsing first uses the toolkit's resilient LaTeX parser and then falls back
    to a lightweight MathLive/LaTeX normalizer plus :func:`parse_expr`. This
    keeps the editor usable even when users paste non-LaTeX expressions such as
    ``a*x + 1`` or lightweight MathLive output such as ``2\pi``.
    """

    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{role} is required.")

    latex_error: Exception | None = None
    try:
        parsed = parse_latex(text)
        if isinstance(parsed, Expr):
            return parsed
    except (LatexParseError, TypeError, ValueError, SyntaxError) as exc:
        latex_error = exc
    except Exception as exc:  # pragma: no cover - defensive parser guard
        latex_error = exc

    parse_errors: list[Exception] = []
    candidates = []
    normalized = _normalize_latexish_text(text)
    if normalized:
        candidates.append(normalized)
    if text not in candidates:
        candidates.append(text)

    for candidate in candidates:
        try:
            return _parse_plain_math_text(candidate)
        except Exception as exc:
            parse_errors.append(exc)

    detail = f" LaTeX parser error: {latex_error}" if latex_error is not None else ""
    if parse_errors:
        detail += f" Plain-text parser error: {parse_errors[-1]}"
    raise ValueError(f"Could not parse {role}.{detail}")


def _latex_to_symbol(value: str, *, role: str, default_latex: str | None = None) -> Symbol:
    """Parse a symbol-entry field and ensure it resolves to exactly one symbol."""

    source = str(value or "").strip() or str(default_latex or "").strip()
    if not source:
        raise ValueError(f"{role} is required.")
    parsed = _latex_to_expression(source, role=role)
    if not isinstance(parsed, Symbol):
        raise ValueError(f"{role} must be a single symbol, got {parsed!r}.")
    return parsed


def _to_latex(value: Any, *, default: str = "") -> str:
    """Serialize a symbolic or numeric value into LaTeX for editor fields."""

    if value is None:
        return default
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or default
    try:
        return sp.latex(sp.sympify(value))
    except Exception:
        text = str(value)
        return text if text else default


def _sorted_unique_names(symbols: set[Symbol]) -> tuple[str, ...]:
    """Return canonical parameter names in a stable, user-friendly order."""

    return tuple(sorted({parameter_name(symbol) for symbol in symbols}))


def _infer_draft_parameter_symbols(draft: PlotEditorDraft) -> set[Symbol]:
    """Return parameter-like free symbols implied by one editor draft.

    The helper mirrors the public plotting APIs while filling in one important
    gap: parametric range bounds can also contain symbols (for example
    ``(t, 0, 2*pi*a)``), so the editor includes those symbols in the inferred
    parameter set too.
    """

    excluded: set[Symbol]
    expressions: list[Expr]
    if draft.kind == "cartesian":
        expressions = [
            _latex_to_expression(
                draft.cartesian_expression_latex,
                role="Cartesian expression",
            )
        ]
        excluded = {
            _latex_to_symbol(
                draft.cartesian_var_latex,
                role="Cartesian free variable",
                default_latex="x",
            )
        }
    elif draft.kind == "parametric":
        excluded = {
            _latex_to_symbol(
                draft.parameter_var_latex,
                role="Parametric parameter",
                default_latex="t",
            )
        }
        parameter_min = _latex_to_expression(
            draft.parameter_min_latex,
            role="Parameter minimum",
        )
        parameter_max = _latex_to_expression(
            draft.parameter_max_latex,
            role="Parameter maximum",
        )
        bound_symbols = (set(parameter_min.free_symbols) | set(parameter_max.free_symbols)) - excluded
        if bound_symbols:
            names = ", ".join(_sorted_unique_names(bound_symbols))
            raise ValueError(
                "Parametric parameter bounds must currently be numeric; "
                f"symbolic bounds are not supported yet ({names})."
            )
        expressions = [
            _latex_to_expression(draft.parametric_x_latex, role="Parametric x(t)"),
            _latex_to_expression(draft.parametric_y_latex, role="Parametric y(t)"),
        ]
    else:
        expressions = [
            _latex_to_expression(
                draft.field_expression_latex,
                role="Scalar-field expression",
            )
        ]
        excluded = {
            _latex_to_symbol(
                draft.field_x_var_latex,
                role="Field x variable",
                default_latex="x",
            ),
            _latex_to_symbol(
                draft.field_y_var_latex,
                role="Field y variable",
                default_latex="y",
            ),
        }

    parameter_symbols: set[Symbol] = set()
    for expression in expressions:
        parameter_symbols.update(set(expression.free_symbols) - excluded)
    return parameter_symbols


def _draft_parameter_preview(figure: Figure, draft: PlotEditorDraft) -> ParameterPreview:
    """Infer which parameter symbols the draft would create or reuse."""

    try:
        names = _sorted_unique_names(_infer_draft_parameter_symbols(draft))
        if not names:
            return ParameterPreview((), ())
        existing_names = set(figure.parameters.keys())
        will_reuse = tuple(name for name in names if name in existing_names)
        will_create = tuple(name for name in names if name not in existing_names)
        return ParameterPreview(will_create=will_create, will_reuse=will_reuse)
    except ValueError as exc:
        return ParameterPreview((), (), error=str(exc))


def apply_plot_editor_draft(
    figure: Figure,
    draft: PlotEditorDraft,
    *,
    existing_plot: Any | None = None,
) -> Any:
    """Apply one validated editor draft through the public figure API.

    Parameters
    ----------
    figure:
        Target figure that will own the created/updated plot.
    draft:
        Detached form snapshot.
    existing_plot:
        Existing runtime plot being edited, when any. The helper uses this to
        preserve the current plot id and visibility semantics.
    """

    plot_id = draft.plot_id or getattr(existing_plot, "id", None)
    if draft.view_ids:
        view_arg: str | tuple[str, ...] = (
            draft.view_ids[0] if len(draft.view_ids) == 1 else draft.view_ids
        )
    else:
        view_arg = figure.views.current_id

    is_edit = existing_plot is not None
    label_arg = draft.label if is_edit else (draft.label.strip() or None)
    common_kwargs: dict[str, Any] = {
        "id": plot_id,
        "label": label_arg,
        "view": view_arg,
        "visible": getattr(existing_plot, "visible", True),
    }

    if draft.kind == "cartesian":
        expression = _latex_to_expression(
            draft.cartesian_expression_latex,
            role="Cartesian expression",
        )
        variable = _latex_to_symbol(
            draft.cartesian_var_latex,
            role="Cartesian free variable",
            default_latex="x",
        )
        return figure.plot(
            expression,
            variable,
            samples=int(draft.cartesian_samples),
            **common_kwargs,
        )

    if draft.kind == "parametric":
        x_expression = _latex_to_expression(draft.parametric_x_latex, role="Parametric x(t)")
        y_expression = _latex_to_expression(draft.parametric_y_latex, role="Parametric y(t)")
        parameter_var = _latex_to_symbol(
            draft.parameter_var_latex,
            role="Parametric parameter",
            default_latex="t",
        )
        parameter_min = _latex_to_expression(draft.parameter_min_latex, role="Parameter minimum")
        parameter_max = _latex_to_expression(draft.parameter_max_latex, role="Parameter maximum")
        parameter_symbols = tuple(
            sp.Symbol(name) for name in _sorted_unique_names(_infer_draft_parameter_symbols(draft))
        )
        return figure.parametric_plot(
            (x_expression, y_expression),
            (parameter_var, parameter_min, parameter_max),
            parameters=parameter_symbols or None,
            samples=int(draft.parametric_samples),
            **common_kwargs,
        )

    field_expression = _latex_to_expression(
        draft.field_expression_latex,
        role="Scalar-field expression",
    )
    x_variable = _latex_to_symbol(
        draft.field_x_var_latex,
        role="Field x variable",
        default_latex="x",
    )
    y_variable = _latex_to_symbol(
        draft.field_y_var_latex,
        role="Field y variable",
        default_latex="y",
    )
    grid = (int(draft.field_grid_x), int(draft.field_grid_y))

    if draft.kind == "contour":
        return figure.contour(field_expression, x_variable, y_variable, grid=grid, **common_kwargs)
    if draft.kind == "temperature":
        return figure.temperature(field_expression, x_variable, y_variable, grid=grid, **common_kwargs)
    if draft.kind == "density":
        return figure.density(field_expression, x_variable, y_variable, grid=grid, **common_kwargs)
    raise ValueError(f"Unsupported plot editor kind: {draft.kind!r}")


class PlotComposerDialog:
    """Modal editor for creating and editing figure plots from the legend.

    The dialog is intentionally modest: it offers explicit mode selection,
    MathLive-backed expression fields, a separate free-variable entry, and a
    small set of high-value options (label, samples/grid, and target views).
    """

    def __init__(self, figure: Figure, *, modal_host: widgets.Box) -> None:
        self._figure = figure
        self._modal_host = modal_host
        self._editing_plot_id: str | None = None
        self._is_open = False
        self._suspend_observers = False

        self._style = widgets.HTML(
            value=self._dialog_style_html(),
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )

        self._kind = widgets.Dropdown(
            description="Type:",
            options=(
                ("Function y = f(x)", "cartesian"),
                ("Parametric (x(t), y(t))", "parametric"),
                ("Contour z = f(x, y)", "contour"),
                ("Density heatmap", "density"),
                ("Temperature heatmap", "temperature"),
            ),
            value="cartesian",
            layout=widgets.Layout(width="100%"),
        )
        self._id_text = widgets.Text(
            description="ID:",
            placeholder="Auto",
            layout=widgets.Layout(width="100%"),
        )
        self._label_text = widgets.Text(
            description="Label:",
            placeholder="Legend label",
            layout=widgets.Layout(width="100%"),
        )
        self._views = widgets.SelectMultiple(
            description="Views:",
            options=(),
            value=(),
            layout=widgets.Layout(width="100%", min_height="88px"),
        )

        self._cartesian_expression = MathLiveField(
            placeholder=r"x^2 + a x + b",
            aria_label="Cartesian expression",
        )
        self._cartesian_variable = MathLiveField(
            value="x",
            placeholder="x",
            aria_label="Cartesian free variable",
        )
        self._cartesian_samples = widgets.BoundedIntText(
            description="Samples:",
            min=2,
            max=100000,
            value=max(int(self._figure.samples or 500), 2),
            layout=widgets.Layout(width="100%"),
        )

        self._parametric_x = MathLiveField(
            placeholder=r"\cos(t)",
            aria_label="Parametric x(t)",
        )
        self._parametric_y = MathLiveField(
            placeholder=r"\sin(t)",
            aria_label="Parametric y(t)",
        )
        self._parameter_variable = MathLiveField(
            value="t",
            placeholder="t",
            aria_label="Parametric parameter",
        )
        self._parameter_min = MathLiveField(
            value="0",
            placeholder="0",
            aria_label="Parametric parameter minimum",
        )
        self._parameter_max = MathLiveField(
            value=r"2\pi",
            placeholder=r"2\pi",
            aria_label="Parametric parameter maximum",
        )
        self._parametric_samples = widgets.BoundedIntText(
            description="Samples:",
            min=2,
            max=100000,
            value=max(int(self._figure.samples or 500), 2),
            layout=widgets.Layout(width="100%"),
        )

        self._field_expression = MathLiveField(
            placeholder=r"x^2 + y^2",
            aria_label="Scalar-field expression",
        )
        self._field_x_variable = MathLiveField(
            value="x",
            placeholder="x",
            aria_label="Scalar-field x variable",
        )
        self._field_y_variable = MathLiveField(
            value="y",
            placeholder="y",
            aria_label="Scalar-field y variable",
        )
        self._field_grid_x = widgets.BoundedIntText(
            description="Grid x:",
            min=2,
            max=10000,
            value=120,
            layout=widgets.Layout(width="100%"),
        )
        self._field_grid_y = widgets.BoundedIntText(
            description="Grid y:",
            min=2,
            max=10000,
            value=120,
            layout=widgets.Layout(width="100%"),
        )

        self._parameter_preview = widgets.HTML(
            value="",
            layout=widgets.Layout(width="100%", margin="4px 0 0 0"),
        )
        self._error_box = widgets.HTML(
            value="",
            layout=widgets.Layout(width="100%", display="none"),
        )

        self._title = widgets.HTML("<b>Add plot</b>")
        self._subtitle = widgets.HTML(
            value="Choose a plot type, enter expressions, and the toolkit will create missing parameters automatically.",
            layout=widgets.Layout(margin="0 0 4px 0"),
        )
        self._close_button = widgets.Button(
            description="✕",
            tooltip="Close plot editor",
            layout=widgets.Layout(width="32px", height="32px", padding="0px"),
        )
        self._close_button.on_click(lambda _button: self.close())
        self._cancel_button = widgets.Button(
            description="Cancel",
            tooltip="Discard plot editor changes",
            layout=widgets.Layout(width="auto", min_width="88px"),
        )
        self._cancel_button.on_click(lambda _button: self.close())
        self._apply_button = widgets.Button(
            description="Add plot",
            tooltip="Apply plot editor changes",
            layout=widgets.Layout(width="auto", min_width="96px"),
        )
        self._apply_button.on_click(self._on_apply_clicked)

        common_section = widgets.VBox(
            [
                self._labelled_row("Plot type", self._kind),
                self._labelled_row("Plot ID", self._id_text),
                self._labelled_row("Label", self._label_text),
                self._labelled_row("Views", self._views),
            ],
            layout=widgets.Layout(gap="8px", width="100%"),
        )

        self._cartesian_box = widgets.VBox(
            [
                self._labelled_row("Expression", self._cartesian_expression),
                self._labelled_row("Free variable", self._cartesian_variable),
                self._cartesian_samples,
            ],
            layout=widgets.Layout(gap="8px", width="100%"),
        )
        self._parametric_box = widgets.VBox(
            [
                self._labelled_row("x(t)", self._parametric_x),
                self._labelled_row("y(t)", self._parametric_y),
                self._labelled_row("Parameter", self._parameter_variable),
                self._labelled_row("t min", self._parameter_min),
                self._labelled_row("t max", self._parameter_max),
                self._parametric_samples,
            ],
            layout=widgets.Layout(gap="8px", width="100%", display="none"),
        )
        self._field_box = widgets.VBox(
            [
                self._labelled_row("Expression", self._field_expression),
                self._labelled_row("x variable", self._field_x_variable),
                self._labelled_row("y variable", self._field_y_variable),
                self._field_grid_x,
                self._field_grid_y,
            ],
            layout=widgets.Layout(gap="8px", width="100%", display="none"),
        )

        header = widgets.HBox(
            [self._title, self._close_button],
            layout=widgets.Layout(
                justify_content="space-between",
                align_items="center",
                width="100%",
                min_width="0",
            ),
        )
        actions = widgets.HBox(
            [self._cancel_button, self._apply_button],
            layout=widgets.Layout(
                justify_content="flex-end",
                align_items="center",
                gap="8px",
                width="100%",
            ),
        )

        self._panel = widgets.VBox(
            [
                header,
                self._subtitle,
                common_section,
                self._cartesian_box,
                self._parametric_box,
                self._field_box,
                self._parameter_preview,
                self._error_box,
                actions,
            ],
            layout=widgets.Layout(
                width="min(720px, calc(100vw - 32px))",
                max_height="calc(100vh - 32px)",
                display="none",
                padding="14px",
                gap="10px",
                border="1px solid rgba(15, 23, 42, 0.14)",
                border_radius="12px",
                background_color="white",
                box_shadow="0 14px 40px rgba(15, 23, 42, 0.24)",
                overflow_y="auto",
                overflow_x="hidden",
                align_items="stretch",
            ),
        )
        self._panel.add_class("gu-plot-editor-panel")

        self._modal = widgets.Box(
            [self._panel],
            layout=widgets.Layout(
                display="none",
                position="fixed",
                top="0",
                left="0",
                width="100vw",
                height="100vh",
                align_items="center",
                justify_content="center",
                background_color="rgba(15, 23, 42, 0.16)",
                z_index="1002",
                overflow="hidden",
            ),
        )
        self._modal.add_class("gu-plot-editor-modal")

        if self._style not in self._modal_host.children:
            self._modal_host.children += (self._style,)
        if self._modal not in self._modal_host.children:
            self._modal_host.children += (self._modal,)

        self._kind.observe(self._on_kind_changed, names="value")
        for observed in (
            self._cartesian_expression,
            self._cartesian_variable,
            self._parametric_x,
            self._parametric_y,
            self._parameter_variable,
            self._parameter_min,
            self._parameter_max,
            self._field_expression,
            self._field_x_variable,
            self._field_y_variable,
            self._views,
        ):
            observed.observe(self._on_form_value_changed, names="value")

    @property
    def panel_visible(self) -> bool:
        """Return whether the modal is currently open."""

        return self._is_open

    def open_for_new(self, *, default_kind: PlotEditorKind = "cartesian") -> None:
        """Open the dialog preloaded for creating a new plot."""

        self._refresh_view_options(selected=(self._figure.views.current_id,))
        self._editing_plot_id = None
        self._id_text.disabled = False
        self._title.value = "<b>Add plot</b>"
        self._apply_button.description = "Add plot"
        self._apply_button.tooltip = "Create the plot from the entered expressions"
        self._clear_error()
        self._load_defaults(default_kind=default_kind)
        self._set_open(True)

    def open_for_plot(self, plot_id: str) -> None:
        """Open the dialog with fields loaded from an existing runtime plot."""

        plot = self._figure.plots.get(plot_id)
        if plot is None:
            raise KeyError(plot_id)

        self._editing_plot_id = plot_id
        self._id_text.disabled = True
        self._title.value = "<b>Edit plot</b>"
        self._apply_button.description = "Apply"
        self._apply_button.tooltip = "Update the plot from the entered expressions"
        self._clear_error()
        self._load_plot(plot)
        self._set_open(True)

    def close(self) -> None:
        """Hide the dialog and clear transient error state."""

        self._clear_error()
        self._set_open(False)

    def _set_open(self, value: bool) -> None:
        self._is_open = bool(value)
        self._panel.layout.display = "flex" if self._is_open else "none"
        self._modal.layout.display = "flex" if self._is_open else "none"

    def _load_defaults(self, *, default_kind: PlotEditorKind) -> None:
        """Populate a fresh new-plot form using figure defaults."""

        self._suspend_observers = True
        try:
            self._kind.value = default_kind
            self._id_text.value = ""
            self._label_text.value = ""
            self._cartesian_expression.value = ""
            self._cartesian_variable.value = "x"
            self._cartesian_samples.value = max(int(self._figure.samples or 500), 2)
            self._parametric_x.value = ""
            self._parametric_y.value = ""
            self._parameter_variable.value = "t"
            self._parameter_min.value = "0"
            self._parameter_max.value = r"2\pi"
            self._parametric_samples.value = max(int(self._figure.samples or 500), 2)
            self._field_expression.value = ""
            self._field_x_variable.value = "x"
            self._field_y_variable.value = "y"
            self._field_grid_x.value = 120
            self._field_grid_y.value = 120
            self._sync_section_visibility()
            self._update_parameter_preview()
        finally:
            self._suspend_observers = False
            self._sync_section_visibility()
            self._update_parameter_preview()

    def _load_plot(self, plot: Any) -> None:
        """Load widget state from an existing plot runtime object."""

        selected_views = tuple(str(view_id) for view_id in getattr(plot, "views", ())) or (
            self._figure.views.current_id,
        )
        self._refresh_view_options(selected=selected_views)

        kind = self._kind_for_plot(plot)
        self._suspend_observers = True
        try:
            self._kind.value = kind
            self._id_text.value = str(getattr(plot, "id", ""))
            self._label_text.value = str(getattr(plot, "label", ""))
            self._sync_section_visibility()

            if kind == "cartesian":
                assert isinstance(plot, Plot)
                self._cartesian_expression.value = _to_latex(plot.symbolic_expression)
                self._cartesian_variable.value = _to_latex(plot._var, default="x")
                self._cartesian_samples.value = max(int(plot.samples or self._figure.samples or 500), 2)
            elif kind == "parametric":
                assert isinstance(plot, ParametricPlot)
                self._parametric_x.value = _to_latex(plot.x_expression)
                self._parametric_y.value = _to_latex(plot.y_expression)
                self._parameter_variable.value = _to_latex(plot.parameter_var, default="t")
                self._parameter_min.value = _to_latex(plot.parameter_domain[0], default="0")
                self._parameter_max.value = _to_latex(plot.parameter_domain[1], default=r"2\pi")
                self._parametric_samples.value = max(int(plot.samples or self._figure.samples or 500), 2)
            else:
                assert isinstance(plot, ScalarFieldPlot)
                self._field_expression.value = _to_latex(plot.symbolic_expression)
                self._field_x_variable.value = _to_latex(plot.x_var, default="x")
                self._field_y_variable.value = _to_latex(plot.y_var, default="y")
                grid_x, grid_y = plot.grid or plot.DEFAULT_GRID
                self._field_grid_x.value = max(int(grid_x), 2)
                self._field_grid_y.value = max(int(grid_y), 2)
        finally:
            self._suspend_observers = False
            self._sync_section_visibility()
            self._update_parameter_preview()

    @staticmethod
    def _kind_for_plot(plot: Any) -> PlotEditorKind:
        """Map one runtime plot object to the corresponding editor mode."""

        if isinstance(plot, ParametricPlot):
            return "parametric"
        if isinstance(plot, ScalarFieldPlot):
            if plot.render_mode == "contour":
                return "contour"
            if plot.preset == "temperature":
                return "temperature"
            return "density"
        return "cartesian"

    def _refresh_view_options(self, *, selected: tuple[str, ...]) -> None:
        """Refresh view choices from the current figure registry."""

        options: list[tuple[str, str]] = []
        for view in self._figure.views.values():
            label = view.id if view.title == view.id else f"{view.id} — {view.title}"
            options.append((label, view.id))
        self._views.options = tuple(options)
        available = {value for _label, value in options}
        filtered = tuple(view_id for view_id in selected if view_id in available)
        self._views.value = filtered or ((self._figure.views.current_id,) if self._figure.views.current_id in available else ())

    def _collect_draft(self) -> PlotEditorDraft:
        """Collect the current widget values into a detached draft."""

        return PlotEditorDraft(
            kind=self._kind.value,
            plot_id=(self._id_text.value.strip() or None),
            label=self._label_text.value,
            view_ids=tuple(str(view_id) for view_id in self._views.value),
            cartesian_expression_latex=self._cartesian_expression.value,
            cartesian_var_latex=self._cartesian_variable.value,
            cartesian_samples=int(self._cartesian_samples.value),
            parametric_x_latex=self._parametric_x.value,
            parametric_y_latex=self._parametric_y.value,
            parameter_var_latex=self._parameter_variable.value,
            parameter_min_latex=self._parameter_min.value,
            parameter_max_latex=self._parameter_max.value,
            parametric_samples=int(self._parametric_samples.value),
            field_expression_latex=self._field_expression.value,
            field_x_var_latex=self._field_x_variable.value,
            field_y_var_latex=self._field_y_variable.value,
            field_grid_x=int(self._field_grid_x.value),
            field_grid_y=int(self._field_grid_y.value),
        )

    def _set_error(self, message: str) -> None:
        """Display a validation/apply error in the dialog."""

        self._error_box.value = (
            f"<div class='gu-plot-editor-error'><b>Could not apply plot.</b> {html.escape(message)}</div>"
        )
        self._error_box.layout.display = "block"

    def _clear_error(self) -> None:
        """Hide the validation/apply error area."""

        self._error_box.value = ""
        self._error_box.layout.display = "none"

    def _on_apply_clicked(self, _button: widgets.Button) -> None:
        """Validate the draft, apply it through Figure, and close on success."""

        draft = self._collect_draft()
        existing = (
            self._figure.plots.get(self._editing_plot_id)
            if self._editing_plot_id is not None
            else None
        )
        try:
            if not draft.view_ids:
                raise ValueError("Select at least one target view.")
            apply_plot_editor_draft(self._figure, draft, existing_plot=existing)
        except Exception as exc:
            self._set_error(str(exc))
            return
        self.close()

    def _on_kind_changed(self, _change: dict[str, Any]) -> None:
        """Switch visible sections when the selected plot family changes."""

        if self._suspend_observers:
            return
        self._sync_section_visibility()
        self._update_parameter_preview()

    def _on_form_value_changed(self, _change: dict[str, Any]) -> None:
        """Refresh the parameter preview for user edits."""

        if self._suspend_observers:
            return
        self._update_parameter_preview()

    def _sync_section_visibility(self) -> None:
        """Show only the section relevant to the selected plot family."""

        kind = self._kind.value
        self._cartesian_box.layout.display = "flex" if kind == "cartesian" else "none"
        self._parametric_box.layout.display = "flex" if kind == "parametric" else "none"
        self._field_box.layout.display = (
            "flex" if kind in {"contour", "density", "temperature"} else "none"
        )

    def _update_parameter_preview(self) -> None:
        """Compute and render the parameter-inference status line."""

        preview = _draft_parameter_preview(self._figure, self._collect_draft())
        if preview.error is not None:
            self._parameter_preview.value = (
                f"<div class='gu-plot-editor-note'><i>{html.escape(preview.error)}</i></div>"
            )
            return
        if not preview.will_create and not preview.will_reuse:
            self._parameter_preview.value = (
                "<div class='gu-plot-editor-note'>No extra parameters inferred from the current expression.</div>"
            )
            return

        parts: list[str] = []
        if preview.will_create:
            parts.append(
                "Will create parameters: <code>"
                + html.escape(", ".join(preview.will_create))
                + "</code>"
            )
        if preview.will_reuse:
            parts.append(
                "Will reuse parameters: <code>"
                + html.escape(", ".join(preview.will_reuse))
                + "</code>"
            )
        self._parameter_preview.value = (
            "<div class='gu-plot-editor-note'>" + "<br>".join(parts) + "</div>"
        )

    @staticmethod
    def _labelled_row(title: str, widget: widgets.Widget) -> widgets.VBox:
        """Return one simple labelled editor row."""

        return widgets.VBox(
            [widgets.HTML(f"<b>{html.escape(title)}</b>"), widget],
            layout=widgets.Layout(width="100%", gap="4px"),
        )

    @staticmethod
    def _dialog_style_html() -> str:
        """Return small CSS helpers for the plot-composer dialog."""

        return (
            "<style>"
            ".gu-plot-editor-panel .widget-label {font-weight: 600 !important;}"
            ".gu-plot-editor-note {color: #334155; font-size: 13px; line-height: 1.35;}"
            ".gu-plot-editor-error {color: #991b1b; background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.18); border-radius: 8px; padding: 8px 10px;}"
            ".gu-plot-editor-panel code {background: rgba(15, 23, 42, 0.06); padding: 1px 4px; border-radius: 4px;}"
            "</style>"
        )


__all__ = [
    "ParameterPreview",
    "PlotComposerDialog",
    "PlotEditorDraft",
    "PlotEditorKind",
    "apply_plot_editor_draft",
]
