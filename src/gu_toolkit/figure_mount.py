"""Small transport-neutral mount manager for figure presentation roots.

The manager is intentionally tiny: it tracks already-built widget roots, maps
those roots into named slots, and emits coarse show/hide lifecycle callbacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

try:  # pragma: no cover - runtime import path depends on environment
    import ipywidgets as widgets
except Exception:  # pragma: no cover
    from ._widget_stubs import widgets  # type: ignore


@dataclass
class _MountItem:
    """One mountable presentation root."""

    id: str
    kind: str
    root_widget: Any
    on_show: Callable[[], None] | None = None
    on_hide: Callable[[], None] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    visible: bool = True
    slot: str | None = None


class _MountManager:
    """Register mountable roots and place them into named slots."""

    def __init__(self) -> None:
        self._items: dict[str, _MountItem] = {}
        self._slot_hosts: dict[str, widgets.Box] = {}
        self._slot_items: dict[str, tuple[str, ...]] = {}

    def register(self, item: _MountItem) -> None:
        """Auto-generated reference note for ``register``.

        Full API
        --------
        ``register(...)``

        Parameters
        ----------
        See the Python signature for the accepted arguments.

        Returns
        -------
        Any
            Result produced by this API.

        Optional arguments
        ------------------
        Optional inputs follow the Python signature when present.

        Architecture note
        -----------------
        This member is part of the figure presentation/runtime refactor boundary.

        Examples
        --------
        Basic use::

            # See tests for concrete usage examples.

        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for package navigation.
        """
        key = str(item.id)
        item.id = key
        self._items[key] = item
        slot = item.slot
        if slot is not None:
            self.mount(key, slot)

    def register_slot(self, slot: str, host: widgets.Box) -> None:
        """Auto-generated reference note for ``register_slot``.

        Full API
        --------
        ``register_slot(...)``

        Parameters
        ----------
        See the Python signature for the accepted arguments.

        Returns
        -------
        Any
            Result produced by this API.

        Optional arguments
        ------------------
        Optional inputs follow the Python signature when present.

        Architecture note
        -----------------
        This member is part of the figure presentation/runtime refactor boundary.

        Examples
        --------
        Basic use::

            # See tests for concrete usage examples.

        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for package navigation.
        """
        key = str(slot)
        self._slot_hosts[key] = host
        if key in self._slot_items:
            self._sync_slot(key)

    def item(self, item_id: str) -> _MountItem:
        """Auto-generated reference note for ``item``.

        Full API
        --------
        ``item(...)``

        Parameters
        ----------
        See the Python signature for the accepted arguments.

        Returns
        -------
        Any
            Result produced by this API.

        Optional arguments
        ------------------
        Optional inputs follow the Python signature when present.

        Architecture note
        -----------------
        This member is part of the figure presentation/runtime refactor boundary.

        Examples
        --------
        Basic use::

            # See tests for concrete usage examples.

        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for package navigation.
        """
        key = str(item_id)
        if key not in self._items:
            raise KeyError(key)
        return self._items[key]

    def items(self) -> tuple[_MountItem, ...]:
        """Auto-generated reference note for ``items``.

        Full API
        --------
        ``items(...)``

        Parameters
        ----------
        See the Python signature for the accepted arguments.

        Returns
        -------
        Any
            Result produced by this API.

        Optional arguments
        ------------------
        Optional inputs follow the Python signature when present.

        Architecture note
        -----------------
        This member is part of the figure presentation/runtime refactor boundary.

        Examples
        --------
        Basic use::

            # See tests for concrete usage examples.

        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for package navigation.
        """
        return tuple(self._items.values())

    def widgets_for_ids(self, item_ids: Iterable[str]) -> tuple[Any, ...]:
        """Auto-generated reference note for ``widgets_for_ids``.

        Full API
        --------
        ``widgets_for_ids(...)``

        Parameters
        ----------
        See the Python signature for the accepted arguments.

        Returns
        -------
        Any
            Result produced by this API.

        Optional arguments
        ------------------
        Optional inputs follow the Python signature when present.

        Architecture note
        -----------------
        This member is part of the figure presentation/runtime refactor boundary.

        Examples
        --------
        Basic use::

            # See tests for concrete usage examples.

        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for package navigation.
        """
        widgets_out: list[Any] = []
        for item_id in item_ids:
            item = self._items.get(str(item_id))
            if item is None:
                raise KeyError(f"Unknown mount item id: {item_id}")
            widgets_out.append(item.root_widget)
        return tuple(widgets_out)

    def mount(self, item_id: str, slot: str) -> None:
        """Auto-generated reference note for ``mount``.

        Full API
        --------
        ``mount(...)``

        Parameters
        ----------
        See the Python signature for the accepted arguments.

        Returns
        -------
        Any
            Result produced by this API.

        Optional arguments
        ------------------
        Optional inputs follow the Python signature when present.

        Architecture note
        -----------------
        This member is part of the figure presentation/runtime refactor boundary.

        Examples
        --------
        Basic use::

            # See tests for concrete usage examples.

        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for package navigation.
        """
        self.mount_many(slot, (item_id,))

    def mount_many(self, slot: str, item_ids: Iterable[str]) -> None:
        """Auto-generated reference note for ``mount_many``.

        Full API
        --------
        ``mount_many(...)``

        Parameters
        ----------
        See the Python signature for the accepted arguments.

        Returns
        -------
        Any
            Result produced by this API.

        Optional arguments
        ------------------
        Optional inputs follow the Python signature when present.

        Architecture note
        -----------------
        This member is part of the figure presentation/runtime refactor boundary.

        Examples
        --------
        Basic use::

            # See tests for concrete usage examples.

        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for package navigation.
        """
        key = str(slot)
        normalized = tuple(str(item_id) for item_id in item_ids)
        for item_id in normalized:
            if item_id not in self._items:
                raise KeyError(f"Unknown mount item id: {item_id}")
        self._slot_items[key] = normalized
        for item_id in normalized:
            self._items[item_id].slot = key
        self._sync_slot(key)

    def slot_items(self, slot: str) -> tuple[str, ...]:
        """Auto-generated reference note for ``slot_items``.

        Full API
        --------
        ``slot_items(...)``

        Parameters
        ----------
        See the Python signature for the accepted arguments.

        Returns
        -------
        Any
            Result produced by this API.

        Optional arguments
        ------------------
        Optional inputs follow the Python signature when present.

        Architecture note
        -----------------
        This member is part of the figure presentation/runtime refactor boundary.

        Examples
        --------
        Basic use::

            # See tests for concrete usage examples.

        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for package navigation.
        """
        return tuple(self._slot_items.get(str(slot), ()))

    def set_visible(self, item_id: str, visible: bool) -> None:
        """Auto-generated reference note for ``set_visible``.

        Full API
        --------
        ``set_visible(...)``

        Parameters
        ----------
        See the Python signature for the accepted arguments.

        Returns
        -------
        Any
            Result produced by this API.

        Optional arguments
        ------------------
        Optional inputs follow the Python signature when present.

        Architecture note
        -----------------
        This member is part of the figure presentation/runtime refactor boundary.

        Examples
        --------
        Basic use::

            # See tests for concrete usage examples.

        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for package navigation.
        """
        item = self.item(item_id)
        desired = bool(visible)
        if item.visible == desired:
            return
        item.visible = desired
        layout = getattr(item.root_widget, "layout", None)
        if layout is not None and hasattr(layout, "display"):
            layout.display = "flex" if desired else "none"
        callback = item.on_show if desired else item.on_hide
        if callable(callback):
            callback()

    def snapshot(self) -> dict[str, Any]:
        """Auto-generated reference note for ``snapshot``.

        Full API
        --------
        ``snapshot(...)``

        Parameters
        ----------
        See the Python signature for the accepted arguments.

        Returns
        -------
        Any
            Result produced by this API.

        Optional arguments
        ------------------
        Optional inputs follow the Python signature when present.

        Architecture note
        -----------------
        This member is part of the figure presentation/runtime refactor boundary.

        Examples
        --------
        Basic use::

            # See tests for concrete usage examples.

        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for package navigation.
        """
        return {
            "items": {
                item_id: {
                    "kind": item.kind,
                    "slot": item.slot,
                    "visible": bool(item.visible),
                }
                for item_id, item in self._items.items()
            },
            "slots": {slot: list(item_ids) for slot, item_ids in self._slot_items.items()},
        }

    def _sync_slot(self, slot: str) -> None:
        host = self._slot_hosts.get(slot)
        if host is None:
            return
        desired = tuple(
            self._items[item_id].root_widget
            for item_id in self._slot_items.get(slot, ())
            if item_id in self._items
        )
        if tuple(getattr(host, "children", ())) != desired:
            host.children = desired


MountItem = _MountItem
MountManager = _MountManager
