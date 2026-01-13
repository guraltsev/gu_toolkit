"""
Purpose
-------
Provide a small, student-facing API for plotting SymPy expressions in Jupyter notebooks, with
a Plotly-first interactive widget that can run in JupyterLite/Pyodide when the required
frontend extensions are bundled.

Non-goals
---------
- Full-featured plotting (3D, scatter/markers, complex layout management).
- Eager imports of heavy/optional UI dependencies at module import time.

Design overview
---------------
This module follows a simple Model/Controller/View split:

- Model: :class:`Plot` holds a SymPy expression, sampling configuration, and style.
- Controller: :class:`SmartFigure` manages the viewport, plot registry, and recompute orchestration.
- View: :class:`PlotBackend` is a thin rendering seam implemented by Plotly and (optionally) Matplotlib.

Key invariants / assumptions
----------------------------
- A Plot is evaluated on a 1D grid (x-values) and returns y-values of matching shape.
- Parameter symbols are treated as scalars; constant (or parameter-only) expressions are broadcast to the x-grid.
- Optional UI dependencies (ipywidgets/plotly) are imported only when constructing widgets/backends.

Public entrypoints
------------------
- :class:`SmartFigure` — main entrypoint; manages plots and (optionally) builds an interactive widget.
- :class:`Plot` — one plotted expression; exposes sampling and style.
- :class:`Style` — visual style configuration.
- :data:`VIEWPORT` — sentinel meaning “inherit from figure viewport”.

Testing
-------
This file is intended to be covered by a small deterministic test suite (e.g. ``tests/test_smartfigure_smoke.py``)
that avoids importing optional UI dependencies.
Supported Python versions: 3.9+.

----

SmartFigure: Smart symbolic plotting (Plotly-first, JupyterLite-friendly)
============================================================================

`SmartFigure` provides a small, student-facing API for plotting SymPy
expressions in Jupyter notebooks. The core design separates:

- **Model**: :class:`Plot` (symbolic expression, sampling configuration, style)
- **Controller**: :class:`SmartFigure` (viewport, plot registry, recompute orchestration)
- **View**: :class:`PlotBackend` (a thin rendering seam)

Phase 1 (implemented here) replaces the Matplotlib-first view layer with a
**Plotly `go.FigureWidget` backend**, embedded in an **ipywidgets layout**.
This makes the module compatible with **JupyterLite/Pyodide** by ensuring that
Matplotlib is not imported at module import time.

Supported environments
----------------------
- ✅ JupyterLab / classic Jupyter Notebook (Python kernel)
- ✅ JupyterLite / Pyodide (provided Plotly + ipywidgets support is bundled)
- ❌ Google Colab (hard error on widget construction)

Only 2D line plots
------------------
This module intentionally supports **only 2D line plots** (no markers, no 3D).

Student Quickstart (one page)
-----------------------------
```python
import sympy as sp
from SmartFigure import SmartFigure

x = sp.Symbol("x")

fig = SmartFigure(show_now=False)

p = fig.plot(sp.sin(x), name="wave")
fig.widget  # display the interactive widget

# Change the viewport (forces resampling on the next draw)
fig.x_range = (-2, 2)

# Change styling reactively
p.style.color = "red"
p.style.width = 3
p.style.linestyle = "--"
p.style.opacity = 0.7
p.style.visible = True
```

Instructor distribution notes (JupyterLite)
-------------------------------------------
To distribute notebooks via JupyterLite (e.g. GitHub Pages), your build must
bundle:

- `plotly` (with `FigureWidget` support)
- `ipywidgets` + the JupyterLite widget manager/extensions used by your setup

If either dependency is missing at runtime, accessing :attr:`SmartFigure.widget`
raises a :class:`~gu_SmartException.GuideError` with actionable guidance.

Developer guide
---------------
Backend contract
^^^^^^^^^^^^^^^^
A backend implements :class:`PlotBackend`:

- `add_plot(name, x, y, style) -> handle`
- `update_plot(handle, x, y)`
- `apply_style(handle, style)`
- `remove_plot(handle)`
- `set_viewport(x_range, y_range)`
- `request_redraw()`

The controller always treats the figure's viewport (``SmartFigure._x_range`` /
``SmartFigure._y_range``) as the **source of truth**.

Style mapping (Plotly)
^^^^^^^^^^^^^^^^^^^^^^
:class:`Style` fields map to Plotly trace properties as follows:

- `visible` → `trace.visible` (bool)
- `color` → `trace.line.color`
- `width` → `trace.line.width`
- `opacity` → `trace.opacity`
- `linestyle` → `trace.line.dash` via:
  `'-'→'solid', '--'→'dash', ':'→'dot', '-.'→'dashdot'`

Widget construction
^^^^^^^^^^^^^^^^^^^
:attr:`SmartFigure.widget` lazily:

1) Checks environment policy (rejects Colab)
2) Imports `ipywidgets` and `plotly` lazily (to keep module import lightweight)
3) Constructs `PlotlyBackend` and applies the current viewport
4) Adds traces for all registered plots (by name)
5) Computes + pushes sampled `(x, y)` data to the backend

Phase 2 preview (NOT implemented)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A future phase may attach Plotly relayout (pan/zoom) events and resample on
viewport changes. This Phase 1 code keeps viewport state in :class:`SmartFigure`
so Phase 2 can be implemented without rewriting the backend boundary.
"""

from __future__ import annotations

__all__ = [
    # Fundamentals
    "VIEWPORT",

    # UI helpers (optional dependencies)
    "SmartSlider",

    # Configuration
    "Style",

    # Backends
    "PlotBackend",
    "MplBackend",
    "PlotlyTraceHandle",
    "PlotlyBackend",

    # Core API
    "Plot",
    "SmartFigure",
]

import sys
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    TypeVar,
    Sequence,
    Tuple,
    Union,
    SupportsFloat,
    runtime_checkable,
    cast,
)

import numpy
import sympy

from gu_toolkit.plugins.numpify import numpify
from gu_toolkit.plugins.SmartException import GuideError
from gu_toolkit.plugins.SmartParameters import (
    CallbackToken,
    SmartParameter,
    SmartParameterRegistry,
)

# === SECTION: Plotly label sanitation [id: plotly-labels] ===
#
# Defensive escaping for Plotly trace names/legends, with MathJax `$...$` support.

def _plotly_sanitize_trace_name(label: object) -> str:
    """Return a Plotly trace name that is:
    - safe against Plotly's pseudo-HTML parsing (angle brackets, ampersands)
    - safe for LaTeX/MathJax when the user uses `$...$` math segments
    - tolerant of unicode
    - explicit (raise) on unmatched `$` to avoid client-side silent failures

    Contract:
    - Plain text is treated as plain text (no HTML tags are interpreted).
    - Inline math is supported via `$...$` (MathJax/LaTeX).
    - A literal dollar sign can be written as `\\$`.
    """
    text = str(label)

    # Treat `\$` as a literal dollar (not a math delimiter).
    LIT = "\u0000GU_DOLLAR\u0000"
    text = text.replace(r"\$", LIT)

    parts = text.split("$")
    dollar_count = len(parts) - 1
    if dollar_count % 2 == 1:
        # Unmatched `$` very commonly breaks Plotly rendering client-side with no Python error.
        raise GuideError(
            f"Unmatched `$` in plot name: {label!r}.",
            hint="Use `$...$` for LaTeX, or write a literal dollar as `\\$`. "
                 "Example: name='$\\sin(x)$' or name='Cost is \\$5'.",
        )

    out_parts: List[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            # Outside math: escape pseudo-HTML so `<...>` shows literally and doesn't get parsed.
            part = part.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Literal dollars outside math should not start a new math region.
            part = part.replace(LIT, "&#36;")
        else:
            # Inside math: keep TeX; a literal dollar should be `\$` for MathJax.
            part = part.replace(LIT, r"\$")
        out_parts.append(part)

    return "$".join(out_parts)

# === END SECTION: Plotly label sanitation ===

# === SECTION: Fundamentals & tokens [id: fundamentals] ===
#
# VIEWPORT is a sentinel meaning “inherit viewport/sampling settings from the parent figure”.

class _ViewportToken:
    """Sentinel token representing 'inherit settings from the parent figure'."""
    def __repr__(self) -> str:
        return "VIEWPORT"

VIEWPORT = _ViewportToken()

# === END SECTION: Fundamentals & tokens ===



# === SECTION: Helpers and optional dependency boundaries [id: helpers] ===


# === SECTION: UI slider widget [id: ui-smartslider] ===
#
# This widget is only needed when building interactive Jupyter layouts. To keep this module importable
# in environments without ipywidgets (CI, headless scripts, some kernels), we build the concrete
# ipywidgets subclass lazily on first use.
# === END SECTION: UI slider widget ===

_SMART_SLIDER_CLASS: Optional[type] = None

def _reset_smart_slider_cache_for_tests() -> None:
    """Reset the cached ipywidgets slider class (test helper)."""
    global _SMART_SLIDER_CLASS
    _SMART_SLIDER_CLASS = None

def _get_smart_slider_class() -> type:
    """Return the cached concrete ipywidgets implementation of :class:`SmartSlider`."""
    global _SMART_SLIDER_CLASS
    if _SMART_SLIDER_CLASS is not None:
        return _SMART_SLIDER_CLASS

    widgets = _lazy_import_ipywidgets()

    class _SmartSlider(widgets.VBox):
        """Concrete ipywidgets slider with a collapsible settings panel."""

        def __init__(
            self,
            *,
            value: float = 0.0,
            min_val: float = -1.0,
            max_val: float = 1.0,
            step: float = 0.01,
            description: str = "",
        ) -> None:
            self.slider = widgets.FloatSlider(
                value=value,
                min=min_val,
                max=max_val,
                step=step,
                description=description,
                continuous_update=True,
                readout=True,
                layout=widgets.Layout(width="100%", min_width="300px", flex="1 1 auto"),
            )

            # A small cog button toggles advanced settings (min/max/step).
            self.settings_btn = widgets.Button(
                icon="cog",
                tooltip="Configure slider limits",
                layout=widgets.Layout(width="35px", height="auto", flex="0 0 auto"),
            )
            self.settings_btn.on_click(self._toggle_settings)

            self.main_row = widgets.HBox(
                [self.slider, self.settings_btn],
                layout=widgets.Layout(width="100%", align_items="center"),
            )

            _input_layout = widgets.Layout(width="150px", min_width="130px")
            _input_style = {"description_width": "45px"}

            self.min_input = widgets.FloatText(
                value=float(min_val),
                description="Min:",
                layout=_input_layout,
                style=_input_style,
            )
            self.max_input = widgets.FloatText(
                value=float(max_val),
                description="Max:",
                layout=_input_layout,
                style=_input_style,
            )
            self.step_input = widgets.FloatText(
                value=float(step),
                description="Step:",
                layout=_input_layout,
                style=_input_style,
            )

            self.min_input.observe(self._update_min, names="value")
            self.max_input.observe(self._update_max, names="value")
            self.step_input.observe(self._update_step, names="value")

            # Use wrapping to avoid horizontal scrollbars in narrow containers.
            self.settings_panel = widgets.HBox(
                [self.min_input, self.max_input, self.step_input],
                layout=widgets.Layout(
                    display="none",
                    width="100%",
                    flex_flow="row wrap",
                    padding="5px 0 0 0",
                    overflow="hidden",
                ),
            )

            super().__init__(
                [self.main_row, self.settings_panel],
                layout=widgets.Layout(width="100%", min_width="340px"),
            )

        def _toggle_settings(self, _b: object) -> None:
            """Show or hide the settings panel."""
            self.settings_panel.layout.display = (
                "flex" if self.settings_panel.layout.display == "none" else "none"
            )


        def _update_min(self, change: Mapping[str, object]) -> None:
            try:
                self.slider.min = float(change.get("new", self.slider.min))
            except Exception:
                # Keep previous value on invalid input.
                self.min_input.value = float(self.slider.min)

        def _update_max(self, change: Mapping[str, object]) -> None:
            try:
                self.slider.max = float(change.get("new", self.slider.max))
            except Exception:
                self.max_input.value = float(self.slider.max)

        def _update_step(self, change: Mapping[str, object]) -> None:
            try:
                self.slider.step = float(change.get("new", self.slider.step))
            except Exception:
                self.step_input.value = float(self.slider.step)

    _SMART_SLIDER_CLASS = _SmartSlider
    return _SmartSlider


class SmartSlider:
    """Proxy/factory returning a concrete ipywidgets slider implementation.

    The returned object is an ipywidgets Widget (a VBox). This indirection keeps the module importable
    without ipywidgets.
    """

    def __new__(
        cls,
        *,
        value: float = 0.0,
        min_val: float = -1.0,
        max_val: float = 1.0,
        step: float = 0.01,
        description: str = "",
    ) -> object:
        slider_cls = _get_smart_slider_class()
        return slider_cls(value=value, min_val=min_val, max_val=max_val, step=step, description=description)  # type: ignore[misc]

# --- Subsection: Environment & dependency helpers (lazy imports) ---

def _in_colab() -> bool:
    """Return True if running in Google Colab."""
    if "google.colab" in sys.modules:
        return True
    try:
        import google.colab  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def _require_not_colab() -> None:
    """Raise GuideError if the current runtime is Google Colab."""
    if _in_colab():
        raise GuideError(
            "Google Colab is not supported by SmartFigure's interactive widget.\n\n"
            "Why: Colab's widget/Plotly integration is not compatible with the portable "
            "JupyterLite-first design of this project.\n\n"
            "Use one of these instead:\n"
            "  • JupyterLab / Jupyter Notebook (local or hosted)\n"
            "  • JupyterLite / Pyodide (course website build)\n"
        )


def _lazy_import_ipywidgets():
    """Import ipywidgets lazily and return the module."""
    try:
        import ipywidgets as widgets  # type: ignore
        return widgets
    except Exception as e:
        raise GuideError(
            "ipywidgets is required to display SmartFigure widgets, but it could not be imported.\n\n"
            "If you are in a standard Python environment, install it with:\n"
            "  pip install ipywidgets\n\n"
            "If you are in JupyterLite, ensure your build bundles ipywidgets and the widget manager."
        ) from e


def _lazy_import_plotly_go():
    """Import plotly.graph_objects lazily and return it."""
    try:
        import plotly.graph_objects as go  # type: ignore
        _ = go.FigureWidget
        return go
    except Exception as e:
        raise GuideError(
            "Plotly (with FigureWidget support) is required to display SmartFigure widgets, "
            "but it could not be imported.\n\n"
            "In a standard Python environment, install it with:\n"
            "  pip install plotly\n\n"
            "In JupyterLite, ensure your build bundles plotly and supports FigureWidget."
        ) from e





# === END SECTION: Helpers and optional dependency boundaries ===

# === SECTION: Configuration (Style and reactive style) [id: config-style] ===
@dataclass
class Style:
    """Controls the visual appearance of a plot."""
    visible: bool = True
    color: Optional[str] = None
    width: Optional[float] = None
    opacity: Optional[float] = None
    linestyle: Optional[str] = None

    _ALLOWED_LINESTYLES = {"-", "--", ":", "-."}
    _ALIASES = {
        "lw": "width", "linewidth": "width",
        "alpha": "opacity",
        "ls": "linestyle",
        "vis": "visible"
    }

    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            prop = self._ALIASES.get(k, k)
            if hasattr(self, prop) and prop in self.__annotations__:
                setattr(self, prop, v)
            else:
                allowed = sorted(list(self.__annotations__.keys()) + list(self._ALIASES.keys()))
                raise ValueError(
                    f"Unknown style argument {k!r}. Allowed arguments are: {', '.join(allowed)}."
                )

    def copy(self) -> "Style":
        new = Style()
        new.visible = self.visible
        new.color = self.color
        new.width = self.width
        new.opacity = self.opacity
        new.linestyle = self.linestyle
        return new

    def __repr__(self) -> str:
        set_params = []
        if not self.visible:
            set_params.append("visible=False")
        if self.color:
            set_params.append(f"color='{self.color}'")
        if self.width:
            set_params.append(f"width={self.width}")
        if self.opacity:
            set_params.append(f"opacity={self.opacity}")
        if self.linestyle:
            set_params.append(f"linestyle='{self.linestyle}'")
        content = ", ".join(set_params) if set_params else "default"
        return f"<Style: {content}>"

    def __setattr__(self, name: str, value: object) -> None:
        if value is None:
            if name == "visible":
                raise TypeError("`style.visible` must be a boolean, got `None`.")
            super().__setattr__(name, None)
            return

        if name == "visible":
            if not isinstance(value, bool):
                raise TypeError(f"`style.visible` must be a boolean, got `{value!r}`")
            super().__setattr__(name, value)
            return

        if name == "width":
            try:
                val = float(value)
                if val <= 0:
                    raise ValueError
                super().__setattr__(name, val)
            except (ValueError, TypeError):
                raise ValueError(f"`style.width` must be a float > 0, got `{value!r}`")
            return

        if name == "opacity":
            try:
                val = float(value)
                if not (0.0 <= val <= 1.0):
                    raise ValueError
                super().__setattr__(name, val)
            except (ValueError, TypeError):
                raise ValueError(f"`style.opacity` must be a float between 0 and 1, got `{value!r}`")
            return

        if name == "linestyle":
            if value not in self._ALLOWED_LINESTYLES:
                raise ValueError(
                    f"`style.linestyle` must be one of {self._ALLOWED_LINESTYLES}, got `{value!r}`"
                )
            super().__setattr__(name, str(value))
            return

        super().__setattr__(name, value)


class ReactiveStyle:
    """A live link to the style of a plot that triggers backend updates on mutation."""
    def __init__(self, style: Style, callback: Callable[[], None]) -> None:
        self._style = style
        self._callback = callback

    def __getattr__(self, name: str) -> object:
        return getattr(self._style, name)

    def __setattr__(self, name: str, value: object) -> None:
        if name in ("_style", "_callback"):
            super().__setattr__(name, value)
            return
        setattr(self._style, name, value)
        self._callback()

    def __repr__(self) -> str:
        return repr(self._style)


# === END SECTION: Configuration (Style and reactive style) ===

# === SECTION: Renderer backends [id: backends] ===

HandleT = TypeVar("HandleT")


@runtime_checkable
class PlotBackend(Protocol[HandleT]):
    """Contract for rendering engines."""

    def add_plot(self, name: str, x: numpy.ndarray, y: numpy.ndarray, style: Style) -> HandleT: ...
    def update_plot(self, handle: HandleT, x: numpy.ndarray, y: numpy.ndarray) -> None: ...
    def apply_style(self, handle: HandleT, style: Style) -> None: ...
    def remove_plot(self, handle: HandleT) -> None: ...
    def set_viewport(self, x_range: Tuple[float, float], y_range: Optional[Tuple[float, float]]) -> None: ...
    def request_redraw(self) -> None: ...

class MplBackend:
    """Matplotlib backend (optional, lazy-imported)."""

    def __init__(self, figsize: Tuple[int, int] = (7, 4), dpi: int = 100) -> None:
        try:
            import matplotlib.pyplot as plt  # type: ignore
        except Exception as e:
            raise GuideError(
                "Matplotlib is not available in this environment. "
                "Use the Plotly-backed widget via `SmartFigure.widget` or "
                "install matplotlib in a standard Python environment."
            ) from e
        self._plt = plt
        self.fig, self.ax = plt.subplots(figsize=figsize, dpi=dpi)
        self.ax.grid(True, alpha=0.25)

    def _translate_style(self, style: Style) -> Dict[str, Any]:
        kw = {"visible": style.visible}
        if style.color is not None:
            kw["color"] = style.color
        if style.width is not None:
            kw["linewidth"] = style.width
        if style.opacity is not None:
            kw["alpha"] = style.opacity
        if style.linestyle is not None:
            kw["linestyle"] = style.linestyle
        return kw

    def add_plot(self, name: str, x: numpy.ndarray, y: numpy.ndarray, style: Style) -> object:
        kw = self._translate_style(style)
        (line,) = self.ax.plot(x, y, label=name, **kw)
        return line

    def update_plot(self, handle: object, x: numpy.ndarray, y: numpy.ndarray) -> None:
        handle.set_data(x, y)

    def apply_style(self, handle: object, style: Style) -> None:
        kw = self._translate_style(style)
        if "color" in kw:
            handle.set_color(kw["color"])
        if "linewidth" in kw:
            handle.set_linewidth(kw["linewidth"])
        if "alpha" in kw:
            handle.set_alpha(kw["alpha"])
        if "linestyle" in kw:
            handle.set_linestyle(kw["linestyle"])
        handle.set_visible(kw["visible"])

    def remove_plot(self, handle: object) -> None:
        handle.remove()

    def set_viewport(self, x_range: Tuple[float, float], y_range: Optional[Tuple[float, float]]) -> None:
        self.ax.set_xlim(*x_range)
        if y_range is not None:
            self.ax.set_ylim(*y_range)

    def request_redraw(self) -> None:
        self.fig.canvas.draw_idle()

@dataclass(frozen=True)
class PlotlyTraceHandle:
    """Stable identifier for a Plotly trace in a FigureWidget (tracked by uid)."""
    uid: str

class PlotlyBackend:
    """Plotly FigureWidget backend (Phase 1 default; 2D lines only)."""

    _LINESTYLE_MAP = {"-": "solid", "--": "dash", ":": "dot", "-.": "dashdot"}

    def __init__(self):
        go = _lazy_import_plotly_go()
        self._go = go
        self.fig = go.FigureWidget()
        # Ensure MathJax is available so `$...$` labels don't break rendering.
        # (If you need offline use, set this to a local URL instead of 'cdn'.)
        cfg = dict(getattr(self.fig, "_config", {}) or {})
        cfg.setdefault("mathjax", "cdn")
        self.fig._config = cfg
        self.fig.update_layout(showlegend=True, margin=dict(l=40, r=20, t=20, b=40))
        self.fig.update_xaxes(showgrid=True)
        self.fig.update_yaxes(showgrid=True)

    def _find_trace(self, handle: PlotlyTraceHandle):
        for tr in self.fig.data:
            meta = getattr(tr, "meta", None)
            if isinstance(meta, dict) and meta.get("_gu_uid") == handle.uid:
                return tr
            # Fallback: try Plotly's uid if meta wasn't preserved
            if getattr(tr, "uid", None) == handle.uid:
                return tr
        return None

    def add_plot(self, name: str, x: numpy.ndarray, y: numpy.ndarray, style: Style) -> PlotlyTraceHandle:
        uid = str(uuid.uuid4())
        safe_name = _plotly_sanitize_trace_name(name)
        tr = self._go.Scatter(name=safe_name, x=x, y=y, mode="lines", uid=uid, meta={"_gu_uid": uid})
        with self.fig.batch_update():
            self.fig.add_trace(tr)
            self.apply_style(PlotlyTraceHandle(uid), style)
        return PlotlyTraceHandle(uid)

    def update_plot(self, handle: PlotlyTraceHandle, x: numpy.ndarray, y: numpy.ndarray) -> None:
        tr = self._find_trace(handle)
        if tr is None:
            return
        with self.fig.batch_update():
            tr.x = x
            tr.y = y

    def apply_style(self, handle: PlotlyTraceHandle, style: Style) -> None:
        tr = self._find_trace(handle)
        if tr is None:
            return

        dash = None
        if style.linestyle is not None:
            dash = self._LINESTYLE_MAP.get(style.linestyle)

        with self.fig.batch_update():
            tr.visible = bool(style.visible)
            if style.color is not None:
                tr.line.color = style.color
            if style.width is not None:
                tr.line.width = style.width
            if dash is not None:
                tr.line.dash = dash
            if style.opacity is not None:
                tr.opacity = style.opacity

    def remove_plot(self, handle: PlotlyTraceHandle) -> None:
        uid = handle.uid
        existing = tuple(self.fig.data)

        def matches(t) -> bool:
            meta = getattr(t, "meta", None)
            if isinstance(meta, dict) and meta.get("_gu_uid") == uid:
                return True
            return getattr(t, "uid", None) == uid

        if not any(matches(t) for t in existing):
            return

        with self.fig.batch_update():
            self.fig.data = tuple(t for t in existing if not matches(t))

    def set_viewport(self, x_range: Tuple[float, float], y_range: Optional[Tuple[float, float]]) -> None:
        xmin, xmax = x_range
        with self.fig.batch_update():
            self.fig.layout.xaxis.range = [xmin, xmax]
            if y_range is not None:
                ymin, ymax = y_range
                self.fig.layout.yaxis.range = [ymin, ymax]

    def request_redraw(self) -> None:
        return


# === END SECTION: Renderer backends ===

# === SECTION: Plot model [id: model-plot] ===
class Plot:
    """Represents one plotted SymPy expression.

    A plot has one independent variable (``symbol``) and zero or more parameter
    symbols (``param_symbols``). The compiled numerical function always expects
    arguments in the deterministic order:

    ``(symbol, *param_symbols)``

    Notes
    -----
    * Parameter symbols are always treated as scalars during evaluation; if a
      compiled function returns a scalar (e.g. constants or parameterized
      constants), :meth:`compute_data` broadcasts it to match the sampled x-grid.
    """

    def __init__(
        self,
        name: str,
        expr: sympy.Expr,
        symbol: sympy.Symbol,
        param_symbols: Tuple[sympy.Symbol, ...],
        domain: Union[Tuple[float, float], _ViewportToken],
        samples: Union[int, _ViewportToken],
        style: Style,
        on_change_callback: Callable[["Plot", bool, bool], None],
        param_value_getter: Optional[Callable[[Tuple[sympy.Symbol, ...]], Tuple[Any, ...]]] = None,
    ) -> None:
        self._name = str(name)
        self._expr = expr
        self._symbol = symbol
        self._param_symbols = tuple(param_symbols)
        self._param_value_getter = param_value_getter
        self._domain = domain
        self._samples = samples
        self._style = style
        self._on_change_callback = on_change_callback

        self._reactive_style = ReactiveStyle(self._style, self._on_style_proxy_change)

        self.backend_handle: Any = None
        self._func: Optional[Callable[..., Any]] = None
        self._compile()

    def __repr__(self) -> str:
        params = ", ".join(p.name for p in self._param_symbols)
        params_s = f" params=[{params}]" if params else ""
        return f"<Plot '{self.name}': {self.expr}{params_s} | visible={self.visible}>"

    @property
    def name(self) -> str:
        return self._name

    @property
    def expr(self) -> sympy.Expr:
        return self._expr

    @property
    def symbol(self) -> sympy.Symbol:
        return self._symbol

    @property
    def param_symbols(self) -> Tuple[sympy.Symbol, ...]:
        """Ordered parameter symbols used by this plot (deterministic)."""
        return self._param_symbols

    @property
    def style(self) -> ReactiveStyle:
        return self._reactive_style

    @property
    def visible(self) -> bool:
        return self._style.visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self.style.visible = value

    @property
    def samples(self) -> Union[int, _ViewportToken]:
        return self._samples

    @samples.setter
    def samples(self, value: Union[int, _ViewportToken]) -> None:
        self.update(samples=value)

    @property
    def domain(self) -> Union[Tuple[float, float], _ViewportToken]:
        return self._domain

    @domain.setter
    def domain(self, value: Union[Tuple[float, float], _ViewportToken]) -> None:
        self.update(domain=value)

    def _compile(self) -> None:
        """Compile the sympy expression to a numpy function."""
        declared_args = (self._symbol, *self._param_symbols)
        free_syms = tuple(a for a in declared_args if a in self._expr.free_symbols)

        try:
            base = numpify(self._expr, args=free_syms, vectorize=True)
        except Exception as exc:
            raise GuideError(
                f"Failed to compile expression for plot {self._name!r}. "
                "If this expression is constant or does not depend on some declared symbols, "
                "this typically indicates a compiler mismatch.",
            ) from exc

        used_positions = [i for i, a in enumerate(declared_args) if a in set(free_syms)]
        uses_x = self._symbol in self._expr.free_symbols

        def compiled(x: numpy.ndarray, *params: float) -> numpy.ndarray:
            x_arr = numpy.asarray(x, dtype=float)
            full = (x_arr, *params)
            used_vals = [full[i] for i in used_positions]
            y = base(*used_vals)
            y_arr = numpy.asarray(y, dtype=float)
            if not uses_x:
                # Broadcast constants / parameter-only expressions to the x-grid.
                y_arr = numpy.broadcast_to(y_arr, x_arr.shape)
            return y_arr

        self._func = compiled
    def _on_style_proxy_change(self) -> None:
        self._on_change_callback(self, needs_recompute=False, needs_redraw=True)

    def update(
        self,
        *,
        expr: Optional[sympy.Expr] = None,
        symbol: Optional[sympy.Symbol] = None,
        param_symbols: Optional[Tuple[sympy.Symbol, ...]] = None,
        domain: Optional[Union[Tuple[float, float], _ViewportToken]] = None,
        samples: Optional[Union[int, _ViewportToken]] = None,
        style: Optional[Style] = None,
        visible: Optional[bool] = None,
    ) -> None:
        """Update plot configuration and trigger controller callbacks."""
        needs_recompute = False
        needs_redraw = False

        if expr is not None and expr != self._expr:
            self._expr = expr
            needs_recompute = True
        if symbol is not None and symbol != self._symbol:
            self._symbol = symbol
            needs_recompute = True
        if param_symbols is not None and tuple(param_symbols) != self._param_symbols:
            self._param_symbols = tuple(param_symbols)
            needs_recompute = True

        if domain is not None and domain != self._domain:
            self._domain = domain
            needs_recompute = True
        if samples is not None and samples != self._samples:
            self._samples = samples
            needs_recompute = True

        if needs_recompute and (expr is not None or symbol is not None or param_symbols is not None):
            self._compile()

        if style is not None:
            self._style = style
            self._reactive_style._style = style
            needs_redraw = True

        if visible is not None and visible != self._style.visible:
            self._style.visible = visible
            needs_redraw = True

        self._on_change_callback(self, needs_recompute, needs_redraw)

    def compute_data(
        self,
        viewport_range: Tuple[float, float],
        global_samples: int,
        param_values: Optional[Sequence[float]] = None,
    ) -> Tuple[numpy.ndarray, numpy.ndarray]:
        """Sample this plot on the given viewport, using provided parameter values."""
        v_min, v_max = viewport_range
        bounds = self._domain

        # Determine sampling bounds
        if bounds is VIEWPORT:
            start, stop = v_min, v_max
        else:
            d_min, d_max = bounds
            real_d_min = d_min if d_min is not None else float("-inf")
            real_d_max = d_max if d_max is not None else float("inf")
            start = max(v_min, real_d_min)
            stop = min(v_max, real_d_max)

        if start >= stop:
            return numpy.array([]), numpy.array([])

        # Determine number of samples
        n = global_samples if self._samples is VIEWPORT else int(self._samples)
        
        # Generate x values
        x_arr = numpy.linspace(start, stop, n)
        
        # Get parameter values
        if param_values is None and self._param_symbols:
            if self._param_value_getter is None:
                raise ValueError(
                    "Missing parameter values for plot evaluation. "
                    "Pass `param_values=...` explicitly, or call `compute_data` "
                    "on a Plot created by a SmartFigure (which provides registry values)."
                )
            param_values = tuple(self._param_value_getter(self._param_symbols))
        elif param_values is None:
            param_values = ()

        # Evaluate the function
        param_tuple = tuple(float(v) for v in param_values)
        y_arr = self._func(x_arr, *param_tuple)
        return x_arr, numpy.asarray(y_arr, dtype=float)


# === END SECTION: Plot model ===

# === SECTION: Parameter slider bindings [id: ui-bindings] ===

# -----------------------------------------------------------------------------
# Stage 5: Parameter slider bindings (UI layer)
# -----------------------------------------------------------------------------
class _ParamSliderBinding:
    """Two-way binding between a :class:`SmartParameter` and a :class:`SmartSlider`.

    The binding protocol follows the blueprint:

    * Slider -> parameter: user interaction calls ``set_protected`` / ``set_bounds``.
    * Parameter -> slider: external parameter changes update the widget without
      feedback loops.

    Notes
    -----
    This class lives in the UI layer. It is created only when a
    :class:`SmartFigure` widget is constructed (i.e. when ipywidgets is available).
    """

    def __init__(
        self,
        *,
        symbol: sympy.Symbol,
        param: SmartParameter,
        slider: Any,
        slider_token: CallbackToken,
    ) -> None:
        self.symbol = symbol
        self.param = param
        self.slider = slider
        self.slider_token = slider_token

        # Guard used to prevent widget updates from triggering callbacks.
        self._suspend_handlers = False

        # We store handlers explicitly so we can unobserve them reliably.
        self._is_attached = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def attach(self) -> None:
        """Attach widget observers."""
        if self._is_attached:
            return

        # Disable SmartSlider's internal min/max/step wiring. We want the
        # SmartParameter to be the source of truth.
        for widget_attr, handler_name in (
            ("min_input", "_update_min"),
            ("max_input", "_update_max"),
            ("step_input", "_update_step"),
        ):
            try:
                inp = getattr(self.slider, widget_attr)
                handler = getattr(self.slider, handler_name)
                inp.unobserve(handler, names="value")
            except Exception:
                pass

        try:
            self.slider.slider.observe(self._on_slider_value, names="value")
            self.slider.min_input.observe(self._on_bounds_change, names="value")
            self.slider.max_input.observe(self._on_bounds_change, names="value")
            self.slider.step_input.observe(self._on_step_change, names="value")
        finally:
            self._is_attached = True

    def detach(self) -> None:
        """Detach widget observers (best-effort)."""
        if not self._is_attached:
            return
        try:
            self.slider.slider.unobserve(self._on_slider_value, names="value")
            self.slider.min_input.unobserve(self._on_bounds_change, names="value")
            self.slider.max_input.unobserve(self._on_bounds_change, names="value")
            self.slider.step_input.unobserve(self._on_step_change, names="value")
        except Exception:
            pass
        self._is_attached = False

    # ------------------------------------------------------------------
    # Parameter -> slider sync
    # ------------------------------------------------------------------
    def sync_from_param(
        self,
        *,
        owner_token: Optional[CallbackToken] = None,
        what_changed: Tuple[str, ...] = (),
    ) -> None:
        """Update the widget to reflect the parameter state.

        If ``owner_token`` matches this binding's ``slider_token`` we skip updates
        to avoid feedback loops.
        """
        if owner_token == self.slider_token:
            return

        self._suspend_handlers = True
        try:
            v = float(self.param.value)

            # SmartSlider and FloatSlider require finite numeric bounds.
            mn = self._coerce_bound(self.param.min_val, fallback=v - 1.0)
            mx = self._coerce_bound(self.param.max_val, fallback=v + 1.0)
            if not (mn < mx):
                mn, mx = v - 1.0, v + 1.0

            step = self._coerce_step(getattr(self.param, "step", None), mn, mx)

            # Update slider first, then text inputs.
            self.slider.slider.min = mn
            self.slider.slider.max = mx
            self.slider.slider.step = step
            self.slider.slider.value = self._clamp(v, mn, mx)

            self.slider.min_input.value = mn
            self.slider.max_input.value = mx
            self.slider.step_input.value = step
        finally:
            self._suspend_handlers = False

    @staticmethod
    def _coerce_bound(raw: Any, *, fallback: float) -> float:
        try:
            if raw is None:
                return float(fallback)
            return float(raw)
        except Exception:
            return float(fallback)

    @staticmethod
    def _clamp(val: float, mn: float, mx: float) -> float:
        return max(mn, min(mx, val))

    @staticmethod
    def _coerce_step(raw: Any, mn: float, mx: float) -> float:
        try:
            if raw is None:
                raise TypeError
            step = float(raw)
        except Exception:
            # A reasonable default: 200 steps across the range.
            step = (mx - mn) / 200.0 if mx > mn else 0.01
        if step <= 0:
            step = 0.01
        return step

    # ------------------------------------------------------------------
    # Slider -> parameter handlers
    # ------------------------------------------------------------------
    def _on_slider_value(self, change: Dict[str, Any]) -> None:
        if self._suspend_handlers:
            return
        try:
            new_val = float(change["new"])
        except Exception:
            return

        # Update parameter, then re-sync from parameter to reflect any coercion.
        self._set_param_value(new_val)
        self.sync_from_param(owner_token=None)

    def _on_bounds_change(self, _change: Dict[str, Any]) -> None:
        if self._suspend_handlers:
            return
        try:
            mn = float(self.slider.min_input.value)
            mx = float(self.slider.max_input.value)
        except Exception:
            return

        self._set_param_bounds(mn, mx)
        # Always re-sync: bounds changes may clamp value.
        self.sync_from_param(owner_token=None)

    def _on_step_change(self, change: Dict[str, Any]) -> None:
        if self._suspend_handlers:
            return
        try:
            new_step = float(change["new"])
        except Exception:
            return
        if new_step <= 0:
            return

        # Best-effort: `step` is not reactive by contract.
        try:
            setattr(self.param, "step", new_step)
        except Exception:
            pass

        self._suspend_handlers = True
        try:
            self.slider.slider.step = new_step
        finally:
            self._suspend_handlers = False

    def _set_param_value(self, new_val: float) -> None:
        try:
            self.param.set_protected(
                new_val,
                owner_token=self.slider_token,
                what_changed=("value",),
                source="slider",
            )
            return
        except TypeError:
            # Older/alternate SmartParameter implementations.
            pass
        except Exception:
            return

        try:
            self.param.value = new_val
        except Exception:
            pass

    def _set_param_bounds(self, mn: float, mx: float) -> None:
        try:
            self.param.set_bounds(min_val=mn, max_val=mx, owner_token=self.slider_token, source="slider")
            return
        except TypeError:
            pass
        except Exception:
            return

        # Fallback: set attributes directly if available.
        try:
            self.param.min_val = mn
            self.param.max_val = mx
        except Exception:
            pass

# === END SECTION: Parameter slider bindings ===

# === SECTION: SmartFigure controller [id: controller] ===
class SmartFigure:
    """Main plotting controller with a Plotly FigureWidget view.

    DESIGN OVERVIEW
    ---------------
    ``SmartFigure`` is a small controller that orchestrates:

    * **Expression analysis**: determine the independent variable and which free
      symbols should be treated as **parameters**.
    * **Registry integration**: parameters live in a :class:`SmartParameterRegistry`
      (shared by default, overridable per-figure).
    * **Dependency tracking**: changing a parameter recomputes **only** the plots
      that depend on that parameter.
    * **UI policy (Option A)**: a figure shows sliders only for parameters used by
      its current plots; removing a plot removes its now-unused sliders, but the
      registry entry is retained.

    Expression analysis rules (blueprint)
    ------------------------------------
    Let ``S = expr.free_symbols``.

    * ``|S| == 0``: constant expression; independent symbol is ``symbol`` if
      provided, else the figure's default ``var``. No parameters.
    * ``|S| == 1``:
      - if ``symbol`` is omitted or equals the sole free symbol: that symbol is
        the independent variable, no parameters.
      - if ``symbol`` is provided and differs: treat as a *parameterized
        constant* in ``symbol``; the sole free symbol becomes a parameter.
    * ``|S| > 1``: the user must pass ``symbol=...`` (and it must be in ``S``);
      all other free symbols become parameters.

    Parameter ordering and evaluation contract
    -----------------------------------------
    Parameters are sorted deterministically by ``.name`` and compiled with
    ``numpify(args=(symbol, *params_sorted))``. At evaluation time, each plot is
    called as ``f(x_values, *param_values_sorted)``.

    Registry retention policy
    -------------------------
    Parameters are **never** removed from the registry, even if unused by the
    current figure. Only this figure's callbacks and UI sliders are cleaned up.
    """

    # Class-level default registry (shared by default).
    _DEFAULT_PARAMETER_REGISTRY: SmartParameterRegistry = SmartParameterRegistry()

    @classmethod
    def _reset_shared_parameter_registry_for_tests(cls) -> None:
        """Reset the shared default parameter registry (test helper)."""
        cls._DEFAULT_PARAMETER_REGISTRY = SmartParameterRegistry()

    def __init__(
        self,
        var: sympy.Symbol = sympy.Symbol("x"),
        x_range: Tuple[SupportsFloat, SupportsFloat] = (-4, 4),
        y_range: Tuple[SupportsFloat, SupportsFloat] = (-3, 3),
        samples: int = 1000,
        show_now: bool = True,
        *,
        parameter_registry: Optional[SmartParameterRegistry] = None,
    ) -> None:
        self.default_symbol = var
        self._x_range = (float(x_range[0]), float(x_range[1]))
        self._y_range = (float(y_range[0]), float(y_range[1]))
        self._global_samples = int(samples)

        # Parameter registry: shared by default, but can be overridden per-figure.
        self.parameter_registry: SmartParameterRegistry = (
            parameter_registry if parameter_registry is not None else self._DEFAULT_PARAMETER_REGISTRY
        )

        # Plots and dependencies.
        self._plots: "OrderedDict[str, Plot]" = OrderedDict()
        self._plots_by_param: Dict[sympy.Symbol, set[str]] = {}
        self._param_callback_token: Dict[sympy.Symbol, CallbackToken] = {}
        self._plot_params: Dict[str, Tuple[sympy.Symbol, ...]] = {}

        # UI (Stage 5): per-figure parameter sliders (Option A).
        self._widget: Optional[object] = None
        self._sliders_box: Optional[object] = None
        self._sliders_by_param: Dict[sympy.Symbol, _ParamSliderBinding] = {}

        self._backend: Optional[PlotlyBackend] = None

        if show_now:
            self.show()

    # -------------------------------------------------------------------------
    # View / widget lifecycle
    # -------------------------------------------------------------------------
    def _ensure_backend(self) -> "PlotlyBackend":
        """Create and initialize the plotting backend if needed.

        This is a lazy initializer shared by :attr:`widget` and :attr:`backend`.
        """
        if self._backend is None:
            self._backend = PlotlyBackend()
            self._backend.set_viewport(self._x_range, self._y_range)
            for plot in self._plots.values():
                self._create_backend_primitive(plot)
            self._update_all_data()
        return self._backend

    @property
    def backend(self) -> "PlotlyBackend":
        """Return the (lazily created) plotting backend.

        This is primarily useful for testing and introspection. Accessing this
        property does not display anything.
        """
        return self._ensure_backend()

    @property
    def plots(self) -> Mapping[str, Plot]:
        """Return a read-only mapping of the registered plots.

        Returns
        -------
        Mapping[str, Plot]
            A dictionary-like view mapping plot names to Plot objects.
            modifications must be done via :meth:`plot` or :meth:`remove`.
        """
        return MappingProxyType(self._plots)


    def _ensure_widget_container(self) -> object:
        """Build (and cache) the ipywidgets container for this figure.

        The container always includes a slider column (hidden when empty) and the
        Plotly ``FigureWidget``.

        Raises
        ------
        GuideError
            If running in Google Colab or if ipywidgets is unavailable.
        """
        _require_not_colab()

        backend = self._ensure_backend()
        widgets = _lazy_import_ipywidgets()

        if self._widget is None:
            self._sliders_box = widgets.VBox(
                [],
                layout=widgets.Layout(
                    display="none",
                    overflow="auto",
                    max_width="360px",
                    padding="0 10px 0 0",
                ),
            )

            self._widget = widgets.HBox(
                [self._sliders_box, backend.fig],
                layout=widgets.Layout(align_items="stretch"),
            )

            # Populate sliders for any parameters already used by existing plots.
            self._sync_ui_sliders_with_dependencies()

        return self._widget

    @property
    def widget(self) -> object:
        """Return the interactive widget (slider column + plot view)."""
        return self._ensure_widget_container()

    def show(self):
        w = self.widget
        try:
            from IPython.display import display  # type: ignore
            display(w)
        except Exception:
            pass
        return w



    # -------------------------------------------------------------------------
    # Stage 5: Slider UI policy (Option A)
    # -------------------------------------------------------------------------
    def _used_param_symbols(self) -> Tuple[sympy.Symbol, ...]:
        """Return the parameter symbols currently used by this figure.

        Symbols are returned sorted deterministically by ``.name``.
        """
        used = [s for s, names in self._plots_by_param.items() if names]
        return tuple(sorted(used, key=lambda s: s.name))

    def _refresh_sliders_box(self) -> None:
        """Rebuild the slider column from current dependencies (best-effort)."""
        if self._sliders_box is None:
            return

        ordered_syms = self._used_param_symbols()
        children: list[Any] = []
        for s in ordered_syms:
            binding = self._sliders_by_param.get(s)
            if binding is not None:
                children.append(binding.slider)

        self._sliders_box.children = tuple(children)
        self._sliders_box.layout.display = "flex" if children else "none"

    def _sync_ui_sliders_with_dependencies(self) -> None:
        """Ensure the UI shows sliders only for parameters used by this figure."""
        if self._sliders_box is None:
            return

        desired = set(self._used_param_symbols())
        existing = set(self._sliders_by_param.keys())

        # Create missing bindings.
        for s in sorted(desired - existing, key=lambda sym: sym.name):
            self._ensure_param_slider(s)

        # Remove bindings that are no longer needed.
        for s in sorted(existing - desired, key=lambda sym: sym.name):
            self._remove_param_slider(s)

        self._refresh_sliders_box()

    def _ensure_param_slider(self, sym: sympy.Symbol) -> None:
        """Create and attach a slider for the given parameter symbol."""
        if self._sliders_box is None:
            return
        if sym in self._sliders_by_param:
            return

        param = self.parameter_registry.get_param(sym)

        # SmartSlider requires finite bounds.
        try:
            v = float(param.value)
        except Exception:
            v = 0.0
        try:
            mn = float(param.min_val) if param.min_val is not None else v - 1.0
        except Exception:
            mn = v - 1.0
        try:
            mx = float(param.max_val) if param.max_val is not None else v + 1.0
        except Exception:
            mx = v + 1.0
        if not (mn < mx):
            mn, mx = v - 1.0, v + 1.0

        step = getattr(param, "step", None)
        try:
            step_f = float(step) if step is not None else (mx - mn) / 200.0
        except Exception:
            step_f = (mx - mn) / 200.0
        if step_f <= 0:
            step_f = 0.01

        slider = SmartSlider(value=v, min_val=mn, max_val=mx, step=step_f, description=str(sym))
        # `CallbackToken` is an opaque value used to prevent callback feedback loops.
        # Some implementations require an explicit string token.
        raw_token = f"slider:{uuid.uuid4()}"
        try:
            token = CallbackToken(token=raw_token)  # type: ignore[call-arg]
        except TypeError:
            token = CallbackToken(raw_token)  # type: ignore[call-arg]
        binding = _ParamSliderBinding(symbol=sym, param=param, slider=slider, slider_token=token)
        binding.attach()

        # Bring slider fully in sync with parameter (in case of coercion/clamping).
        binding.sync_from_param(owner_token=None)

        self._sliders_by_param[sym] = binding

    def _remove_param_slider(self, sym: sympy.Symbol) -> None:
        """Remove and dispose of a parameter slider from this figure's UI."""
        binding = self._sliders_by_param.pop(sym, None)
        if binding is None:
            return

        try:
            binding.detach()
        finally:
            try:
                binding.slider.close()
            except Exception:
                pass

        self._refresh_sliders_box()
    # -------------------------------------------------------------------------
    # Ranges / viewport
    # -------------------------------------------------------------------------
    @property
    def x_range(self) -> Tuple[float, float]:
        return self._x_range

    @x_range.setter
    def x_range(self, val: Tuple[SupportsFloat, SupportsFloat]) -> None:
        self._x_range = (float(val[0]), float(val[1]))
        if self._backend:
            self._backend.set_viewport(self._x_range, self._y_range)
        self._update_all_data()

    @property
    def y_range(self) -> Tuple[float, float]:
        return self._y_range

    @y_range.setter
    def y_range(self, val: Tuple[SupportsFloat, SupportsFloat]) -> None:
        self._y_range = (float(val[0]), float(val[1]))
        if self._backend:
            self._backend.set_viewport(self._x_range, self._y_range)
        self._update_all_data()

    # -------------------------------------------------------------------------
    # Expression analysis (Stage 2)
    # -------------------------------------------------------------------------
    def _analyze_expr(
        self, expr: sympy.Expr, requested: Optional[sympy.Symbol]
    ) -> Tuple[sympy.Symbol, Tuple[sympy.Symbol, ...]]:
        """Return (independent_symbol, param_symbols_sorted) for `expr`.

        Rules (blueprint):
        * |S|>1: must specify `requested` (even if it is not in S).
        * |S|=1: if `requested` is None -> that symbol is independent;
                 if requested differs -> parameterized constant.
        * |S|=0: constant expression; independent is requested or default_symbol.
        """
        if requested is not None and not isinstance(requested, sympy.Symbol):
            raise GuideError(f"symbol must be a SymPy Symbol, got {type(requested)!r}")

        free_syms = tuple(sorted(expr.free_symbols, key=lambda s: s.name))

        if len(free_syms) == 0:
            sym = requested if requested is not None else self.default_symbol
            return sym, ()

        if len(free_syms) == 1:
            only = free_syms[0]
            if requested is None or requested == only:
                return only, ()
            # Parameterized constant in `requested`.
            return requested, (only,)

        # len(free_syms) > 1
        if requested is None:
            raise GuideError(
                f"Expression `{expr}` has multiple symbols `{set(free_syms)}`.",
                hint="Specify 'symbol=...' explicitly.",
            )
        params = tuple(s for s in free_syms if s != requested)
        return requested, params

    def _resolve_symbol(self, expr: sympy.Expr, requested: Optional[sympy.Symbol]) -> sympy.Symbol:
        """Backwards-compatible helper returning only the independent symbol."""
        sym, _params = self._analyze_expr(expr, requested)
        return sym

    # -------------------------------------------------------------------------
    # Dependency tracking + callbacks (Stage 4)
    # -------------------------------------------------------------------------
    def _ensure_param_exists(self, sym: sympy.Symbol) -> None:
        _ = self.parameter_registry.get_param(sym)

    def _ensure_param_callback(self, sym: sympy.Symbol) -> None:
        if sym in self._param_callback_token:
            return
        param = self.parameter_registry.get_param(sym)
        token = param.register_callback(self._on_param_change)
        self._param_callback_token[sym] = token

    def _maybe_remove_param_callback(self, sym: sympy.Symbol) -> None:
        if sym in self._plots_by_param and self._plots_by_param[sym]:
            return
        token = self._param_callback_token.pop(sym, None)
        if token is None:
            return
        try:
            self.parameter_registry.get_param(sym).remove_callback(token)
        except Exception:
            # Best effort: never let callback cleanup break figure usage.
            pass

        # Stage 5: remove slider from this figure's UI (registry entry is retained).
        self._remove_param_slider(sym)

    def _set_plot_params(self, plot_name: str, param_syms: Tuple[sympy.Symbol, ...]) -> None:
        """Update dependency mappings for one plot name."""
        old = self._plot_params.get(plot_name, ())
        new = tuple(param_syms)

        # Remove old dependencies.
        for s in old:
            names = self._plots_by_param.get(s)
            if names is not None:
                names.discard(plot_name)
                if not names:
                    self._plots_by_param.pop(s, None)
                    self._maybe_remove_param_callback(s)
                    self._remove_param_slider(s)

        # Add new dependencies.
        for s in new:
            self._plots_by_param.setdefault(s, set()).add(plot_name)
            self._ensure_param_exists(s)
            self._ensure_param_callback(s)

        self._plot_params[plot_name] = new

        self._sync_ui_sliders_with_dependencies()

    def _on_param_change(
        self,
        param: SmartParameter,
        *,
        owner_token: Optional[CallbackToken] = None,
        what_changed: Tuple[str, ...] = (),
        **_kwargs: Any,
    ) -> None:
        # Stage 5: keep any live slider in sync with the parameter.
        param_id = param.id
        if isinstance(param_id, sympy.Symbol):
            binding = self._sliders_by_param.get(param_id)
            if binding is not None:
                binding.sync_from_param(owner_token=owner_token, what_changed=what_changed)

        # Recompute only when the value changes (bounds-only changes do not affect evaluation).
        # If bounds changes clamp the value, Stage 1 ensures "value" appears in what_changed.
        if what_changed and "value" not in what_changed:
            return

        if not self._backend:
            # If no live view exists yet, we defer recompute to the next draw.
            return

        param_id = param.id
        if not isinstance(param_id, sympy.Symbol):
            return

        affected = tuple(self._plots_by_param.get(param_id, set()))
        for name in affected:
            plot = self._plots.get(name)
            if plot is None:
                continue
            self._recompute_and_draw(plot)

    # -------------------------------------------------------------------------
    # Public plotting API
    # -------------------------------------------------------------------------
    def plot(
        self,
        expr: object,
        *,
        name: Optional[str] = None,
        symbol: Optional[sympy.Symbol] = None,
        domain: Optional[Union[Tuple[SupportsFloat, SupportsFloat], _ViewportToken]] = None,
        samples: Optional[Union[int, _ViewportToken]] = None,
        style: Optional[Mapping[str, object]] = None,
        visible: Optional[bool] = None,
    ) -> Plot:
        """Add or update a plot by name.

        Parameters
        ----------
        expr:
            SymPy expression (or something SymPy can sympify).
        name:
            Unique identifier for this plot within the figure. If omitted, an
            auto-name ``f_k`` is chosen.
        symbol:
            Independent variable. If omitted on first creation, it is inferred by
            :meth:`_analyze_expr` (see class docstring). When updating an existing
            plot, omitting `symbol` keeps the previous independent symbol.
        """
        if name is None:
            name = self._next_auto_name()

        expr_sp = sympy.sympify(expr)

        style_obj = Style()
        if style:
            try:
                for k, v in style.items():
                    if not hasattr(style_obj, k):
                        raise ValueError(f"Unknown style key '{k}'")
                    setattr(style_obj, k, v)
            except (ValueError, TypeError) as e:
                raise GuideError(f"Style configuration error: {e}") from e
        if visible is not None:
            style_obj.visible = visible

        new_domain_spec = None
        if domain is not None:
            new_domain_spec = self._normalize_bounds(domain)

        if name in self._plots:
            existing_plot = self._plots[name]
            # Ensure direct Plot.compute_data(...) can read registry parameter values.
            existing_plot._param_value_getter = self._param_values_for_symbols
            requested_symbol = symbol if symbol is not None else existing_plot.symbol
            resolved_sym, param_syms = self._analyze_expr(expr_sp, requested_symbol)

            if new_domain_spec is None and domain is None:
                new_domain_spec = None  # keep existing
            # Ensure parameters exist and update dependencies.
            for ps in param_syms:
                self._ensure_param_exists(ps)
            self._set_plot_params(name, param_syms)

            existing_plot.update(
                expr=expr_sp,
                symbol=resolved_sym,
                param_symbols=param_syms,
                domain=new_domain_spec,
                samples=samples,
                style=style_obj,
                visible=visible,
            )
            return existing_plot

        resolved_sym, param_syms = self._analyze_expr(expr_sp, symbol)

        # Ensure parameters exist and store dependency mapping.
        for ps in param_syms:
            self._ensure_param_exists(ps)
        self._set_plot_params(name, param_syms)

        domain_spec = self._normalize_bounds(domain or VIEWPORT)
        samples_spec = samples if samples is not None else VIEWPORT

        new_plot = Plot(
            name=name,
            expr=expr_sp,
            symbol=resolved_sym,
            param_symbols=param_syms,
            domain=domain_spec,
            samples=samples_spec,
            style=style_obj,
            param_value_getter=self._param_values_for_symbols,
            on_change_callback=self._handle_plot_change,
        )
        self._plots[name] = new_plot

        if self._backend:
            self._create_backend_primitive(new_plot)
            self._recompute_and_draw(new_plot)

        return new_plot

    def remove(self, name: str) -> None:
        if name not in self._plots:
            raise GuideError(f"No plot named '{name}'.")
        plot = self._plots.pop(name)

        # Dependency cleanup (does not remove parameters from registry).
        self._set_plot_params(name, ())
        self._plot_params.pop(name, None)

        if self._backend and plot.backend_handle:
            self._backend.remove_plot(plot.backend_handle)
            self._backend.request_redraw()

    def clear(self) -> None:
        if self._backend:
            for plot in self._plots.values():
                if plot.backend_handle:
                    self._backend.remove_plot(plot.backend_handle)
            self._backend.request_redraw()

        # Dependency cleanup (does not delete registry entries).
        for nm in list(self._plots.keys()):
            self._set_plot_params(nm, ())
        self._plots.clear()
        self._plot_params.clear()

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------
    def _next_auto_name(self) -> str:
        k = 1
        while True:
            nm = f"f_{k}"
            if nm not in self._plots:
                return nm
            k += 1

    def _normalize_bounds(self, domain: Any) -> Union[Tuple[float, float], _ViewportToken]:
        if domain is VIEWPORT:
            return VIEWPORT
        if not isinstance(domain, (tuple, list)) or len(domain) != 2:
            raise GuideError(f"Invalid domain format: {domain}. Expected (min, max).")
        try:
            d_min = float(domain[0]) if domain[0] is not None else None
            d_max = float(domain[1]) if domain[1] is not None else None
            return (d_min, d_max)  # type: ignore
        except (ValueError, TypeError):
            raise GuideError(f"Invalid domain format: {domain}. Expected (min, max).")

    def _create_backend_primitive(self, plot: Plot) -> None:
        if not self._backend:
            return
        handle = self._backend.add_plot(plot.name, numpy.array([]), numpy.array([]), plot._style)
        plot.backend_handle = handle
        self._backend.apply_style(handle, plot._style)

    def _handle_plot_change(self, plot: Plot, needs_recompute: bool, needs_redraw: bool) -> None:
        if not self._backend:
            return
        if needs_recompute:
            self._recompute_and_draw(plot)
        elif needs_redraw:
            if plot.backend_handle:
                self._backend.apply_style(plot.backend_handle, plot._style)
                self._backend.request_redraw()

    def _param_values_for_symbols(self, symbols: Tuple[sympy.Symbol, ...]) -> Tuple[float, ...]:
        """Return parameter values (floats) in the same order as `symbols`."""
        vals: list[float] = []
        for s in symbols:
            try:
                vals.append(float(self.parameter_registry.get_param(s).value))
            except Exception as e:
                raise GuideError(
                    f"Could not read value for parameter '{s}'.",
                    hint=str(e),
                ) from e
        return tuple(vals)

    def _param_values_for_plot(self, plot: Plot) -> Tuple[float, ...]:
        return self._param_values_for_symbols(plot.param_symbols)

    def _recompute_and_draw(self, plot: Plot) -> None:
        if not self._backend:
            return
        param_values = self._param_values_for_plot(plot)
        x, y = plot.compute_data(self._x_range, self._global_samples, param_values=param_values)
        if plot.backend_handle:
            self._backend.update_plot(plot.backend_handle, x, y)
            self._backend.apply_style(plot.backend_handle, plot._style)
            self._backend.request_redraw()

    def _update_all_data(self) -> None:
        for plot in self._plots.values():
            self._recompute_and_draw(plot)


# === END SECTION: SmartFigure controller ===

# === SECTION: Plugin exports [id: exports] ===
__gu_exports__ = __all__
__gu_priority__ = 200
__gu_enabled__ = True
# === END SECTION: Plugin exports ===
