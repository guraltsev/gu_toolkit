"""Info panel manager for Figure."""

from __future__ import annotations

import re
from typing import Any, Dict, Hashable, Optional

import ipywidgets as widgets

from .figure_layout import OneShotOutput

# SECTION: InfoPanelManager (The Model for Info) [id: InfoPanelManager]
# =============================================================================

class InfoPanelManager:
    """
    Manages the 'Info' section output widgets and interactive components.

    It allows adding "Output" widgets (where you can print text or display charts)
    and registering "Stateful Components" (classes that update when sliders move).
    """
    
    _ID_REGEX = re.compile(r"^info:(\d+)$")

    def __init__(self, layout_box: widgets.Box) -> None:
        """Initialize the info panel manager.

        Parameters
        ----------
        layout_box : ipywidgets.Box
            Container where info outputs will be added.

        Returns
        -------
        None

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP

        Notes
        -----
        Use :meth:`get_output` to create outputs lazily as content is needed.
        """
        self._outputs: Dict[Hashable, widgets.Output] = {}
        self._components: Dict[Hashable, Any] = {}
        self._layout_box = layout_box
        self._counter = 0

    def get_output(self, id: Optional[Hashable] = None, **layout_kwargs: Any) -> widgets.Output:
        """
        Get or create an Info Output widget.

        Parameters
        ----------
        id : hashable, optional
            Unique identifier for the output. If omitted, a new ID is generated.
        **layout_kwargs : Any
            Keyword arguments forwarded to ``ipywidgets.Layout``.

        Returns
        -------
        ipywidgets.Output
            Output widget associated with the ID.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> out = panel.get_output("info:1")  # doctest: +SKIP

        Notes
        -----
        IDs are stored on the widget as ``out.id`` for convenience.
        """
        if id is None:
            self._counter += 1
            id = f"info:{self._counter}"
        
        if id in self._outputs:
            out = self._outputs[id]
            if layout_kwargs:
                out.layout = widgets.Layout(**layout_kwargs)
            return out
        
        # Validate ID if string (avoids collision with auto-generated IDs)
        if isinstance(id, str):
            m = self._ID_REGEX.match(id)
            if m:
                self._counter = max(self._counter, int(m.group(1)))

        out = widgets.Output(layout=widgets.Layout(**layout_kwargs))
        setattr(out, 'id', id)
        
        self._outputs[id] = out
        self._layout_box.children += (out,)
        return out

    def add_component(self, id: Hashable, component_inst: Any) -> None:
        """Register an info component instance.

        Parameters
        ----------
        id : hashable
            Unique identifier for the component.
        component_inst : Any
            Component instance to store.

        Returns
        -------
        None

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.add_component("demo", object())  # doctest: +SKIP

        See Also
        --------
        get_component : Retrieve a registered component.
        """
        self._components[id] = component_inst

    def get_component(self, id: Hashable) -> Any:
        """Retrieve a previously registered info component.

        Parameters
        ----------
        id : hashable
            Component identifier.

        Returns
        -------
        Any
            The registered component instance.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.add_component("demo", object())  # doctest: +SKIP
        >>> panel.get_component("demo")  # doctest: +SKIP

        See Also
        --------
        add_component : Register a component instance.
        """
        return self._components[id]

    @property
    def has_info(self) -> bool:
        """Whether any info outputs exist.

        Returns
        -------
        bool
            ``True`` if at least one output has been created.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.has_info
        False

        See Also
        --------
        get_output : Create an output widget in the info panel.
        """
        return len(self._outputs) > 0


# =============================================================================
