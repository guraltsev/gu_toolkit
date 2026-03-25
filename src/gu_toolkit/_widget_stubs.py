"""Compatibility helpers for widget-centric test and fallback environments.

This module centralizes the toolkit's optional dependency fallback for
``ipywidgets`` and ``anywidget``. In normal notebook environments the real
packages are imported unchanged. In minimal or offline test environments a
small traitlets-based shim is provided instead so the pure-Python parts of the
repository remain importable and testable.

The shim intentionally implements only the subset of the widget API exercised by
this repository's unit tests. It is **not** a drop-in replacement for the full
ipywidgets stack and should be treated as a last-resort compatibility layer.
"""

from __future__ import annotations

from contextlib import contextmanager
import sys
import types
from typing import Any, Callable

import traitlets


class _SimpleNamespace:
    """Tiny mutable object used for ``layout`` and ``style`` traits."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__dict__!r})"


class Layout(_SimpleNamespace):
    """Minimal stand-in for :class:`ipywidgets.Layout`."""


class _Style(_SimpleNamespace):
    """Mutable style container used by fallback widgets."""


class Widget(traitlets.HasTraits):
    """Minimal traitlets-backed widget base class.

    The fallback widget keeps the API surface intentionally small while still
    supporting trait observation, layout/style mutation, CSS class tracking,
    and message callbacks used by :mod:`gu_toolkit.PlotlyPane`.
    """

    layout = traitlets.Any()
    style = traitlets.Any()

    def __init__(
        self,
        *args: Any,
        layout: Layout | None = None,
        style: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.layout = layout if layout is not None else Layout()
        self.style = style if style is not None else _Style()
        self._classes: set[str] = set()
        self._dom_classes: tuple[str, ...] = ()
        self._msg_handlers: list[Callable[[Any, Any, Any], None]] = []
        for key, value in kwargs.items():
            setattr(self, key, value)

    def add_class(self, name: str) -> None:
        self._classes.add(str(name))
        self._dom_classes = tuple(sorted(self._classes))

    def remove_class(self, name: str) -> None:
        self._classes.discard(str(name))
        self._dom_classes = tuple(sorted(self._classes))

    def on_msg(self, callback: Callable[[Any, Any, Any], None]) -> None:
        self._msg_handlers.append(callback)

    def send(self, *args: Any, **kwargs: Any) -> None:
        """No-op message transport used by tests.

        Real ipywidgets sends trait/buffer messages to the front-end. The test
        shim intentionally does nothing here.
        """

    def _emit_msg(self, content: Any = None, buffers: Any = None) -> None:
        for callback in list(self._msg_handlers):
            callback(self, content, buffers)

    def close(self) -> None:
        return None

    def _repr_mimebundle_(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"text/plain": repr(self)}


class Box(Widget):
    children = traitlets.Any(())

    def __init__(self, children: tuple[Any, ...] | list[Any] = (), **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.children = tuple(children)


class VBox(Box):
    pass


class HBox(Box):
    pass


class Label(Widget):
    value = traitlets.Unicode("")

    def __init__(self, value: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.value = str(value)


class HTML(Widget):
    value = traitlets.Unicode("")

    def __init__(self, value: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.value = str(value)


class HTMLMath(HTML):
    pass


class Text(Widget):
    value = traitlets.Unicode("")
    continuous_update = traitlets.Bool(True)
    description = traitlets.Unicode("")
    placeholder = traitlets.Unicode("")

    def __init__(
        self,
        value: str = "",
        *,
        continuous_update: bool = True,
        description: str = "",
        placeholder: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.continuous_update = bool(continuous_update)
        self.description = str(description)
        self.placeholder = str(placeholder)
        self.value = str(value)


class FloatSlider(Widget):
    value = traitlets.Float(0.0)
    min = traitlets.Float(0.0)
    max = traitlets.Float(1.0)
    step = traitlets.Float(0.1)
    continuous_update = traitlets.Bool(True)
    readout = traitlets.Bool(True)
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        value: float = 0.0,
        *,
        min: float = 0.0,
        max: float = 1.0,
        step: float = 0.1,
        continuous_update: bool = True,
        readout: bool = True,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.min = float(min)
        self.max = float(max)
        self.step = float(step)
        self.continuous_update = bool(continuous_update)
        self.readout = bool(readout)
        self.disabled = bool(disabled)
        self.value = float(value)


class IntSlider(Widget):
    value = traitlets.Int(0)
    min = traitlets.Int(0)
    max = traitlets.Int(100)
    step = traitlets.Int(1)
    continuous_update = traitlets.Bool(True)
    readout = traitlets.Bool(True)

    def __init__(
        self,
        value: int = 0,
        *,
        min: int = 0,
        max: int = 100,
        step: int = 1,
        continuous_update: bool = True,
        readout: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.min = int(min)
        self.max = int(max)
        self.step = int(step)
        self.continuous_update = bool(continuous_update)
        self.readout = bool(readout)
        self.value = int(value)


class Button(Widget):
    description = traitlets.Unicode("")
    tooltip = traitlets.Unicode("")
    button_style = traitlets.Unicode("")
    icon = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        description: str = "",
        *,
        tooltip: str = "",
        button_style: str = "",
        icon: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.description = str(description)
        self.tooltip = str(tooltip)
        self.button_style = str(button_style)
        self.icon = str(icon)
        self.disabled = bool(disabled)
        self._click_handlers: list[Callable[[Any], None]] = []

    def on_click(self, callback: Callable[[Any], None]) -> None:
        self._click_handlers.append(callback)

    def click(self) -> None:
        for callback in list(self._click_handlers):
            callback(self)


class ToggleButton(Button):
    value = traitlets.Bool(False)

    def __init__(self, value: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.value = bool(value)


class ToggleButtons(Widget):
    value = traitlets.Any(None)
    options = traitlets.Any(())
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        *,
        options: Any = (),
        value: Any = None,
        description: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.options = options
        self.description = str(description)
        self.disabled = bool(disabled)
        self.value = value


class Checkbox(Widget):
    value = traitlets.Bool(False)
    description = traitlets.Unicode("")
    indent = traitlets.Bool(True)
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        value: bool = False,
        *,
        description: str = "",
        indent: bool = True,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.value = bool(value)
        self.description = str(description)
        self.indent = bool(indent)
        self.disabled = bool(disabled)


class FloatText(Widget):
    value = traitlets.Float(0.0)
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        value: float = 0.0,
        *,
        description: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.value = float(value)
        self.description = str(description)
        self.disabled = bool(disabled)


class BoundedFloatText(FloatText):
    min = traitlets.Float(0.0)
    max = traitlets.Float(1.0e308)

    def __init__(
        self,
        value: float = 0.0,
        *,
        min: float = 0.0,
        max: float = 1.0e308,
        **kwargs: Any,
    ) -> None:
        super().__init__(value=value, **kwargs)
        self.min = float(min)
        self.max = float(max)


class IntText(Widget):
    value = traitlets.Int(0)
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        value: int = 0,
        *,
        description: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.value = int(value)
        self.description = str(description)
        self.disabled = bool(disabled)


class BoundedIntText(IntText):
    min = traitlets.Int(0)
    max = traitlets.Int(2147483647)

    def __init__(
        self,
        value: int = 0,
        *,
        min: int = 0,
        max: int = 2147483647,
        **kwargs: Any,
    ) -> None:
        super().__init__(value=value, **kwargs)
        self.min = int(min)
        self.max = int(max)


class Dropdown(Widget):
    value = traitlets.Any()
    options = traitlets.Any(())
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        options: Any = (),
        value: Any = None,
        *,
        description: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.options = options
        self.description = str(description)
        self.disabled = bool(disabled)
        self.value = value


class SelectMultiple(Widget):
    value = traitlets.Tuple()
    options = traitlets.Any(())
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        options: Any = (),
        value: tuple[Any, ...] = (),
        *,
        description: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.options = options
        self.description = str(description)
        self.disabled = bool(disabled)
        self.value = tuple(value)


class ColorPicker(Widget):
    """Minimal stand-in for :class:`ipywidgets.ColorPicker`."""

    value = traitlets.Unicode("#000000")
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)
    concise = traitlets.Bool(False)

    def __init__(
        self,
        value: str = "#000000",
        *,
        description: str = "",
        disabled: bool = False,
        concise: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.description = str(description)
        self.disabled = bool(disabled)
        self.concise = bool(concise)
        self.value = str(value)


class Output(Widget):
    outputs = traitlets.List(trait=traitlets.Any())

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.outputs = []

    @contextmanager
    def capture(self, *args: Any, **kwargs: Any):
        yield self

    def clear_output(self, wait: bool = False) -> None:
        self.outputs = []

    def append_stdout(self, text: str) -> None:
        self.outputs = [*self.outputs, {"name": "stdout", "text": str(text)}]

    def append_stderr(self, text: str) -> None:
        self.outputs = [*self.outputs, {"name": "stderr", "text": str(text)}]

    def append_display_data(self, obj: Any) -> None:
        self.outputs = [*self.outputs, {"data": obj}]

    def __enter__(self) -> "Output":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


_widgets_module = types.ModuleType("ipywidgets")
_widgets_module.Layout = Layout
_widgets_module.Widget = Widget
_widgets_module.Box = Box
_widgets_module.VBox = VBox
_widgets_module.HBox = HBox
_widgets_module.Label = Label
_widgets_module.HTML = HTML
_widgets_module.HTMLMath = HTMLMath
_widgets_module.Text = Text
_widgets_module.FloatSlider = FloatSlider
_widgets_module.IntSlider = IntSlider
_widgets_module.Button = Button
_widgets_module.ToggleButton = ToggleButton
_widgets_module.ToggleButtons = ToggleButtons
_widgets_module.Checkbox = Checkbox
_widgets_module.FloatText = FloatText
_widgets_module.BoundedFloatText = BoundedFloatText
_widgets_module.IntText = IntText
_widgets_module.BoundedIntText = BoundedIntText
_widgets_module.Dropdown = Dropdown
_widgets_module.SelectMultiple = SelectMultiple
_widgets_module.ColorPicker = ColorPicker
_widgets_module.Output = Output
_widgets_module.link = traitlets.link
_widgets_module.dlink = traitlets.dlink
_widgets_module.Widget.widget_types = {}


try:  # pragma: no cover - exercised only when real dependency exists
    import ipywidgets as widgets  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - covered via unit tests
    widgets = _widgets_module


try:  # pragma: no cover - exercised only when real dependency exists
    import anywidget  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - covered via unit tests
    if widgets is _widgets_module:
        class _FallbackAnyWidget(Widget):
            """Small ``anywidget.AnyWidget`` substitute used in tests."""

            _esm = ""
    else:
        class _FallbackAnyWidget(widgets.DOMWidget):  # type: ignore[misc, valid-type]
            """Fallback ``anywidget.AnyWidget`` compatible with real ipywidgets."""

            _esm = ""
            _view_name = traitlets.Unicode("FallbackAnyWidgetView").tag(sync=True)
            _model_name = traitlets.Unicode("FallbackAnyWidgetModel").tag(sync=True)
            _view_module = traitlets.Unicode("@jupyter-widgets/base").tag(sync=True)
            _model_module = traitlets.Unicode("@jupyter-widgets/base").tag(sync=True)
            _view_module_version = traitlets.Unicode("*").tag(sync=True)
            _model_module_version = traitlets.Unicode("*").tag(sync=True)

            def _emit_msg(self, content: Any = None, buffers: Any = None) -> None:
                self._handle_custom_msg(content if content is not None else {}, buffers)

    _anywidget_module = types.ModuleType("anywidget")
    _anywidget_module.AnyWidget = _FallbackAnyWidget
    anywidget = _anywidget_module


def install_widget_stubs() -> None:
    """Install fallback widget modules into :mod:`sys.modules` when missing.

    Tests use this helper from ``tests/conftest.py`` so direct imports like
    ``import ipywidgets as widgets`` succeed even in offline environments where
    the real dependency is unavailable.
    """

    sys.modules.setdefault("ipywidgets", widgets)
    sys.modules.setdefault("anywidget", anywidget)


__all__ = ["widgets", "anywidget", "install_widget_stubs"]
