"""View lifecycle and stale-state policy manager for ``Figure``.

This module centralizes workspace view ownership so ``Figure`` can remain an
orchestrator. The manager owns:

- view registration and identity validation,
- active-view selection bookkeeping,
- stale-state transitions for inactive views.
"""

from __future__ import annotations

from collections.abc import Iterable

from .figure_view import View
from .InputConvert import InputConvert


class ViewManager:
    """Own workspace view models and active-view selection state."""

    def __init__(self, *, default_view_id: str) -> None:
        self._default_view_id = str(default_view_id)
        self._views: dict[str, View] = {}
        self._active_view_id = self._default_view_id

    @property
    def active_view_id(self) -> str:
        """Return the currently active view id."""
        return self._active_view_id

    @property
    def views(self) -> dict[str, View]:
        """Return the mutable view registry."""
        return self._views

    @property
    def default_view_id(self) -> str:
        """Return the immutable default view id."""
        return self._default_view_id

    def active_view(self) -> View:
        """Return the active view model."""
        return self._views[self._active_view_id]

    def require_view(self, view_id: str) -> View:
        """Return ``view_id`` model or raise ``KeyError``."""
        if view_id not in self._views:
            raise KeyError(f"Unknown view: {view_id}")
        return self._views[view_id]

    def add_view(
        self,
        view_id: str,
        *,
        title: str | None,
        x_range: tuple[int | float | str, int | float | str] | None,
        y_range: tuple[int | float | str, int | float | str] | None,
        x_label: str | None,
        y_label: str | None,
    ) -> View:
        """Create a new view model and register it."""
        key = str(view_id)
        if key in self._views:
            raise ValueError(f"View '{key}' already exists")

        xr = x_range if x_range is not None else (-4.0, 4.0)
        yr = y_range if y_range is not None else (-3.0, 3.0)
        view = View(
            id=key,
            title=title or key,
            x_label=x_label or "",
            y_label=y_label or "",
            default_x_range=(
                float(InputConvert(xr[0], float)),
                float(InputConvert(xr[1], float)),
            ),
            default_y_range=(
                float(InputConvert(yr[0], float)),
                float(InputConvert(yr[1], float)),
            ),
            is_active=(not self._views),
        )
        self._views[key] = view
        if view.is_active:
            self._active_view_id = key
        return view

    def set_active_view(
        self,
        view_id: str,
        *,
        current_viewport_x: tuple[float, float] | None,
        current_viewport_y: tuple[float, float] | None,
    ) -> tuple[View, View] | None:
        """Switch active view, persisting current viewport on the previous view."""
        key = str(view_id)
        if key not in self._views:
            raise KeyError(f"Unknown view: {key}")
        if key == self._active_view_id:
            return None

        current = self.active_view()
        current.viewport_x_range = current_viewport_x
        current.viewport_y_range = current_viewport_y
        current.is_active = False

        self._active_view_id = key
        nxt = self.active_view()
        nxt.is_active = True
        return current, nxt

    def remove_view(self, view_id: str) -> None:
        """Remove a non-active, non-default view if present."""
        key = str(view_id)
        if key == self._active_view_id:
            raise ValueError("Cannot remove active view")
        if key == self._default_view_id:
            raise ValueError("Cannot remove default view")
        self._views.pop(key, None)

    def mark_stale(self, *, view_id: str | None = None, except_views: Iterable[str] = ()) -> None:
        """Mark matching views stale.

        Parameters
        ----------
        view_id : str or None
            Specific view id to mark. ``None`` marks all views.
        except_views : Iterable[str]
            View ids to skip while marking.
        """
        excluded = set(except_views)
        targets = [view_id] if view_id is not None else list(self._views.keys())
        for target in targets:
            if target in excluded:
                continue
            view = self._views.get(target)
            if view is not None:
                view.is_stale = True

    def clear_stale(self, view_id: str) -> None:
        """Reset stale flag for ``view_id`` if present."""
        view = self._views.get(view_id)
        if view is not None:
            view.is_stale = False
