from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest
import sympy as sp
import traitlets

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src" / "gu_toolkit"


def _install_widget_stubs() -> types.ModuleType:
    if "ipywidgets" in sys.modules:
        return sys.modules["ipywidgets"]

    try:
        import ipywidgets as widgets  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        widgets = types.ModuleType("ipywidgets")
    else:
        return widgets

    class Layout:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Widget(traitlets.HasTraits):
        layout = traitlets.Any()
        style = traitlets.Any()

        def __init__(self, *args, layout=None, style=None, **kwargs):
            super().__init__()
            self.layout = layout if layout is not None else Layout()
            self.style = style
            self._classes: set[str] = set()
            for key, value in kwargs.items():
                setattr(self, key, value)

        def add_class(self, name: str) -> None:
            self._classes.add(name)

        def remove_class(self, name: str) -> None:
            self._classes.discard(name)

    class Box(Widget):
        children = traitlets.Any(())

        def __init__(self, children=(), **kwargs):
            super().__init__(**kwargs)
            self.children = tuple(children)

    class VBox(Box):
        pass

    class HBox(Box):
        pass

    class HTML(Widget):
        value = traitlets.Unicode("")

        def __init__(self, value: str = "", **kwargs):
            super().__init__(**kwargs)
            self.value = value

    class HTMLMath(HTML):
        pass

    class Text(Widget):
        value = traitlets.Unicode("")
        continuous_update = traitlets.Bool(True)

        def __init__(self, value: str = "", continuous_update: bool = True, **kwargs):
            super().__init__(**kwargs)
            self.continuous_update = bool(continuous_update)
            self.value = value

    class FloatSlider(Widget):
        value = traitlets.Float(0.0)
        min = traitlets.Float(0.0)
        max = traitlets.Float(1.0)
        step = traitlets.Float(0.1)
        continuous_update = traitlets.Bool(True)
        readout = traitlets.Bool(True)

        def __init__(
            self,
            value: float = 0.0,
            min: float = 0.0,
            max: float = 1.0,
            step: float = 0.1,
            continuous_update: bool = True,
            readout: bool = True,
            **kwargs,
        ):
            super().__init__(**kwargs)
            self.min = float(min)
            self.max = float(max)
            self.step = float(step)
            self.continuous_update = bool(continuous_update)
            self.readout = bool(readout)
            self.value = float(value)

    class Button(Widget):
        description = traitlets.Unicode("")
        tooltip = traitlets.Unicode("")
        button_style = traitlets.Unicode("")

        def __init__(self, description: str = "", tooltip: str = "", **kwargs):
            super().__init__(**kwargs)
            self.description = description
            self.tooltip = tooltip
            self.button_style = ""
            self._click_handlers = []

        def on_click(self, callback):
            self._click_handlers.append(callback)

        def click(self) -> None:
            for callback in list(self._click_handlers):
                callback(self)

    class Checkbox(Widget):
        value = traitlets.Bool(False)
        description = traitlets.Unicode("")
        indent = traitlets.Bool(True)

        def __init__(self, value: bool = False, description: str = "", indent: bool = True, **kwargs):
            super().__init__(**kwargs)
            self.value = bool(value)
            self.description = description
            self.indent = bool(indent)

    class FloatText(Widget):
        value = traitlets.Float(0.0)
        description = traitlets.Unicode("")

        def __init__(self, value: float = 0.0, description: str = "", **kwargs):
            super().__init__(**kwargs)
            self.value = float(value)
            self.description = description

    class BoundedFloatText(FloatText):
        min = traitlets.Float(0.0)
        max = traitlets.Float(1.0e308)

        def __init__(self, value: float = 0.0, min: float = 0.0, max: float = 1.0e308, **kwargs):
            super().__init__(value=value, **kwargs)
            self.min = float(min)
            self.max = float(max)

    class Dropdown(Widget):
        value = traitlets.Any()
        options = traitlets.Any(())
        description = traitlets.Unicode("")

        def __init__(self, options=(), value=None, description: str = "", **kwargs):
            super().__init__(**kwargs)
            self.options = options
            self.description = description
            self.value = value

    widgets.Layout = Layout
    widgets.Widget = Widget
    widgets.Box = Box
    widgets.VBox = VBox
    widgets.HBox = HBox
    widgets.HTML = HTML
    widgets.HTMLMath = HTMLMath
    widgets.Text = Text
    widgets.FloatSlider = FloatSlider
    widgets.Button = Button
    widgets.Checkbox = Checkbox
    widgets.FloatText = FloatText
    widgets.BoundedFloatText = BoundedFloatText
    widgets.Dropdown = Dropdown
    widgets.link = traitlets.link

    sys.modules["ipywidgets"] = widgets
    return widgets


def _ensure_package() -> None:
    if "gu_toolkit" in sys.modules:
        return
    package = types.ModuleType("gu_toolkit")
    package.__path__ = [str(_SRC_DIR)]
    sys.modules["gu_toolkit"] = package


def _load_module(module_name: str, relative_path: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, _SRC_DIR / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_install_widget_stubs()
_ensure_package()

animation_module = _load_module("gu_toolkit.animation", "animation.py")
_load_module("gu_toolkit.InputConvert", "InputConvert.py")
_load_module("gu_toolkit.ParamEvent", "ParamEvent.py")
paramref_module = _load_module("gu_toolkit.ParamRef", "ParamRef.py")
_load_module("gu_toolkit.ParameterSnapshot", "ParameterSnapshot.py")
slider_module = _load_module("gu_toolkit.Slider", "Slider.py")
figure_parameters_module = _load_module(
    "gu_toolkit.figure_parameters", "figure_parameters.py"
)

AnimationController = animation_module.AnimationController
DEFAULT_ANIMATION_TIME = animation_module.DEFAULT_ANIMATION_TIME
FloatSlider = slider_module.FloatSlider
ProxyParamRef = paramref_module.ProxyParamRef
ParameterManager = figure_parameters_module.ParameterManager
widgets = sys.modules["ipywidgets"]


class _ManualClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.callbacks: list = []

    def time(self) -> float:
        return self.now

    def subscribe(self, callback) -> None:
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def unsubscribe(self, callback) -> None:
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def advance(self, dt: float) -> None:
        self.now += float(dt)
        for callback in list(self.callbacks):
            callback(self.now)


class _FakeTarget:
    def __init__(self, *, value: float, min: float, max: float, step: float) -> None:
        self._value = float(value)
        self.min = float(min)
        self.max = float(max)
        self.step = float(step)
        self.applied: list[float] = []

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, new_value: float) -> None:
        self._value = float(new_value)
        self.applied.append(self._value)


def _make_controller(
    target: _FakeTarget,
    *,
    animation_time: float = 1.0,
    animation_mode: str = ">>",
) -> tuple[AnimationController, _ManualClock]:
    clock = _ManualClock()
    controller = AnimationController(
        target,
        clock=clock,
        time_source=clock.time,
        animation_time=animation_time,
        animation_mode=animation_mode,
    )
    return controller, clock


def test_animation_controller_updates_only_when_discrete_value_changes() -> None:
    target = _FakeTarget(value=0.0, min=0.0, max=1.0, step=0.5)
    controller, clock = _make_controller(target, animation_time=5.0)

    controller.start()
    clock.advance(0.1)
    clock.advance(0.1)

    assert target.applied == []
    assert target.value == 0.0

    clock.advance(1.1)

    assert target.value == pytest.approx(0.5)
    assert target.applied == [0.5]


def test_animation_controller_forward_loop_wraps_to_start() -> None:
    target = _FakeTarget(value=0.0, min=0.0, max=1.0, step=0.1)
    controller, clock = _make_controller(target, animation_time=1.0, animation_mode=">>")

    controller.start()
    clock.advance(0.6)
    assert target.value == pytest.approx(0.6)

    clock.advance(0.6)
    assert target.value == pytest.approx(0.2)


def test_animation_controller_forward_stop_reaches_end_and_stops() -> None:
    target = _FakeTarget(value=0.2, min=0.0, max=1.0, step=0.1)
    controller, clock = _make_controller(target, animation_time=1.0, animation_mode=">")

    controller.start()
    clock.advance(1.0)

    assert target.value == pytest.approx(1.0)
    assert controller.running is False
    assert clock.callbacks == []


def test_animation_controller_bounces_at_the_range_end() -> None:
    target = _FakeTarget(value=0.9, min=0.0, max=1.0, step=0.1)
    controller, clock = _make_controller(target, animation_time=1.0, animation_mode="<>")

    controller.start()
    clock.advance(0.3)
    assert target.value == pytest.approx(0.8)
    assert controller._direction < 0

    clock.advance(0.2)
    assert target.value == pytest.approx(0.6)
    assert controller._direction < 0


def test_domain_change_preserves_internal_position_inside_new_range() -> None:
    target = _FakeTarget(value=0.2, min=0.0, max=1.0, step=0.1)
    controller, clock = _make_controller(target, animation_time=1.0, animation_mode=">>")

    controller.start()
    clock.advance(0.06)

    assert controller._internal_value == pytest.approx(0.26)
    assert target.value == pytest.approx(0.3)

    target.step = 0.5
    controller.handle_domain_change()

    assert controller._internal_value == pytest.approx(0.26)
    assert target.value == pytest.approx(0.5)

    clock.advance(0.3)
    assert controller._internal_value == pytest.approx(0.56)
    assert target.value == pytest.approx(0.5)


def test_domain_change_clamps_internal_position_when_it_falls_outside_range() -> None:
    target = _FakeTarget(value=0.8, min=0.0, max=1.0, step=0.1)
    controller, clock = _make_controller(target, animation_time=1.0, animation_mode=">>")

    controller.start()
    clock.advance(0.02)
    assert controller._internal_value == pytest.approx(0.82)

    target.max = 0.4
    controller.handle_domain_change()

    assert controller._internal_value == pytest.approx(0.4)
    assert target.value == pytest.approx(0.4)

    clock.advance(0.3)
    assert target.value == pytest.approx(0.1)


def test_float_slider_exposes_animation_controls_with_default_values() -> None:
    slider = FloatSlider()

    assert slider.layout.width == "100%"
    assert slider.slider.layout.flex == "1 1 auto"
    assert slider.description_label.layout.width == "auto"
    assert slider.btn_animate.description == "Start animation"
    assert slider.btn_animate.tooltip == "Start animation"
    assert "smart-slider-root" in slider._classes
    assert "smart-slider-top-row" in slider._top_row._classes
    assert slider.set_animation_time.value == pytest.approx(DEFAULT_ANIMATION_TIME)
    assert slider.set_animation_mode.value == ">>"
    assert slider.animation_running is False


def test_float_slider_animation_button_toggles_running_state() -> None:
    slider = FloatSlider(value=0.0, min=0.0, max=1.0, step=0.1)
    clock = _ManualClock()
    slider._animation._clock = clock
    slider._animation._time_source = clock.time
    slider.animation_time = 1.0

    slider.btn_animate.click()
    assert slider.animation_running is True
    assert slider.btn_animate.description == "Pause animation"
    assert "mod-running" in slider.btn_animate._classes

    clock.advance(0.6)
    assert slider.value == pytest.approx(0.6)

    slider.btn_animate.click()
    assert slider.animation_running is False
    assert slider.btn_animate.description == "Start animation"
    assert "mod-running" not in slider.btn_animate._classes



def test_float_slider_still_accepts_expression_input() -> None:
    slider = FloatSlider(value=0.0, min=0.0, max=4.0, step=0.1)

    slider.number.value = "pi/2"

    assert slider.value == pytest.approx(1.57079632679)


def test_float_slider_invalid_text_still_reverts_to_previous_value() -> None:
    slider = FloatSlider(value=1.25, min=0.0, max=4.0, step=0.1)

    slider.number.value = "not a number"

    assert slider.value == pytest.approx(1.25)
    assert slider.number.value == "1.25"

def test_proxy_paramref_and_parameter_manager_expose_animation_metadata() -> None:
    a = sp.symbols("a")
    layout_box = widgets.VBox()
    manager = ParameterManager(lambda *_: None, layout_box)
    ref = manager.parameter(a, value=0.0, min=0.0, max=2.0, step=0.5)

    assert isinstance(ref, ProxyParamRef)
    slider = ref.widget
    clock = _ManualClock()
    slider._animation._clock = clock
    slider._animation._time_source = clock.time

    ref.animation_time = 3.0
    ref.animation_mode = "<>"

    assert "animation_time" in ref.capabilities
    assert "animation_mode" in ref.capabilities
    assert "animation_running" in ref.capabilities
    assert "start_animation" in dir(ref)

    ref.start_animation()
    assert ref.animation_running is True
    clock.advance(0.75)
    assert ref.value == pytest.approx(0.5)
    ref.stop_animation()
    assert ref.animation_running is False

    snap = manager.snapshot(full=True)
    assert snap[a]["animation_time"] == pytest.approx(3.0)
    assert snap[a]["animation_mode"] == "<>"
    assert snap[a]["animation_running"] is False
