from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

from sympy.core.symbol import Symbol

from .ParamEvent import ParamEvent


@runtime_checkable
class ParamRef(Protocol):
    @property
    def parameter(self) -> Symbol: ...

    @property
    def widget(self) -> Any: ...

    @property
    def value(self) -> Any: ...

    @value.setter
    def value(self, v: Any) -> None: ...

    def observe(self, callback: Callable[[ParamEvent], None], *, fire: bool = False) -> None: ...

    def reset(self) -> None: ...


class ProxyParamRef:
    """Default ParamRef implementation that proxies to a widget/control."""

    def __init__(self, parameter: Symbol, widget: Any) -> None:
        self._parameter = parameter
        self._widget = widget

    @property
    def parameter(self) -> Symbol:
        return self._parameter

    @property
    def widget(self) -> Any:
        return self._widget

    @property
    def value(self) -> Any:
        return self._widget.value

    @value.setter
    def value(self, v: Any) -> None:
        self._widget.value = v

    def observe(self, callback: Callable[[ParamEvent], None], *, fire: bool = False) -> None:
        def _handler(change: Any) -> None:
            event = ParamEvent(
                parameter=self._parameter,
                old=getattr(change, "old", None) if not isinstance(change, dict) else change.get("old"),
                new=getattr(change, "new", None) if not isinstance(change, dict) else change.get("new"),
                ref=self,
                raw=change,
            )
            callback(event)

        self._widget.observe(_handler, names="value")

        if fire:
            event = ParamEvent(
                parameter=self._parameter,
                old=self.value,
                new=self.value,
                ref=self,
                raw=None,
            )
            callback(event)

    def reset(self) -> None:
        if hasattr(self._widget, "reset"):
            self._widget.reset()
        else:
            raise AttributeError("reset not supported for this control.")

    def _require_attr(self, name: str) -> Any:
        if not hasattr(self._widget, name):
            raise AttributeError(f"{name} not supported for this control.")
        return getattr(self._widget, name)

    @property
    def min(self) -> Any:
        return self._require_attr("min")

    @min.setter
    def min(self, value: Any) -> None:
        if not hasattr(self._widget, "min"):
            raise AttributeError("min not supported for this control.")
        self._widget.min = value

    @property
    def max(self) -> Any:
        return self._require_attr("max")

    @max.setter
    def max(self, value: Any) -> None:
        if not hasattr(self._widget, "max"):
            raise AttributeError("max not supported for this control.")
        self._widget.max = value

    @property
    def step(self) -> Any:
        return self._require_attr("step")

    @step.setter
    def step(self, value: Any) -> None:
        if not hasattr(self._widget, "step"):
            raise AttributeError("step not supported for this control.")
        self._widget.step = value
