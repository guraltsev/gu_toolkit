"""Public view objects and figure-level view facade.

This module defines the public ``View`` object returned by ``fig.views[...]``
and the small mapping-like ``FigureViews`` facade exposed on
:class:`gu_toolkit.Figure.Figure`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any

import plotly.graph_objects as go

from .InputConvert import InputConvert
from .PlotlyPane import PlotlyPane
from .figure_types import RangeLike

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .Figure import Figure


class View:
    """Public object representing one plotting workspace in a figure.

    A view owns one stable Plotly widget runtime for its entire lifetime,
    together with per-view axis defaults and remembered viewport state.
    It can be activated directly via :meth:`activate` or used as a context
    manager with ``with fig.views["detail"]:``.
    """

    __slots__ = (
        "_figure",
        "id",
        "_title",
        "_x_label",
        "_y_label",
        "_default_x_range",
        "_default_y_range",
        "viewport_x_range",
        "viewport_y_range",
        "is_active",
        "is_stale",
        "_figure_widget",
        "_pane",
        "_context_previous_ids",
    )

    def __init__(
        self,
        *,
        figure: Figure,
        id: str,
        title: str,
        x_label: str,
        y_label: str,
        default_x_range: RangeLike,
        default_y_range: RangeLike,
        figure_widget: go.FigureWidget,
        pane: PlotlyPane,
        is_active: bool = False,
        is_stale: bool = False,
    ) -> None:
        self._figure = figure
        self.id = str(id)
        self._title = str(title)
        self._x_label = str(x_label)
        self._y_label = str(y_label)
        self._default_x_range = self._coerce_range(default_x_range)
        self._default_y_range = self._coerce_range(default_y_range)
        self.viewport_x_range: tuple[float, float] | None = None
        self.viewport_y_range: tuple[float, float] | None = None
        self.is_active = bool(is_active)
        self.is_stale = bool(is_stale)
        self._figure_widget = figure_widget
        self._pane = pane
        self._context_previous_ids: list[str | None] = []
        self._apply_axis_titles()
        self._apply_default_ranges()

    @staticmethod
    def _coerce_range(value: RangeLike) -> tuple[float, float]:
        return (
            float(InputConvert(value[0], float)),
            float(InputConvert(value[1], float)),
        )

    def _apply_axis_titles(self) -> None:
        self._figure_widget.update_xaxes(title_text=(self._x_label or None))
        self._figure_widget.update_yaxes(title_text=(self._y_label or None))

    def _apply_default_ranges(self) -> None:
        self._figure_widget.update_xaxes(range=self._default_x_range)
        self._figure_widget.update_yaxes(range=self._default_y_range)

    @property
    def figure(self) -> Figure:
        """Return the parent figure that owns this view."""
        return self._figure

    @property
    def figure_widget(self) -> go.FigureWidget:
        """Return the stable Plotly widget owned by this view."""
        return self._figure_widget

    @property
    def pane(self) -> PlotlyPane:
        """Return the stable :class:`PlotlyPane` owned by this view."""
        return self._pane

    @property
    def plotly_layout(self) -> Any:
        """Return the Plotly layout object for this view's widget."""
        return self._figure_widget.layout

    @property
    def title(self) -> str:
        """Return the selector title shown for this view."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        self._title = str(value)
        self._figure._layout.set_view_title(self.id, self._title)

    @property
    def x_label(self) -> str:
        """Return the stored x-axis label for this view."""
        return self._x_label

    @x_label.setter
    def x_label(self, value: str) -> None:
        self._x_label = str(value)
        self._apply_axis_titles()

    @property
    def y_label(self) -> str:
        """Return the stored y-axis label for this view."""
        return self._y_label

    @y_label.setter
    def y_label(self, value: str) -> None:
        self._y_label = str(value)
        self._apply_axis_titles()

    @property
    def x_range(self) -> tuple[float, float]:
        """Return the default x-range for this view."""
        return self._default_x_range

    @x_range.setter
    def x_range(self, value: RangeLike) -> None:
        rng = self._coerce_range(value)
        self._default_x_range = rng
        self.viewport_x_range = rng
        self._figure_widget.update_xaxes(range=rng)

    @property
    def default_x_range(self) -> tuple[float, float]:
        """Compatibility alias for :attr:`x_range`."""
        return self.x_range

    @default_x_range.setter
    def default_x_range(self, value: RangeLike) -> None:
        self.x_range = value

    @property
    def y_range(self) -> tuple[float, float]:
        """Return the default y-range for this view."""
        return self._default_y_range

    @y_range.setter
    def y_range(self, value: RangeLike) -> None:
        rng = self._coerce_range(value)
        self._default_y_range = rng
        self.viewport_y_range = rng
        self._figure_widget.update_yaxes(range=rng)

    @property
    def default_y_range(self) -> tuple[float, float]:
        """Compatibility alias for :attr:`y_range`."""
        return self.y_range

    @default_y_range.setter
    def default_y_range(self, value: RangeLike) -> None:
        self.y_range = value

    @property
    def current_x_range(self) -> tuple[float, float] | None:
        """Return the live viewport x-range when available."""
        rng = self._figure_widget.layout.xaxis.range
        if rng is None:
            return self.viewport_x_range
        result = (float(rng[0]), float(rng[1]))
        self.viewport_x_range = result
        return result

    @current_x_range.setter
    def current_x_range(self, value: RangeLike | None) -> None:
        if value is None:
            rng = self._default_x_range
        else:
            rng = self._coerce_range(value)
        self.viewport_x_range = rng
        self._figure_widget.update_xaxes(range=rng)

    @property
    def current_y_range(self) -> tuple[float, float] | None:
        """Return the live viewport y-range when available."""
        rng = self._figure_widget.layout.yaxis.range
        if rng is None:
            return self.viewport_y_range
        result = (float(rng[0]), float(rng[1]))
        self.viewport_y_range = result
        return result

    @current_y_range.setter
    def current_y_range(self, value: RangeLike | None) -> None:
        if value is None:
            rng = self._default_y_range
        else:
            rng = self._coerce_range(value)
        self.viewport_y_range = rng
        self._figure_widget.update_yaxes(range=rng)

    def activate(self) -> View:
        """Activate this view on its parent figure and return ``self``."""
        self._figure.set_active_view(self.id)
        return self

    def __enter__(self) -> View:
        previous: str | None = None
        try:
            previous = self._figure.views.current_id
        except Exception:  # pragma: no cover - defensive
            previous = None
        self._context_previous_ids.append(previous)
        self._figure.__enter__()
        try:
            self.activate()
        except Exception as exc:  # pragma: no cover - defensive cleanup
            self._context_previous_ids.pop()
            self._figure.__exit__(type(exc), exc, exc.__traceback__)
            raise
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        previous = self._context_previous_ids.pop() if self._context_previous_ids else None
        try:
            if previous is not None and previous in self._figure.views and previous != self.id:
                self._figure.set_active_view(previous)
        finally:
            self._figure.__exit__(exc_type, exc, tb)


class FigureViews(Mapping[str, View]):
    """Mapping-like facade that exposes a figure's registered views."""

    __slots__ = ("_fig",)

    def __init__(self, fig: Figure) -> None:
        self._fig = fig

    def __getitem__(self, key: str) -> View:
        return self._fig._view_manager.require_view(str(key))

    def __iter__(self) -> Iterator[str]:
        return iter(self._fig._view_manager.views)

    def __len__(self) -> int:
        return len(self._fig._view_manager.views)

    @property
    def current_id(self) -> str:
        """Return the current active view id."""
        return self._fig._view_manager.active_view_id

    @current_id.setter
    def current_id(self, value: str) -> None:
        self._fig.set_active_view(str(value))

    @property
    def current(self) -> View:
        """Return the current active public view object."""
        return self._fig._view_manager.active_view()

    def add(
        self,
        view_id: str,
        *,
        title: str | None = None,
        x_range: RangeLike | None = None,
        y_range: RangeLike | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        activate: bool = False,
    ) -> View:
        """Create a new view by delegating to :meth:`Figure.add_view`."""
        return self._fig.add_view(
            view_id,
            title=title,
            x_range=x_range,
            y_range=y_range,
            x_label=x_label,
            y_label=y_label,
            activate=activate,
        )

    def remove(self, view_id: str) -> None:
        """Remove a view by delegating to :meth:`Figure.remove_view`."""
        self._fig.remove_view(view_id)

    def select(self, view_id: str) -> None:
        """Select a view by setting :attr:`current_id`."""
        self.current_id = view_id


__all__ = ["FigureViews", "View"]
