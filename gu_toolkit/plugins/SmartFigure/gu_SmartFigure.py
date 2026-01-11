"""
gu_SmartFigure: Smart symbolic plotting (Plotly-first, JupyterLite-friendly)
============================================================================

`gu_SmartFigure` provides a small, student-facing API for plotting SymPy
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
from gu_SmartFigure import SmartFigure

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

import sys
import uuid
from types import MappingProxyType
from collections import OrderedDict
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    Union,
    TypeVar,
    runtime_checkable,
    OrderedDict as OrderedDictType,
)

import numpy
import sympy

from gu_numpify import numpify
from gu_SmartException import GuideError

# ==============================================================================
# Plotly text / legend label sanitation
# ==============================================================================
def _plotly_sanitize_trace_name(label: Any) -> str:
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

# ==============================================================================
# 0. Fundamentals & Tokens
# ==============================================================================

class _ViewportToken:
    """Sentinel token representing 'inherit settings from the parent figure'."""
    def __repr__(self) -> str:
        return "VIEWPORT"


VIEWPORT = _ViewportToken()

# ==============================================================================
# Helpers
# ==============================================================================
import ipywidgets as widgets
from IPython.display import display

class SmartSlider(widgets.VBox):
    def __init__(self, value=0.0, min_val=0.0, max_val=10.0, step=0.1, description='Value'):
        super().__init__()
        
        # 1. Create the Core Components
        self.slider = widgets.FloatSlider(
            value=value,
            min=min_val,
            max=max_val,
            step=step,
            description=description,
            continuous_update=False, # Wait until mouse release to trigger heavy updates
            layout=widgets.Layout(width='300px')
        )
        
 
        
        self.settings_btn = widgets.Button(
            icon='cog',
            layout=widgets.Layout(width='35px', height='auto'),
            tooltip="Configure Slider Limits"
        )

        # 2. Create the Configuration Components (Hidden by default)
        self.min_input = widgets.FloatText(value=min_val, description='Min:', layout=widgets.Layout(width='150px'))
        self.max_input = widgets.FloatText(value=max_val, description='Max:', layout=widgets.Layout(width='150px'))
        self.step_input = widgets.FloatText(value=step, description='Step:', layout=widgets.Layout(width='150px'))
        
        self.settings_panel = widgets.HBox(
            [self.min_input, self.max_input, self.step_input],
            layout=widgets.Layout(display='none', padding='5px 0 0 0') # Initially hidden
        )

        # 3. Layout the Main View
        self.main_row = widgets.HBox([
            self.slider, 
            self.settings_btn
        ])
        
        # Add children to the VBox (Main Row + Settings Panel)
        self.children = [self.main_row, self.settings_panel]

        # 4. Linkage and Logic
        
    
        
        # Button Logic: Toggle Settings Panel
        self.settings_btn.on_click(self._toggle_settings)
        
        # Settings Logic: Update Slider Properties
        self.min_input.observe(self._update_min, names='value')
        self.max_input.observe(self._update_max, names='value')
        self.step_input.observe(self._update_step, names='value')

    def _toggle_settings(self, b):
        """Show or hide the settings panel."""
        if self.settings_panel.layout.display == 'none':
            self.settings_panel.layout.display = 'flex'
        else:
            self.settings_panel.layout.display = 'none'

    def _update_min(self, change):
        """Update slider minimum. Ensure min < max."""
        new_min = change['new']
        if new_min < self.slider.max:
            self.slider.min = new_min
        else:
            # If user tries to set min > max, push min down slightly or handle error
            # Here we just reject the change implicitly by relying on traitlet validation usually,
            # but explicit logic prevents UI locking.
            pass

    def _update_max(self, change):
        """Update slider maximum."""
        new_max = change['new']
        if new_max > self.slider.min:
            self.slider.max = new_max

    def _update_step(self, change):
        """Update slider step size."""
        new_step = change['new']
        if new_step > 0:
            self.slider.step = new_step
# ==============================================================================
# Environment & dependency helpers (lazy imports)
# ==============================================================================

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
            "Google Colab is not supported by gu_SmartFigure's interactive widget.\n\n"
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





# ==============================================================================
# 1. Configuration (Style & Reactive Proxy)
# ==============================================================================

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

    def __init__(self, *args, **kwargs):
        if args:
            raise TypeError(
                "Style does not accept positional arguments. "
                "Use keyword arguments (color='red') or unpack a dict (**style)."
            )
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

    def __setattr__(self, name: str, value: Any) -> None:
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
    def __init__(self, style: Style, callback: Callable[[], None]):
        self._style = style
        self._callback = callback

    def __getattr__(self, name: str) -> Any:
        return getattr(self._style, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_style", "_callback"):
            super().__setattr__(name, value)
            return
        setattr(self._style, name, value)
        self._callback()

    def __repr__(self) -> str:
        return repr(self._style)


# ==============================================================================
# 2. Renderer (Backend)
# ==============================================================================

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

    def __init__(self, figsize=(7, 4), dpi=100):
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

    def add_plot(self, name: str, x: numpy.ndarray, y: numpy.ndarray, style: Style) -> Any:
        kw = self._translate_style(style)
        (line,) = self.ax.plot(x, y, label=name, **kw)
        return line

    def update_plot(self, handle: Any, x: numpy.ndarray, y: numpy.ndarray) -> None:
        handle.set_data(x, y)

    def apply_style(self, handle: Any, style: Style) -> None:
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

    def remove_plot(self, handle: Any) -> None:
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


# ==============================================================================
# 3. Model (Plot)
# ==============================================================================

class Plot:
    """Represents one plotted SymPy expression."""

    def __init__(
        self,
        name: str,
        expr: sympy.Expr,
        symbol: sympy.Symbol,
        domain: Union[Tuple[float, float], _ViewportToken],
        samples: Union[int, _ViewportToken],
        style: Style,
        on_change_callback: Callable[["Plot", bool, bool], None],
    ):
        self._name = name
        self._expr = expr
        self._symbol = symbol
        self._domain = domain
        self._samples = samples
        self._style = style
        self._on_change_callback = on_change_callback

        self._reactive_style = ReactiveStyle(self._style, self._on_style_proxy_change)

        self.backend_handle: Any = None
        self._func: Optional[Callable[[numpy.ndarray], numpy.ndarray]] = None
        self._compile()

    def __repr__(self) -> str:
        return f"<Plot '{self.name}': {self.expr} | visible={self.visible}>"

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
        try:
            self._func = numpify(self._expr, args=[self._symbol], safe=True)
        except Exception as e:
            raise ValueError(f"Failed to compile expression '{self._expr}': {e}") from e

    def _on_style_proxy_change(self) -> None:
        self._on_change_callback(self, needs_recompute=False, needs_redraw=True)

    def update(
        self,
        expr: Optional[sympy.Expr] = None,
        symbol: Optional[sympy.Symbol] = None,
        domain: Optional[Union[Tuple[float, float], _ViewportToken]] = None,
        samples: Optional[Union[int, _ViewportToken]] = None,
        style: Optional[Style] = None,
        visible: Optional[bool] = None,
    ) -> None:
        needs_recompute = False
        needs_redraw = False

        if expr is not None and expr != self._expr:
            self._expr = expr
            needs_recompute = True
        if symbol is not None and symbol != self._symbol:
            self._symbol = symbol
            needs_recompute = True
        if domain is not None and domain != self._domain:
            self._domain = domain
            needs_recompute = True
        if samples is not None and samples != self._samples:
            self._samples = samples
            needs_recompute = True

        if needs_recompute and (expr is not None or symbol is not None):
            self._compile()

        if style is not None:
            self._style = style
            self._reactive_style._style = style
            needs_redraw = True

        if visible is not None and visible != self._style.visible:
            self._style.visible = visible
            needs_redraw = True

        self._on_change_callback(self, needs_recompute, needs_redraw)

    def compute_data(self, viewport_range: Tuple[float, float], global_samples: int) -> Tuple[numpy.ndarray, numpy.ndarray]:
        v_min, v_max = viewport_range
        bounds = self._domain

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

        n = global_samples if self._samples is VIEWPORT else int(self._samples)

        try:
            x_arr = numpy.linspace(start, stop, n)
            if self._func is None:
                return numpy.array([]), numpy.array([])
            y_arr = self._func(x_arr)

            # --- Plotly/FigureWidget compatibility & numerical hygiene ---
            # Plotly accepts numpy arrays, but they must be numeric (not dtype=object
            # with SymPy scalars). We coerce to real float arrays here.
            x_arr = numpy.asarray(x_arr, dtype=float)
            y_arr = numpy.asarray(y_arr)

            # If SymPy/numpify produced an object array, attempt numeric coercion.
            if y_arr.dtype == object:
                try:
                    y_arr = y_arr.astype(float)
                except Exception as _e:
                    raise ValueError(
                        "Plot evaluation produced non-numeric values (dtype=object). "
                        "This often happens if the expression was not fully numeric after numpify. "
                        f"Expression: {self._expr}"
                    ) from _e

            # Complex values: allow near-real; otherwise error.
            if numpy.iscomplexobj(y_arr):
                imag_max = float(numpy.max(numpy.abs(numpy.imag(y_arr)))) if y_arr.size else 0.0
                if imag_max > 1e-12:
                    raise ValueError(
                        "Plot evaluation produced complex values with non-negligible imaginary part. "
                        f"Expression: {self._expr}"
                    )
                y_arr = numpy.real(y_arr)

            # Final coercion to float for stable widget transport.
            try:
                y_arr = numpy.asarray(y_arr, dtype=float)
            except Exception as _e:
                raise ValueError(
                    "Plot evaluation produced values that could not be converted to floats. "
                    f"Expression: {self._expr}"
                ) from _e

            # Ensure 1D and matching lengths.
            x_arr = numpy.ravel(x_arr)
            y_arr = numpy.ravel(y_arr)
            if x_arr.shape != y_arr.shape:
                raise ValueError(
                    "Plot evaluation returned x and y arrays with different shapes. "
                    f"x.shape={x_arr.shape}, y.shape={y_arr.shape}. "
                    f"Expression: {self._expr}"
                )

            return x_arr, y_arr
        except Exception as e:
            raise ValueError(f"Error evaluating '{self._expr}' on range [{start:.2f}, {stop:.2f}]: {e}") from e


# ==============================================================================
# 4. Controller (SmartFigure)
# ==============================================================================

class SmartFigure:
    """Main plotting controller with a Plotly FigureWidget view (Phase 1)."""

    def __init__(
        self,
        var: sympy.Symbol = sympy.Symbol("x"),
        x_range: Tuple[Any, Any] = (-4, 4),
        y_range: Tuple[Any, Any] = (-3, 3),
        samples: int = 1000,
        show_now: bool = True,
    ):
        self.default_symbol = var
        self._x_range = (float(x_range[0]), float(x_range[1]))
        self._y_range = (float(y_range[0]), float(y_range[1]))
        self._global_samples = samples

        self._plots: OrderedDictType[str, Plot] = OrderedDict()
        self._backend: Optional[PlotBackend] = None
        self._widget: Optional[Any] = None

        if show_now:
            self.show()

    @property
    def widget(self) -> Any:
        if self._widget is None:
            _require_not_colab()
            widgets = _lazy_import_ipywidgets()

            self._backend = PlotlyBackend()
            self._backend.set_viewport(self._x_range, self._y_range)

            for plot in self._plots.values():
                self._create_backend_primitive(plot)

            self._update_all_data()

            self._widget = widgets.VBox([self._backend.fig])
        return self._widget

    @property
    def backend(self) -> PlotBackend:
        _ = self.widget
        return self._backend  # type: ignore

    def show(self) -> Any:
        w = self.widget
        try:
            from IPython.display import display  # type: ignore
            display(w)
        except Exception:
            pass
        return w

    @property
    def x_range(self) -> Tuple[float, float]:
        return self._x_range

    @x_range.setter
    def x_range(self, val: Tuple[Any, Any]):
        self._x_range = (float(val[0]), float(val[1]))
        if self._backend:
            self._backend.set_viewport(self._x_range, self._y_range)
        self._update_all_data()


    @property
    def y_range(self) -> Tuple[float, float]:
        return self._y_range

    @y_range.setter
    def y_range(self, val: Tuple[Any, Any]):
        self._y_range = (float(val[0]), float(val[1]))
        if self._backend:
            self._backend.set_viewport(self._x_range, self._y_range)


    @property
    def plots(self) -> MappingProxyType[str, Plot]:
        return MappingProxyType(self._plots)

    def get_plot_names(self) -> List[str]:
        return list(self._plots.keys())

    def plot(
        self,
        expr: sympy.Expr,
        name: Optional[str] = None,
        symbol: Optional[sympy.Symbol] = None,
        domain: Optional[Union[Tuple[float, float], _ViewportToken]] = None,
        samples: Optional[Union[int, _ViewportToken]] = None,
        style: Optional[Union[Style, Dict[str, Any]]] = None,
        visible: bool = True,
    ) -> Plot:
        if name is None:
            name = self._next_auto_name()

        try:
            if style is not None:
                if isinstance(style, dict):
                    style_obj = Style(**style)
                elif isinstance(style, Style):
                    style_obj = style
                else:
                    raise TypeError("Style must be a dictionary or Style object.")
            else:
                style_obj = Style()
            style_obj.visible = visible
        except (ValueError, TypeError) as e:
            raise GuideError(f"Style configuration error: {e}") from e

        if name in self._plots:
            existing_plot = self._plots[name]
            new_domain_spec = None
            if domain is not None:
                new_domain_spec = self._normalize_bounds(domain)

            existing_plot.update(
                expr=sympy.sympify(expr),
                symbol=symbol,
                domain=new_domain_spec,
                samples=samples,
                style=style_obj,
                visible=visible,
            )
            return existing_plot

        expr = sympy.sympify(expr)
        resolved_sym = self._resolve_symbol(expr, symbol)

        domain_spec = self._normalize_bounds(domain or VIEWPORT)
        samples_spec = samples if samples is not None else VIEWPORT

        new_plot = Plot(
            name=name,
            expr=expr,
            symbol=resolved_sym,
            domain=domain_spec,
            samples=samples_spec,
            style=style_obj,
            on_change_callback=self._handle_plot_change,
        )

        self._plots[name] = new_plot

        if self._backend is not None:
            self._create_backend_primitive(new_plot)
            self._recompute_and_draw(new_plot)

        return new_plot

    def remove(self, name: str) -> None:
        if name in self._plots:
            plot = self._plots[name]
            if self._backend and plot.backend_handle:
                self._backend.remove_plot(plot.backend_handle)
                self._backend.request_redraw()
            del self._plots[name]

    def clear(self) -> None:
        if self._backend:
            for plot in self._plots.values():
                if plot.backend_handle:
                    self._backend.remove_plot(plot.backend_handle)
            self._backend.request_redraw()
        self._plots.clear()

    def _next_auto_name(self) -> str:
        k = 1
        while True:
            nm = f"f_{k}"
            if nm not in self._plots:
                return nm
            k += 1

    def _resolve_symbol(self, expr: sympy.Expr, requested: Optional[sympy.Symbol]) -> sympy.Symbol:
        free = expr.free_symbols
        if requested:
            if requested not in free and free:
                raise GuideError(
                    f"Requested symbol `{requested}` is not in expression `{expr}`.",
                    hint=f"Make sure that your expression depends on `{requested}`.",
                )
            return requested
        if not free:
            return self.default_symbol
        if len(free) == 1:
            return list(free)[0]
        raise GuideError(
            f"Expression `{expr}` has multiple symbols `{free}`.",
            hint="Specify 'symbol=...' explicitly.",
        )

    def _normalize_bounds(self, domain: Any) -> Union[Tuple[float, float], _ViewportToken]:
        if domain is VIEWPORT:
            return VIEWPORT

        if not isinstance(domain, (tuple, list)):
            raise GuideError(f"Invalid domain format: {domain}. Expected tuple or VIEWPORT.")
        if len(domain) != 2:
            raise GuideError(f"Invalid domain tuple length: {domain}. Expected 2 elements.")
        if isinstance(domain[0], sympy.Symbol):
            raise GuideError(
                f"Found symbol {domain[0]} in domain tuple. "
                "This is no longer supported. Please use the 'symbol' argument explicitly.",
                hint=f"Change your plot command to `plot(..., symbol={domain[0]}, domain={domain[1]})`",
            )

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

    def _recompute_and_draw(self, plot: Plot) -> None:
        if not self._backend:
            return
        x, y = plot.compute_data(self._x_range, self._global_samples)
        if plot.backend_handle:
            self._backend.update_plot(plot.backend_handle, x, y)
            self._backend.apply_style(plot.backend_handle, plot._style)
            self._backend.request_redraw()

    def _update_all_data(self) -> None:
        for plot in self._plots.values():
            self._recompute_and_draw(plot)


