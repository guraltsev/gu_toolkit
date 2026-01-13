"""SmartException: an interactive exception coach for notebooks.

Purpose
-------
Provide a *pluggable* exception handler for IPython/Jupyter that displays a small,
actionable "diagnosis card" instead of a raw traceback. The handler tries multiple
diagnosis heuristics (from general to specific), ranks them by confidence, and lets
the user switch between plausible explanations.

Non-goals
---------
- This is not a security sandbox. Markdown/HTML rendering is intended for trusted,
  local notebook usage.
- This is not a full static analyzer. Diagnoses are heuristics and may be wrong.

Design overview
---------------
The module is organized as:

1) **Core types + registry**: dataclasses representing the exception context and
   candidate diagnoses; a registry decorator for built-in/custom diagnosers.
2) **Analysis**: best-effort extraction of the relevant source line/caret from the
   exception + traceback, and running the registry to produce ranked candidates.
3) **Built-in diagnosers**: lightweight heuristics (missing bracket, NameError typos,
   common math syntax mistakes, etc.).
4) **UI**: IPyWidgets-based renderer that shows the top candidate and navigation
   controls, plus an optional "Details" (traceback) panel.
5) **Activation**: convenience helpers to install/uninstall the handler in IPython.

Key invariants / assumptions
----------------------------
- The exception handler must never raise: failures in diagnostics/UI fall back to
  printing the original traceback.
- All diagnosers must be deterministic and side-effect free (except for internal
  caching of their last match).
- Optional dependencies (IPython, ipywidgets, markdown) are imported only at the
  boundaries that require them.

Public entrypoints
------------------
- ``GuideError``: raise this to show a 100% confidence guidance card.
- ``smart_exception_handler``: IPython custom exception handler callback.
- ``activate`` / ``deactivate``: install/uninstall the handler in IPython.
- ``register_diagnosis`` / ``Diagnosis``: extend the heuristics registry.

Testing pointer
---------------
See ``tests/test_smart_exception.py`` (suggested) or a dedicated notebook-based
verification suite.

Supported Python versions: 3.10+
"""

from __future__ import annotations

from dataclasses import dataclass
import html as _html
import logging
import re
import traceback
import types
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from typing import Generic, Optional, TypeVar

__gu_exports__ = ["GuideError"]
__gu_priority__ = 200
__gu_enabled__ = True

__all__ = ["GuideError"]


# === SECTION: Core types and registry [id: core]===
#
# The core layer is dependency-light so that the module is importable even
# without IPython/ipywidgets installed. UI-only imports happen in the UI section.
# === END SECTION: Core types and registry ===


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A best-effort pointer to the relevant source location."""

    line: str
    caret: str
    lineno: Optional[int]


@dataclass(frozen=True, slots=True)
class DiagnosisCard:
    """A single diagnosis candidate to show to the user."""

    confidence: float
    title: str
    explanation: str
    hint: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class ExceptionContext:
    """Context passed to diagnosers.

    Notes
    -----
    ``user_ns`` is best-effort: it is taken from the active IPython shell if one
    exists; otherwise it is an empty mapping.
    """

    etype: type[BaseException]
    evalue: BaseException
    tb: types.TracebackType
    code_line: str
    user_ns: Mapping[str, object]


class GuideError(Exception):
    """Raise a "teachable" error with a guaranteed diagnosis card.

    Parameters
    ----------
    message:
        Primary explanation shown to the user.
    hint:
        Actionable next step shown at the bottom of the card.

    Examples
    --------
    >>> raise GuideError("Don't do that!", hint="Do this instead.")  # doctest: +SKIP
    """

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint


class Diagnosis:
    """Base class for diagnosis heuristics.

    User doc
    --------
    Subclass this to add a new heuristic. Instances are registered via
    ``@register_diagnosis``. A diagnoser must:

    - implement :meth:`_check_condition` to return a confidence in ``[0, 1]``
    - implement :meth:`_generate_info` to build the card fields for display

    API reference
    -------------
    - ``diagnose(ctx)``: return a :class:`DiagnosisCard` fields (except location),
      or ``None`` if not applicable.

    Developer guide
    ---------------
    - Keep heuristics deterministic and fast.
    - Store match-specific state in ``_reset_state`` + instance attributes.
    - Prefer narrow, high-confidence checks over broad ones; a low-confidence
      diagnoser can still be useful as an alternative candidate.
    """

    def diagnose(self, ctx: ExceptionContext) -> Optional[tuple[float, str, str, str]]:
        """Return (confidence, title, explanation, hint) if this diagnosis matches.

        The returned tuple intentionally excludes source location; location is
        derived once in the analysis layer and attached uniformly.
        """
        try:
            self._reset_state()
            confidence = float(self._check_condition(ctx))
            if confidence <= 0.0:
                return None

            title, explanation, hint = self._generate_info(ctx)
            return (confidence, title, explanation, hint)
        except Exception:
            # Diagnostics must never crash the handler.
            return None

    def _reset_state(self) -> None:
        """Clear any per-run cached state."""
        return None

    def _check_condition(self, ctx: ExceptionContext) -> float:
        """Return confidence in [0, 1]."""
        return 0.0

    def _generate_info(self, ctx: ExceptionContext) -> tuple[str, str, str]:
        """Return (title, explanation, hint)."""
        return ("Unknown Issue", "No explanation available.", "")


_D = TypeVar("_D", bound=Diagnosis)
_DIAGNOSERS: list[Diagnosis] = []


def register_diagnosis(cls: type[_D]) -> type[_D]:
    """Register a :class:`Diagnosis` subclass.

    This decorator instantiates the class once at import time.
    """
    _DIAGNOSERS.append(cls())
    return cls


def _clear_registry_for_tests() -> None:
    """Clear the diagnosis registry.

    This is intended for unit tests only.
    """
    _DIAGNOSERS.clear()


# === SECTION: Exception analysis and ranking [id: analysis]===
#
# Convert an exception + traceback into a ranked list of DiagnosisCard objects.
# === END SECTION: Exception analysis and ranking ===


_IGNORED_FILENAME_HINTS: frozenset[str] = frozenset(
    {
        "gu_SmartFigure.py",
        "gu_numpify.py",
        "gu_NamedSympyFunction.py",
        "gu_SmartException.py",
        "gu_doc.py",
        "gu_context.py",
    }
)


def _make_carets(start: Optional[int], end: Optional[int]) -> str:
    if start is None:
        return ""
    end_ = end if end is not None else (start + 1)
    length = max(1, end_ - start)
    return (" " * start) + ("^" * length)


def _extract_user_frame(tb: types.TracebackType) -> Optional[traceback.FrameSummary]:
    """Return the most relevant traceback frame for the user's code."""
    records = traceback.extract_tb(tb)
    for frame in reversed(records):
        filename = frame.filename
        if "site-packages" in filename or "dist-packages" in filename:
            continue
        if any(hint in filename for hint in _IGNORED_FILENAME_HINTS):
            continue
        return frame
    return records[-1] if records else None


def _extract_location(etype: type[BaseException], evalue: BaseException, tb: types.TracebackType) -> SourceLocation:
    """Extract a code line, caret marker, and line number (best effort)."""
    code_line = ""
    caret = ""
    lineno: Optional[int] = None

    frame = _extract_user_frame(tb)

    try:
        # SyntaxError provides accurate offsets on the exception object.
        if isinstance(evalue, SyntaxError) and evalue.text:
            code_line = evalue.text.rstrip("\n")
            lineno = int(evalue.lineno) if evalue.lineno is not None else None

            # SyntaxError offsets are 1-based.
            start = (evalue.offset or 1) - 1
            end = (getattr(evalue, "end_offset", None) or (start + 1)) - 1
            caret = _make_carets(start, end)

        # Runtime exceptions: the FrameSummary may include 0-based columns (Py 3.11+).
        elif frame is not None:
            code_line = frame.line or ""
            lineno = int(frame.lineno) if frame.lineno is not None else None

            # FrameSummary may not carry a source line (e.g. exec/eval); try linecache.
            if not code_line and lineno is not None:
                try:
                    import linecache
                    code_line = linecache.getline(frame.filename, lineno).rstrip("\n")
                except Exception:
                    pass

            col = getattr(frame, "colno", None)
            end_col = getattr(frame, "end_colno", None)
            caret = _make_carets(col, end_col)
    except Exception:
        # Keep best-effort defaults.
        pass

    if code_line:
        stripped = code_line.lstrip()
        indent_len = len(code_line) - len(stripped)
        code_line = stripped
        if caret and len(caret) > indent_len:
            caret = caret[indent_len:]
        elif caret:
            caret = ""

    return SourceLocation(line=code_line, caret=caret, lineno=lineno)


def _get_user_namespace() -> Mapping[str, object]:
    """Return IPython user namespace if available; otherwise an empty mapping."""
    try:
        from IPython import get_ipython  # type: ignore[import-not-found]
    except Exception:
        return {}
    ip = get_ipython()
    if ip is None:
        return {}
    ns = getattr(ip, "user_ns", None)
    return ns if isinstance(ns, Mapping) else {}


def _build_context(
    etype: type[BaseException],
    evalue: BaseException,
    tb: types.TracebackType,
    location: SourceLocation,
) -> ExceptionContext:
    return ExceptionContext(
        etype=etype,
        evalue=evalue,
        tb=tb,
        code_line=location.line,
        user_ns=_get_user_namespace(),
    )


def _diagnose(ctx: ExceptionContext, location: SourceLocation) -> list[DiagnosisCard]:
    """Run diagnosers and return a ranked list of candidates (best effort)."""
    candidates: list[DiagnosisCard] = []

    # A) Explicit GuideError: guaranteed match.
    if isinstance(ctx.evalue, GuideError):
        candidates.append(
            DiagnosisCard(
                confidence=1.0,
                title="Guidance",
                explanation=str(ctx.evalue),
                hint=ctx.evalue.hint,
                location=location,
            )
        )
        return candidates

    # B) Registry diagnosers.
    for diagnoser in _DIAGNOSERS:
        match = diagnoser.diagnose(ctx)
        if match is None:
            continue
        confidence, title, explanation, hint = match
        candidates.append(
            DiagnosisCard(
                confidence=confidence,
                title=title,
                explanation=explanation,
                hint=hint,
                location=location,
            )
        )

    # C) Default fallback.
    candidates.append(
        DiagnosisCard(
            confidence=0.0,
            title=f"Exception: {ctx.etype.__name__}",
            explanation=f"An error occurred: {_html.escape(str(ctx.evalue))}",
            hint="Open Details below for the full traceback.",
            location=location,
        )
    )

    # Higher confidence first; stable within equal confidence.
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates


# === SECTION: Built-in diagnosers [id: diagnosers]===
#
# Built-in heuristics are ordered from general to specific. Each heuristic should
# return a confidence that reflects how often it is "actually right".
# === END SECTION: Built-in diagnosers ===


@register_diagnosis
class InputIncomplete(Diagnosis):
    """Detect code that ends prematurely (missing closing paren/bracket/quote)."""

    def _check_condition(self, ctx: ExceptionContext) -> float:
        if ctx.etype.__name__ == "_IncompleteInputError":
            return 0.99
        if isinstance(ctx.evalue, SyntaxError) and "unexpected EOF" in str(ctx.evalue):
            return 0.95
        return 0.0

    def _generate_info(self, ctx: ExceptionContext) -> tuple[str, str, str]:
        return (
            "Missing Closing Symbol",
            "Python reached the end of your code but was expecting more. "
            "This almost always means you have an unclosed parenthesis `(`, "
            "bracket `[`, curly brace `{`, or string quote.",
            "Check the end of the highlighted block for a missing `)` or `]`.",
        )


@register_diagnosis
class InputIssue(Diagnosis):
    """Baseline: error occurred directly in the user's cell."""

    def _check_condition(self, ctx: ExceptionContext) -> float:
        frame = _extract_user_frame(ctx.tb)
        if frame is None:
            return 0.0

        filename = frame.filename
        # If we couldn't find any non-library frame, treat it as not an input issue.
        if "site-packages" in filename or "dist-packages" in filename:
            return 0.0
        if any(hint in filename for hint in _IGNORED_FILENAME_HINTS):
            return 0.0

        return 0.1

    def _generate_info(self, ctx: ExceptionContext) -> tuple[str, str, str]:
        return (
            "Input Issue",
            "The execution stopped directly in your cell code. This is usually due to a typo or syntax mismatch.",
            "Review the highlighted line.",
        )


@register_diagnosis
class InputNameError(InputIssue):
    """More specific: the input issue is a NameError."""

    def _check_condition(self, ctx: ExceptionContext) -> float:
        parent_conf = super()._check_condition(ctx)
        if parent_conf <= 0.0:
            return 0.0
        if isinstance(ctx.evalue, NameError):
            return 0.25
        return 0.0

    def _generate_info(self, ctx: ExceptionContext) -> tuple[str, str, str]:
        return (
            "Undefined Variable",
            f"Python cannot find the variable definition. **{_html.escape(str(ctx.evalue))}**.",
            "Did you define it in a previous cell?",
        )


@register_diagnosis
class InputCaseTypo(InputNameError):
    """Highly specific: NameError caused by capitalization mismatch (e.g. X vs x)."""

    def _reset_state(self) -> None:
        self._missing_name: Optional[str] = None
        self._suggestion: Optional[str] = None

    def _check_condition(self, ctx: ExceptionContext) -> float:
        if super()._check_condition(ctx) <= 0.0:
            return 0.0

        missing = _extract_missing_name(ctx.evalue)
        if missing is None:
            return 0.0

        missing_lower = missing.lower()
        candidates = [k for k in ctx.user_ns.keys() if isinstance(k, str)]
        for cand in candidates:
            if cand.lower() == missing_lower and cand != missing:
                self._missing_name = missing
                self._suggestion = cand
                return 0.95
        return 0.0

    def _generate_info(self, ctx: ExceptionContext) -> tuple[str, str, str]:
        missing = self._missing_name or "<?>"
        suggestion = self._suggestion or "<?>"
        return (
            "Capitalization Error",
            f"You typed `{missing}`, but defined `{suggestion}`.",
            f"Python is case-sensitive. Change it to `{suggestion}`.",
        )


@register_diagnosis
class InputFuzzyTypo(InputNameError):
    """Highly specific: NameError likely caused by a typo; suggest close matches."""

    def _reset_state(self) -> None:
        self._missing_name: Optional[str] = None
        self._suggestion: Optional[str] = None

    def _check_condition(self, ctx: ExceptionContext) -> float:
        if super()._check_condition(ctx) <= 0.0:
            return 0.0

        missing = _extract_missing_name(ctx.evalue)
        if missing is None:
            return 0.0

        names = [k for k in ctx.user_ns.keys() if isinstance(k, str)]
        # Simple edit-distance based suggestion.
        try:
            import difflib
        except Exception:
            return 0.0

        matches = difflib.get_close_matches(missing, names, n=1, cutoff=0.75)
        if matches:
            self._missing_name = missing
            self._suggestion = matches[0]
            # Lower than capitalization mismatch so InputCaseTypo wins if both apply.
            return 0.60

        return 0.0

    def _generate_info(self, ctx: ExceptionContext) -> tuple[str, str, str]:
        missing = self._missing_name or "<?>"
        suggestion = self._suggestion or "<?>"
        return (
            "Possible Typo",
            f"Variable `{missing}` is not defined.",
            f"Did you mean `{suggestion}`?",
        )


def _extract_missing_name(err: BaseException) -> Optional[str]:
    """Extract the missing name from a NameError (best effort)."""
    if hasattr(err, "name"):
        name = getattr(err, "name")
        if isinstance(name, str) and name:
            return name
    match = re.search(r"name '([A-Za-z_][A-Za-z0-9_]*)' is not defined", str(err))
    return match.group(1) if match else None


@register_diagnosis
class MathSyntaxCaret(Diagnosis):
    """Detect usage of ``^`` for exponentiation."""

    def _check_condition(self, ctx: ExceptionContext) -> float:
        if "^" in ctx.code_line and "unsupported operand" in str(ctx.evalue):
            return 0.9
        return 0.0

    def _generate_info(self, ctx: ExceptionContext) -> tuple[str, str, str]:
        return (
            "Syntax: Powers",
            "It looks like you used `^` for power.",
            "Use `**` instead (e.g. `x**2`).",
        )


@register_diagnosis
class MathSyntaxImplicitMult(Diagnosis):
    """Detect implicit multiplication like ``2x`` instead of ``2*x``."""

    def _check_condition(self, ctx: ExceptionContext) -> float:
        if isinstance(ctx.evalue, SyntaxError) and re.search(r"\d[a-zA-Z]", ctx.code_line):
            return 0.85
        return 0.0

    def _generate_info(self, ctx: ExceptionContext) -> tuple[str, str, str]:
        return (
            "Syntax: Multiplication",
            "It looks like you wrote something like `2x`.",
            "Python requires the star for multiplication: `2*x`.",
        )


@register_diagnosis
class MissingImport(Diagnosis):
    """Detect missing common math functions (likely needing a prefix/import)."""

    def _reset_state(self) -> None:
        self._missing_name: Optional[str] = None

    def _check_condition(self, ctx: ExceptionContext) -> float:
        if not isinstance(ctx.evalue, NameError):
            return 0.0

        name = _extract_missing_name(ctx.evalue)
        if name is None:
            return 0.0

        if name in {"sin", "cos", "tan", "exp", "log", "sqrt", "pi", "inf"}:
            self._missing_name = name
            return 0.95
        return 0.0

    def _generate_info(self, ctx: ExceptionContext) -> tuple[str, str, str]:
        name = self._missing_name or "<?>"
        return (
            "Missing Prefix",
            f"Python doesn't know `{name}` directly.",
            f"Try `sp.{name}` or `np.{name}`.",
        )


# === SECTION: UI renderer (ipywidgets) [id: ui]===
#
# This section is the only place that imports ipywidgets / IPython.display.
# === END SECTION: UI renderer (ipywidgets) ===


_LOG = logging.getLogger(__name__)


def _require_ipywidgets() -> tuple[object, object]:
    try:
        import ipywidgets as widgets  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(
            "SmartException UI requires 'ipywidgets'. Install it (e.g. via pip/conda) "
            "to use the interactive exception cards."
        ) from exc

    try:
        from IPython.display import display  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(
            "SmartException requires IPython to render exception cards."
        ) from exc

    return widgets, display


def _markdown_to_html(text: str) -> str:
    """Convert markdown to HTML if the optional dependency is available."""
    try:
        import markdown  # type: ignore[import-not-found]
    except Exception:
        return text
    try:
        return markdown.markdown(text)
    except Exception:
        return text


def _render_html_card(widgets: object, display: Callable[[object], None], card: DiagnosisCard) -> None:
    """Render a single card into the current output context."""
    conf = card.confidence

    if conf >= 1.0:
        border = "#0277BD"
        bg = "#E1F5FE"
        icon = "🎓"
    elif conf > 0.4:
        border = "#FF8F00"
        bg = "#FFF8E1"
        icon = "💡"
    elif conf > 0.05:
        border = "#616161"
        bg = "#F5F5F5"
        icon = "⚠️"
    else:
        border = "#D32F2F"
        bg = "#FFEBEE"
        icon = "❌"

    caret_html = ""
    if card.location.caret:
        caret_html = f'<div style="color:#D32F2F; font-weight:700;">{_html.escape(card.location.caret)}</div>'

    expl_html = _markdown_to_html(card.explanation)
    hint_html = _markdown_to_html(card.hint)

    lineno = card.location.lineno
    lineno_label = str(lineno) if lineno is not None else "?"

    html_content = f"""
<div class="smart-exception-card" style="
    background-color:{bg};
    color:#212121;
    border-left:5px solid {border};
    padding:12px 16px;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
    border-radius:8px;
    box-shadow:0 2px 4px rgba(0,0,0,0.10);
    margin-bottom:5px;
">
  <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:8px;">
    <h4 style="margin:0; color:#212121; font-size:1.1em; font-weight:650;">
      <span role="img" aria-hidden="true">{icon}</span> {_html.escape(card.title)}
    </h4>
    <span style="font-size:0.85em; color:#555;" title="Confidence score">Match: {int(conf*100)}%</span>
  </div>

  <div style="margin:0 0 10px 0; font-size:1em; line-height:1.5; color:#212121;">
    {expl_html}
  </div>

  <div style="
      background-color:#FFFFFF;
      color:#333333;
      padding:8px 10px;
      border:1px solid #ddd;
      font-family:'Menlo','Consolas','Monaco',monospace;
      font-size:0.9em;
      margin-bottom:8px;
      border-radius:6px;
      overflow-x:auto;
  ">
    <div style="margin-bottom:2px; color:#666; user-select:none; font-size:0.8em;">Line {lineno_label}:</div>
    <div style="white-space:pre; line-height:1.2;">{_html.escape(card.location.line)}</div>
    <div style="white-space:pre; line-height:1.2;">{caret_html}</div>
  </div>

  <div style="color:#004D40; font-weight:650; font-size:0.95em; display:flex; gap:6px; align-items:baseline;">
    <span aria-hidden="true">➥</span>
    <div>{hint_html}</div>
  </div>
</div>

<style>
  .smart-exception-card p {{ margin: 0 0 6px 0; }}
  .smart-exception-card code {{
      background-color: rgba(255,255,255,0.6);
      padding: 2px 4px;
      border-radius: 4px;
      font-family: monospace;
  }}
</style>
"""
    display(widgets.HTML(value=html_content))


def smart_exception_handler(
    shell: object,
    etype: type[BaseException],
    evalue: BaseException,
    tb: types.TracebackType,
    tb_offset: Optional[int] = None,
) -> None:
    """IPython custom exception handler that renders ranked diagnosis cards.

    Notes
    -----
    This handler is intentionally defensive: if anything goes wrong while
    rendering, it falls back to printing the raw traceback.
    """
    try:
        widgets, display = _require_ipywidgets()

        location = _extract_location(etype, evalue, tb)
        ctx = _build_context(etype, evalue, tb, location)
        candidates = _diagnose(ctx, location)

        out_card = widgets.Output()
        nav_container = widgets.HBox(
            layout=widgets.Layout(margin="5px 0 10px 0", flex_flow="row wrap", align_items="baseline")
        )

        state: MutableMapping[str, int] = {"current_idx": 0}

        def render_view() -> None:
            idx = int(state["current_idx"])
            card = candidates[idx]

            with out_card:
                out_card.clear_output()
                _render_html_card(widgets, display, card)

            buttons: list[object] = []
            if len(candidates) > 1:
                label = widgets.HTML(
                    value='<span style="color:#666; margin-right:8px; font-size:0.9em;">Or maybe:</span>'
                )
                buttons.append(label)

                for i, cand in enumerate(candidates):
                    is_active = (i == idx)
                    bg_color = "#E1F5FE" if is_active else "transparent"
                    border_val = "1px solid #B3E5FC" if is_active else "1px solid transparent"

                    btn = widgets.Button(
                        description=cand.title,
                        layout=widgets.Layout(width="auto", height="28px", border=border_val, margin="0 2px"),
                        style={"button_color": bg_color},
                        tooltip=f"Switch to diagnosis: {cand.title}",
                    )

                    def _on_click(_btn: object, *, target_i: int = i) -> None:
                        state["current_idx"] = target_i
                        render_view()

                    btn.on_click(_on_click)  # type: ignore[attr-defined]
                    buttons.append(btn)

            nav_container.children = tuple(buttons)

        render_view()

        out_debug = widgets.Output(
            layout=widgets.Layout(
                display="none",
                border="1px solid #ddd",
                padding="10px",
                margin="5px 0 0 0",
                background_color="#f9f9f9",
            )
        )
        with out_debug:
            traceback.print_exception(etype, evalue, tb)

        btn_debug = widgets.Button(
            description="▶ Details",
            layout=widgets.Layout(width="auto", border="none", margin="0", padding="0", height="auto"),
            style={"button_color": "transparent"},
            tooltip="Show technical details (collapsed)",
        )

        def toggle_debug(_btn: object) -> None:
            if out_debug.layout.display == "none":
                out_debug.layout.display = "block"
                btn_debug.description = "▼ Details"
            else:
                out_debug.layout.display = "none"
                btn_debug.description = "▶ Details"

        btn_debug.on_click(toggle_debug)  # type: ignore[attr-defined]

        display(out_card)
        display(nav_container)
        display(widgets.VBox([btn_debug, out_debug], layout=widgets.Layout(align_items="flex-start", margin="0")))
    except Exception:
        _LOG.exception("SmartException handler failed; falling back to raw traceback.")
        traceback.print_exception(etype, evalue, tb)


# === SECTION: Activation helpers (IPython integration) [id: activation]===
#
# Convenience installation/uninstallation for interactive sessions.
# === END SECTION: Activation helpers (IPython integration) ===


def activate(*, verbose: bool = False) -> None:
    """Install the SmartException handler into the active IPython session."""
    try:
        from IPython import get_ipython  # type: ignore[import-not-found]
    except Exception:
        if verbose:
            _LOG.info("IPython is not available; SmartException not activated.")
        return

    ip = get_ipython()
    if ip is None:
        if verbose:
            _LOG.info("No active IPython shell; SmartException not activated.")
        return

    ip.set_custom_exc((Exception,), smart_exception_handler)
    if verbose:
        _LOG.info("SmartException handler activated.")


def deactivate(*, verbose: bool = False) -> None:
    """Restore default exception handling in the active IPython session."""
    try:
        from IPython import get_ipython  # type: ignore[import-not-found]
    except Exception:
        if verbose:
            _LOG.info("IPython is not available; SmartException not deactivated.")
        return

    ip = get_ipython()
    if ip is None:
        if verbose:
            _LOG.info("No active IPython shell; SmartException not deactivated.")
        return

    ip.set_custom_exc((Exception,), None)
    if verbose:
        _LOG.info("SmartException handler deactivated.")


def _setup(ctx: Mapping[str, object]) -> None:
    """Plugin hook used by the surrounding framework."""
    verbose = bool(ctx.get("verbose", False))
    activate(verbose=verbose)
