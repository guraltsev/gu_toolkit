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
import uuid
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
from .widget_chrome import (
    ModalDialogBridge,
    attach_host_children,
    build_modal_overlay,
    build_modal_panel,
    configure_action_button,
    configure_icon_button,
    full_width_layout,
    hbox,
    hosted_modal_dimensions,
    labelled_field,
    responsive_row,
    set_tab_button_selected,
    shared_style_widget,
    vbox,
)

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
    visible: bool = True


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


def _title_symbol_latex(value: str, *, default: str) -> str:
    """Return the compact LaTeX symbol string shown in responsive field titles."""

    source = str(value or "").strip()
    return source or default


def _parametric_axis_title_latex(axis_name: str, parameter_latex: str) -> str:
    """Return the compact label shown above ``x(t)``/``y(t)`` inputs."""

    parameter = _title_symbol_latex(parameter_latex, default="t")
    return rf"{axis_name}\left({parameter}\right)"


def _parametric_bound_title_latex(parameter_latex: str, *, bound: Literal["min", "max"]) -> str:
    """Return the compact label shown above parameter bound inputs."""

    parameter = _title_symbol_latex(parameter_latex, default="t")
    return rf"{parameter}_{{\mathrm{{{bound}}}}}"


def _math_field_label(latex: str) -> widgets.HTMLMath:
    """Return one MathJax-backed form label styled like the shared text labels."""

    label = widgets.HTMLMath(
        value=latex,
        layout=widgets.Layout(margin="0px", min_width="0"),
    )
    label.add_class("gu-form-field-label")
    return label


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
        "visible": bool(draft.visible),
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

    The dialog now reuses the shared modal/button chrome used elsewhere in the
    toolkit. Formula entry stays front-and-center while labels, identifiers,
    visibility, views, and sampling live in a separate Advanced tab.
    """

    def __init__(self, figure: Figure, *, modal_host: widgets.Box) -> None:
        self._figure = figure
        self._modal_host = modal_host
        self._editing_plot_id: str | None = None
        self._is_open = False
        self._error_open = False
        self._suspend_observers = False
        self._active_tab: Literal["formula", "advanced"] = "formula"
        self._modal_class = f"gu-plot-editor-modal-{uuid.uuid4().hex[:8]}"
        self._error_modal_class = f"{self._modal_class}-error"

        self._style = shared_style_widget(self._dialog_style_css())

        self._kind = widgets.Dropdown(
            options=(
                ("Function y = f(x)", "cartesian"),
                ("Parametric (x(t), y(t))", "parametric"),
                ("Contour z = f(x, y)", "contour"),
                ("Density heatmap", "density"),
                ("Temperature heatmap", "temperature"),
            ),
            value="cartesian",
            description="",
            layout=full_width_layout(),
        )
        self._id_text = widgets.Text(
            description="",
            placeholder="Auto",
            layout=full_width_layout(),
        )
        self._label_text = widgets.Text(
            description="",
            placeholder="Legend label",
            layout=full_width_layout(),
        )
        self._views = widgets.SelectMultiple(
            description="",
            options=(),
            value=(),
            layout=widgets.Layout(width="100%", min_width="0", min_height="96px"),
        )
        self._visible_toggle = widgets.Checkbox(
            value=True,
            description="Visible",
            indent=False,
            layout=widgets.Layout(width="auto", min_width="0"),
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
            min=2,
            max=100000,
            value=max(int(self._figure.samples or 500), 2),
            description="",
            layout=full_width_layout(),
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
            min=2,
            max=100000,
            value=max(int(self._figure.samples or 500), 2),
            description="",
            layout=full_width_layout(),
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
            min=2,
            max=10000,
            value=120,
            description="",
            layout=full_width_layout(),
        )
        self._field_grid_y = widgets.BoundedIntText(
            min=2,
            max=10000,
            value=120,
            description="",
            layout=full_width_layout(),
        )

        self._title_eyebrow = widgets.HTML(
            "Plot editor",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self._title_eyebrow.add_class("gu-modal-title-eyebrow")
        self._title = widgets.HTML(
            "Create plot",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self._title.add_class("gu-modal-title-text")
        self._title_context = widgets.HTML(
            "Choose a plot family, enter formulas, and assign the plot to one or more views.",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self._title_context.add_class("gu-modal-subtitle")
        self._title_block = vbox(
            [self._title_eyebrow, self._title, self._title_context],
            gap="2px",
            extra_classes=("gu-modal-header-copy",),
        )

        self._close_button = widgets.Button(
            description="Close plot editor",
            tooltip="Close plot editor",
        )
        configure_icon_button(
            self._close_button,
            role="close",
            size_px=28,
            extra_classes=("gu-plot-editor-close-button",),
        )
        self._close_button.on_click(lambda _button: self.close())

        self._formula_tab_button = widgets.Button(
            description="Formula",
            tooltip="Show formula settings",
            layout=widgets.Layout(flex="1 1 120px", width="auto", min_width="0"),
        )
        configure_action_button(
            self._formula_tab_button,
            variant="tab",
            min_width_px=0,
            extra_classes=("gu-plot-editor-tab-button",),
        )
        self._formula_tab_button.on_click(lambda _button: self._set_tab("formula"))

        self._advanced_tab_button = widgets.Button(
            description="Advanced",
            tooltip="Show advanced settings",
            layout=widgets.Layout(flex="1 1 120px", width="auto", min_width="0"),
        )
        configure_action_button(
            self._advanced_tab_button,
            variant="tab",
            min_width_px=0,
            extra_classes=("gu-plot-editor-tab-button",),
        )
        self._advanced_tab_button.on_click(lambda _button: self._set_tab("advanced"))

        self._cancel_button = widgets.Button(
            description="Cancel",
            tooltip="Discard plot editor changes",
        )
        configure_action_button(self._cancel_button, variant="secondary", min_width_px=88)
        self._cancel_button.on_click(lambda _button: self.close())

        self._apply_button = widgets.Button(
            description="Create",
            tooltip="Create the plot from the entered expressions",
        )
        configure_action_button(self._apply_button, variant="primary", min_width_px=96)
        self._apply_button.on_click(self._on_apply_clicked)

        self._status_bar = widgets.HTML("", layout=full_width_layout())
        self._status_bar.add_class("gu-modal-status-bar")
        self._status_bar.add_class("gu-plot-editor-status-bar")
        self._parameter_preview = self._status_bar

        visibility_row = widgets.HBox(
            [self._visible_toggle],
            layout=widgets.Layout(width="100%", min_width="0", align_items="center"),
        )

        self._parametric_x_label = _math_field_label(r"x\left(t\right)")
        self._parametric_y_label = _math_field_label(r"y\left(t\right)")
        self._parameter_min_label = _math_field_label(r"t_{\mathrm{min}}")
        self._parameter_max_label = _math_field_label(r"t_{\mathrm{max}}")

        self._plot_type_field = labelled_field(
            "Plot type",
            self._kind,
            flex="0 1 260px",
        )
        self._plot_type_row = responsive_row(
            [self._plot_type_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
        )

        self._cartesian_expression_field = labelled_field("Expression", self._cartesian_expression)
        self._cartesian_variable_field = labelled_field(
            "Free variable",
            self._cartesian_variable,
            flex="0 1 190px",
        )
        self._cartesian_variable_row = responsive_row(
            [self._cartesian_variable_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
        )
        self._cartesian_box = vbox(
            [self._cartesian_expression_field, self._cartesian_variable_row],
            gap="10px",
        )

        self._parametric_x_field = labelled_field(self._parametric_x_label, self._parametric_x)
        self._parametric_y_field = labelled_field(self._parametric_y_label, self._parametric_y)
        self._parameter_variable_field = labelled_field(
            "Parameter",
            self._parameter_variable,
            flex="0 1 190px",
        )
        self._parameter_min_field = labelled_field(
            self._parameter_min_label,
            self._parameter_min,
            flex="1 1 190px",
        )
        self._parameter_max_field = labelled_field(
            self._parameter_max_label,
            self._parameter_max,
            flex="1 1 190px",
        )
        self._parametric_parameter_row = responsive_row(
            [
                self._parameter_variable_field,
                self._parameter_min_field,
                self._parameter_max_field,
            ],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
        )
        self._parametric_box = vbox(
            [
                self._parametric_x_field,
                self._parametric_y_field,
                self._parametric_parameter_row,
            ],
            gap="10px",
            display="none",
        )

        self._field_expression_field = labelled_field("Expression", self._field_expression)
        self._field_x_variable_field = labelled_field(
            "x variable",
            self._field_x_variable,
            flex="0 1 190px",
        )
        self._field_y_variable_field = labelled_field(
            "y variable",
            self._field_y_variable,
            flex="0 1 190px",
        )
        self._field_variable_row = responsive_row(
            [self._field_x_variable_field, self._field_y_variable_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
        )
        self._field_box = vbox(
            [self._field_expression_field, self._field_variable_row],
            gap="10px",
            display="none",
        )

        self._views_field = labelled_field("Views", self._views)
        self._label_field = labelled_field("Label", self._label_text, flex="1 1 280px")
        self._id_field = labelled_field("Plot ID", self._id_text, flex="0 1 220px")
        self._visibility_field = labelled_field(
            "Visibility",
            visibility_row,
            flex="0 1 150px",
        )
        self._advanced_meta_row = responsive_row(
            [self._label_field, self._id_field, self._visibility_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
        )

        self._cartesian_samples_field = labelled_field(
            "Samples",
            self._cartesian_samples,
            flex="0 1 190px",
        )
        self._cartesian_samples_row = responsive_row(
            [self._cartesian_samples_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
        )
        self._cartesian_advanced_box = vbox(
            [self._cartesian_samples_row],
            gap="8px",
        )

        self._parametric_samples_field = labelled_field(
            "Samples",
            self._parametric_samples,
            flex="0 1 190px",
        )
        self._parametric_samples_row = responsive_row(
            [self._parametric_samples_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
        )
        self._parametric_advanced_box = vbox(
            [self._parametric_samples_row],
            gap="8px",
            display="none",
        )

        self._field_grid_x_field = labelled_field(
            "Grid x",
            self._field_grid_x,
            flex="0 1 190px",
        )
        self._field_grid_y_field = labelled_field(
            "Grid y",
            self._field_grid_y,
            flex="0 1 190px",
        )
        self._field_grid_row = responsive_row(
            [self._field_grid_x_field, self._field_grid_y_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
        )
        self._field_advanced_box = vbox(
            [self._field_grid_row],
            gap="8px",
            display="none",
        )

        self._formula_tab = vbox(
            [
                self._plot_type_row,
                self._cartesian_box,
                self._parametric_box,
                self._field_box,
            ],
            gap="12px",
            extra_classes=("gu-plot-editor-tab-panel",),
        )
        self._advanced_tab = vbox(
            [
                self._advanced_meta_row,
                self._views_field,
                self._cartesian_advanced_box,
                self._parametric_advanced_box,
                self._field_advanced_box,
            ],
            gap="12px",
            display="none",
            extra_classes=("gu-plot-editor-tab-panel",),
        )

        header = hbox(
            [self._title_block, self._close_button],
            justify_content="space-between",
            align_items="flex-start",
            gap="12px",
            extra_classes=("gu-modal-header",),
        )
        tabs = hbox(
            [self._formula_tab_button, self._advanced_tab_button],
            justify_content="flex-start",
            align_items="stretch",
            gap="4px",
            flex_flow="row wrap",
            extra_classes=("gu-plot-editor-tab-bar", "gu-tab-bar"),
        )
        actions = hbox(
            [self._cancel_button, self._apply_button],
            justify_content="flex-end",
            align_items="center",
            gap="8px",
            flex_flow="row wrap",
        )

        panel_width, panel_min_width, panel_max_width = hosted_modal_dimensions(
            preferred_width_px=720,
            minimum_width_px=360,
        )
        self._panel = build_modal_panel(
            [
                header,
                tabs,
                self._formula_tab,
                self._advanced_tab,
                actions,
                self._status_bar,
            ],
            width=panel_width,
            min_width=panel_min_width,
            max_width=panel_max_width,
            padding="16px",
            gap="12px",
            display="none",
            extra_classes=("gu-plot-editor-panel",),
        )
        self._modal = build_modal_overlay(
            self._panel,
            hosted=True,
            z_index="1002",
            background_color="rgba(15, 23, 42, 0.16)",
            modal_class=self._modal_class,
        )
        self._modal.add_class("gu-plot-editor-modal")

        self._error_eyebrow = widgets.HTML(
            "Plot editor",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self._error_eyebrow.add_class("gu-modal-title-eyebrow")
        self._error_title = widgets.HTML(
            "Could not apply plot",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self._error_title.add_class("gu-modal-title-text")
        self._error_title.add_class("gu-plot-editor-error-title-text")
        self._error_context = widgets.HTML(
            "Review the current tab, adjust the draft, and try again.",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self._error_context.add_class("gu-modal-subtitle")
        self._error_title_block = vbox(
            [self._error_eyebrow, self._error_title, self._error_context],
            gap="2px",
            extra_classes=("gu-modal-header-copy",),
        )
        self._error_close_button = widgets.Button(
            description="Close error dialog",
            tooltip="Close error dialog",
        )
        configure_icon_button(
            self._error_close_button,
            role="close",
            size_px=24,
            extra_classes=("gu-plot-editor-error-close-button",),
        )
        self._error_close_button.on_click(lambda _button: self._hide_error_dialog())
        self._error_message = widgets.HTML("", layout=full_width_layout())
        self._error_message.add_class("gu-plot-editor-error-message")
        self._error_ok_button = widgets.Button(
            description="OK",
            tooltip="Close error dialog",
        )
        configure_action_button(self._error_ok_button, variant="primary", min_width_px=72)
        self._error_ok_button.on_click(lambda _button: self._hide_error_dialog())
        self._error_box = self._error_message

        error_header = hbox(
            [self._error_title_block, self._error_close_button],
            justify_content="space-between",
            align_items="flex-start",
            gap="12px",
            extra_classes=("gu-modal-header",),
        )
        error_actions = hbox(
            [self._error_ok_button],
            justify_content="flex-end",
            align_items="center",
            gap="8px",
        )
        error_width, error_min_width, error_max_width = hosted_modal_dimensions(
            preferred_width_px=420,
            minimum_width_px=300,
        )
        self._error_panel = build_modal_panel(
            [error_header, self._error_message, error_actions],
            width=error_width,
            min_width=error_min_width,
            max_width=error_max_width,
            padding="14px",
            gap="12px",
            display="none",
            extra_classes=("gu-plot-editor-error-panel",),
        )
        self._error_modal = build_modal_overlay(
            self._error_panel,
            hosted=True,
            z_index="1003",
            background_color="rgba(15, 23, 42, 0.22)",
            modal_class=self._error_modal_class,
        )

        zero_layout = widgets.Layout(width="0px", height="0px", margin="0px")
        self._modal_bridge = ModalDialogBridge(
            modal_class=self._modal_class,
            panel_selector=".gu-plot-editor-panel",
            close_selector=".gu-plot-editor-close-button",
            title_selector=".gu-modal-title-text",
            dialog_open=False,
            dialog_label="Plot editor",
            layout=zero_layout,
        )
        self._modal_bridge.on_msg(self._handle_main_dialog_message)
        self._error_bridge = ModalDialogBridge(
            modal_class=self._error_modal_class,
            panel_selector=".gu-plot-editor-error-panel",
            close_selector=".gu-plot-editor-error-close-button",
            title_selector=".gu-plot-editor-error-title-text",
            dialog_open=False,
            dialog_label="Plot editor error",
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._error_bridge.on_msg(self._handle_error_dialog_message)

        attach_host_children(
            self._modal_host,
            self._style,
            self._modal,
            self._error_modal,
            self._modal_bridge,
            self._error_bridge,
        )

        self._kind.observe(self._on_kind_changed, names="value")
        self._parameter_variable.observe(self._on_parameter_variable_changed, names="value")

        self._update_parametric_prompt_copy()
        self._set_tab("formula")
        self._sync_section_visibility()
        self._refresh_status_bar()
        self._sync_open_state()

    @property
    def panel_visible(self) -> bool:
        """Return whether the modal is currently open."""

        return self._is_open

    def open_for_new(self, *, default_kind: PlotEditorKind = "cartesian") -> None:
        """Open the dialog preloaded for creating a new plot."""

        self._refresh_view_options(selected=(self._figure.views.current_id,))
        self._editing_plot_id = None
        self._id_text.disabled = False
        self._title.value = "Create plot"
        self._title_context.value = "Choose a plot family, enter formulas, and assign the plot to one or more views."
        self._apply_button.description = "Create"
        self._apply_button.tooltip = "Create the plot from the entered expressions"
        self._modal_bridge.dialog_label = "Create plot"
        self._clear_error()
        self._set_tab("formula")
        self._load_defaults(default_kind=default_kind)
        self._set_open(True)

    def open_for_plot(self, plot_id: str) -> None:
        """Open the dialog with fields loaded from an existing runtime plot."""

        plot = self._figure.plots.get(plot_id)
        if plot is None:
            raise KeyError(plot_id)

        self._editing_plot_id = plot_id
        self._id_text.disabled = True
        self._title.value = "Edit plot"
        self._title_context.value = f"Update <code>{html.escape(plot_id)}</code> and keep its plot id stable."
        self._apply_button.description = "Apply"
        self._apply_button.tooltip = "Update the plot from the entered expressions"
        self._modal_bridge.dialog_label = f"Edit plot {plot_id}"
        self._clear_error()
        self._set_tab("formula")
        self._load_plot(plot)
        self._set_open(True)

    def close(self) -> None:
        """Hide the dialog and clear transient error state."""

        self._clear_error()
        self._set_open(False)

    def _handle_main_dialog_message(self, _widget: Any, content: Any, _buffers: Any) -> None:
        if not isinstance(content, dict):
            return
        if content.get("type") != "dialog_request":
            return
        if content.get("action") == "close":
            self.close()

    def _handle_error_dialog_message(self, _widget: Any, content: Any, _buffers: Any) -> None:
        if not isinstance(content, dict):
            return
        if content.get("type") != "dialog_request":
            return
        if content.get("action") == "close":
            self._hide_error_dialog()

    def _set_open(self, value: bool) -> None:
        self._is_open = bool(value)
        self._sync_open_state()

    def _sync_open_state(self) -> None:
        self._panel.layout.display = "flex" if self._is_open else "none"
        self._modal.layout.display = "flex" if self._is_open else "none"
        self._error_panel.layout.display = "flex" if self._error_open else "none"
        self._error_modal.layout.display = "flex" if self._error_open else "none"
        self._modal_bridge.dialog_open = self._is_open and not self._error_open
        self._error_bridge.dialog_open = self._error_open

    def _set_tab(self, tab_name: Literal["formula", "advanced"]) -> None:
        self._active_tab = tab_name
        self._formula_tab.layout.display = "flex" if tab_name == "formula" else "none"
        self._advanced_tab.layout.display = "flex" if tab_name == "advanced" else "none"
        set_tab_button_selected(self._formula_tab_button, tab_name == "formula")
        set_tab_button_selected(self._advanced_tab_button, tab_name == "advanced")

    def _on_parameter_variable_changed(self, _change: dict[str, Any]) -> None:
        """Refresh compact parametric labels when the parameter symbol changes."""

        if self._suspend_observers:
            return
        self._update_parametric_prompt_copy()

    def _update_parametric_prompt_copy(self) -> None:
        """Keep compact parametric field titles in sync with the chosen parameter."""

        parameter_latex = _title_symbol_latex(self._parameter_variable.value, default="t")
        self._parametric_x_label.value = _parametric_axis_title_latex("x", parameter_latex)
        self._parametric_y_label.value = _parametric_axis_title_latex("y", parameter_latex)
        self._parameter_min_label.value = _parametric_bound_title_latex(
            parameter_latex,
            bound="min",
        )
        self._parameter_max_label.value = _parametric_bound_title_latex(
            parameter_latex,
            bound="max",
        )
        parameter_name = str(self._parameter_variable.value or "").strip() or "t"
        self._parametric_x.aria_label = f"Parametric x({parameter_name})"
        self._parametric_y.aria_label = f"Parametric y({parameter_name})"
        self._parameter_min.aria_label = f"Minimum value for {parameter_name}"
        self._parameter_max.aria_label = f"Maximum value for {parameter_name}"

    def _refresh_status_bar(self) -> None:
        mode_label = {
            "cartesian": "Function y = f(x)",
            "parametric": "Parametric curve",
            "contour": "Contour plot",
            "density": "Density heatmap",
            "temperature": "Temperature heatmap",
        }.get(self._kind.value, "Plot")
        action_word = self._apply_button.description or "Apply"
        resolution_word = "sampling" if self._kind.value in {"cartesian", "parametric"} else "grid resolution"
        message = (
            f"{mode_label}. Expressions are validated when you click {action_word}. "
            f"Advanced settings hold label, id, visibility, views, and {resolution_word}."
        )
        self._status_bar.value = f"<div>{html.escape(message)}</div>"

    def _load_defaults(self, *, default_kind: PlotEditorKind) -> None:
        """Populate a fresh new-plot form using figure defaults."""

        self._suspend_observers = True
        try:
            self._kind.value = default_kind
            self._id_text.value = ""
            self._label_text.value = ""
            self._visible_toggle.value = True
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
        finally:
            self._suspend_observers = False
            self._update_parametric_prompt_copy()
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
            self._visible_toggle.value = bool(getattr(plot, "visible", True))

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
            self._update_parametric_prompt_copy()
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
        fallback = (self._figure.views.current_id,) if self._figure.views.current_id in available else ()
        self._views.value = filtered or fallback

    def _collect_draft(self) -> PlotEditorDraft:
        """Collect the current widget values into a detached draft."""

        return PlotEditorDraft(
            kind=self._kind.value,
            plot_id=(self._id_text.value.strip() or None),
            label=self._label_text.value,
            view_ids=tuple(str(view_id) for view_id in self._views.value),
            visible=bool(self._visible_toggle.value),
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
        """Open the secondary error dialog for one apply failure."""

        self._show_error_dialog(message)

    def _clear_error(self) -> None:
        """Hide the secondary error dialog and clear its contents."""

        self._hide_error_dialog(clear_message=True)

    def _show_error_dialog(self, message: str) -> None:
        self._error_message.value = (
            "<div class='gu-plot-editor-error-body'>"
            + html.escape(message)
            + "</div>"
        )
        self._error_open = True
        self._sync_open_state()

    def _hide_error_dialog(self, *, clear_message: bool = False) -> None:
        self._error_open = False
        if clear_message:
            self._error_message.value = ""
        self._sync_open_state()

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
                self._set_tab("advanced")
                raise ValueError("Select at least one target view.")
            apply_plot_editor_draft(self._figure, draft, existing_plot=existing)
        except Exception as exc:
            self._set_tab(self._error_tab_name(str(exc)))
            self._set_error(str(exc))
            return
        self.close()

    def _on_kind_changed(self, _change: dict[str, Any]) -> None:
        """Switch visible sections when the selected plot family changes."""

        if self._suspend_observers:
            return
        self._update_parametric_prompt_copy()
        self._sync_section_visibility()
        self._refresh_status_bar()

    def _sync_section_visibility(self) -> None:
        """Show only the sections relevant to the selected plot family."""

        kind = self._kind.value
        self._cartesian_box.layout.display = "flex" if kind == "cartesian" else "none"
        self._parametric_box.layout.display = "flex" if kind == "parametric" else "none"
        self._field_box.layout.display = "flex" if kind in {"contour", "density", "temperature"} else "none"
        self._cartesian_advanced_box.layout.display = "flex" if kind == "cartesian" else "none"
        self._parametric_advanced_box.layout.display = "flex" if kind == "parametric" else "none"
        self._field_advanced_box.layout.display = (
            "flex" if kind in {"contour", "density", "temperature"} else "none"
        )

    def _update_parameter_preview(self) -> None:
        """Refresh the subtle bottom status bar without live compilation feedback."""

        self._refresh_status_bar()

    @staticmethod
    def _error_tab_name(message: str) -> Literal["formula", "advanced"]:
        """Heuristically map one apply error to the most relevant tab."""

        lowered = str(message or "").lower()
        if "view" in lowered:
            return "advanced"
        return "formula"

    @staticmethod
    def _dialog_style_css() -> str:
        """Return small plot-editor-specific CSS additions."""

        return (
            ".gu-plot-editor-panel,.gu-plot-editor-error-panel {overflow-x: hidden !important;}"
            ".gu-plot-editor-panel > *,.gu-plot-editor-error-panel > * {min-width: 0 !important;max-width: 100% !important;}"
            ".gu-plot-editor-tab-bar {width: 100% !important;}"
            ".gu-plot-editor-tab-button {flex: 1 1 120px !important;min-width: 0 !important;max-width: 100% !important;}"
            ".gu-plot-editor-tab-button button,.gu-plot-editor-tab-button .widget-button,.gu-plot-editor-tab-button .jupyter-button {width: 100% !important;}"
            ".gu-plot-editor-tab-panel,.gu-plot-editor-wrap-row {overflow-x: hidden !important;}"
            ".gu-plot-editor-panel :is(.gu-form-field,.gu-modal-row,.gu-modal-section,.widget-box,.jupyter-widgets,.widget-text,.widget-textarea,.widget-dropdown,.widget-select,.widget-select-multiple,.widget-html,.widget-htmlmath) {min-width: 0 !important;max-width: 100% !important;}"
            ".gu-plot-editor-panel :is(select[multiple], .widget-select-multiple select) {overflow-x: hidden !important;}"
            ".gu-plot-editor-panel .gu-modal-header-copy {gap: 2px !important;}"
            ".gu-plot-editor-error-body {color: #991b1b; background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.18); border-radius: 8px; padding: 10px 12px; line-height: 1.45;}"
        )


__all__ = [
    "ParameterPreview",
    "PlotComposerDialog",
    "PlotEditorDraft",
    "PlotEditorKind",
    "apply_plot_editor_draft",
]
