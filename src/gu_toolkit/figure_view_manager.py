"""View registry and active-selection policy for :class:`gu_toolkit.Figure`.

`ViewManager` owns the pure registry-level concerns for public ``View``
objects: registration, active id bookkeeping, validation, and stale-state
tracking. It does not construct widgets or decide layout behavior.
"""

from __future__ import annotations

from collections.abc import Iterable

from .figure_view import View


class ViewManager:
    """Own workspace views and active-view selection state."""

    DEFAULT_VIEW_ID = "main"

    def __init__(self, *, default_view_id: str = DEFAULT_VIEW_ID) -> None:
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
        """Return the stable default view id."""
        return self._default_view_id

    def active_view(self) -> View:
        """Return the active public view object."""
        return self._views[self._active_view_id]

    def require_view(self, view_id: str) -> View:
        """Return ``view_id`` or raise ``KeyError``."""
        if view_id not in self._views:
            raise KeyError(f"Unknown view: {view_id}")
        return self._views[view_id]

    def register_view(self, view: View) -> View:
        """Register an already-created :class:`View` object."""
        key = str(view.id)
        if key in self._views:
            raise ValueError(f"View '{key}' already exists")
        is_first = not self._views
        view.is_active = is_first
        if is_first:
            self._active_view_id = key
        self._views[key] = view
        return view

    def set_active_view(self, view_id: str) -> tuple[View, View] | None:
        """Switch the active view id and update per-view active flags."""
        key = str(view_id)
        if key not in self._views:
            raise KeyError(f"Unknown view: {key}")
        if key == self._active_view_id:
            return None

        current = self.active_view()
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

    def mark_stale(
        self,
        *,
        view_id: str | None = None,
        except_views: Iterable[str] = (),
    ) -> None:
        """Mark one or more views stale."""
        excluded = {str(v) for v in except_views}
        targets = [str(view_id)] if view_id is not None else list(self._views.keys())
        for target in targets:
            if target in excluded:
                continue
            view = self._views.get(target)
            if view is not None:
                view.is_stale = True

    def clear_stale(self, view_id: str) -> None:
        """Reset the stale flag for ``view_id`` if present."""
        view = self._views.get(str(view_id))
        if view is not None:
            view.is_stale = False
