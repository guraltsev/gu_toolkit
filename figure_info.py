"""Info panel manager for Figure."""

from __future__ import annotations

import html
import re
import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, Optional, Sequence, Union

import ipywidgets as widgets
from IPython.display import display

from .debouncing import QueuedDebouncer
from .figure_layout import OneShotOutput
from .FigureSnapshot import InfoCardSnapshot

# SECTION: InfoPanelManager (The Model for Info) [id: InfoPanelManager]
# =============================================================================

class InfoPanelManager:
    """
    Manages the 'Info' section output widgets and interactive components.

    It allows adding "Output" widgets (where you can print text or display charts)
    and registering "Stateful Components" (classes that update when sliders move).
    """
    
    _ID_REGEX = re.compile(r"^info:(\d+)$")
    _SIMPLE_ID_REGEX = re.compile(r"^info(\d+)$")

    @dataclass(frozen=True)
    class InfoChangeContext:
        """Update metadata for dynamic info segment evaluations."""

        reason: str
        trigger: Any = None
        t: float = 0.0
        seq: int = 0

    @dataclass
    class _StaticSegment:
        text: str
        widget: widgets.HTMLMath

    @dataclass
    class _DynamicSegment:
        fn: Callable[[Any, "InfoPanelManager.InfoChangeContext"], str]
        widget: widgets.HTMLMath
        last_text: Optional[str] = None

    @dataclass
    class _SimpleInfoCard:
        id: Hashable
        output: widgets.Output
        container: widgets.VBox
        segments: list[Union["InfoPanelManager._StaticSegment", "InfoPanelManager._DynamicSegment"]]
        debouncer: QueuedDebouncer
        pending_ctx: Optional["InfoPanelManager.InfoChangeContext"] = None
        view_id: Optional[str] = None

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
        self._simple_cards: Dict[Hashable, InfoPanelManager._SimpleInfoCard] = {}
        self._simple_counter = 0
        self._update_seq = 0
        self._active_view_id: Optional[str] = None

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

    def set_simple_card(
        self,
        spec: Union[str, Callable, Sequence[Union[str, Callable]]],
        id: Optional[Hashable] = None,
        *,
        view: Optional[str] = None,
    ) -> Hashable:
        """Create or replace a simple rich-text info card."""
        if id is None:
            id = self._next_simple_id()
        elif isinstance(id, str):
            m = self._SIMPLE_ID_REGEX.match(id)
            if m:
                self._simple_counter = max(self._simple_counter, int(m.group(1)) + 1)

        out = self.get_output(id=id)

        normalized = self._normalize_spec(spec)
        card = self._simple_cards.get(id)
        if card is None:
            container = widgets.VBox(layout=widgets.Layout(gap="6px"))
            card = self._SimpleInfoCard(
                id=id,
                output=out,
                container=container,
                segments=[],
                debouncer=QueuedDebouncer(
                    lambda card_id=id: self._run_card_update(card_id),
                    execute_every_ms=33,
                    drop_overflow=True,
                ),
            )
            self._simple_cards[id] = card

        card.view_id = view
        self._rebuild_simple_card(card, normalized)
        self._apply_card_visibility(card)
        return id



    def _apply_card_visibility(self, card: _SimpleInfoCard) -> None:
        visible = card.view_id is None or card.view_id == self._active_view_id
        card.output.layout.display = "block" if visible else "none"

    def set_active_view(self, view_id: str) -> None:
        """Update which scoped info cards are visible in the sidebar."""
        self._active_view_id = str(view_id)
        for card in self._simple_cards.values():
            self._apply_card_visibility(card)

    def _next_simple_id(self) -> str:
        while True:
            id = f"info{self._simple_counter}"
            self._simple_counter += 1
            if id not in self._outputs:
                return id

    def schedule_info_update(self, reason: str, trigger: Any = None) -> None:
        """Queue updates for all simple cards with a shared reason payload."""
        if not self._simple_cards:
            return

        self._update_seq += 1
        ctx = self.InfoChangeContext(reason=reason, trigger=trigger, t=time.time(), seq=self._update_seq)
        for card in self._simple_cards.values():
            card.pending_ctx = ctx
            card.debouncer()

    def _normalize_spec(self, spec: Union[str, Callable, Sequence[Union[str, Callable]]]) -> list[Union[str, Callable]]:
        if isinstance(spec, str) or callable(spec):
            return [spec]
        if isinstance(spec, Sequence) and not isinstance(spec, (str, bytes)):
            values = list(spec)
            for idx, value in enumerate(values):
                if not isinstance(value, str) and not callable(value):
                    raise TypeError(f"Info spec element at index {idx} must be a str or callable; got {type(value).__name__}")
            return values
        raise TypeError(f"Info spec must be a str, callable, or sequence of these; got {type(spec).__name__}")

    def _rebuild_simple_card(self, card: _SimpleInfoCard, normalized: list[Union[str, Callable]]) -> None:
        segment_widgets: list[widgets.HTMLMath] = []
        segments: list[Union[InfoPanelManager._StaticSegment, InfoPanelManager._DynamicSegment]] = []
        for part in normalized:
            if isinstance(part, str):
                widget = widgets.HTMLMath(value=part, layout=widgets.Layout(margin="0px"))
                segments.append(self._StaticSegment(text=part, widget=widget))
            else:
                widget = widgets.HTMLMath(value="", layout=widgets.Layout(margin="0px"))
                segments.append(self._DynamicSegment(fn=part, widget=widget, last_text=None))
            segment_widgets.append(widget)

        card.segments = segments
        card.pending_ctx = self.InfoChangeContext(reason="manual", trigger=None, t=time.time(), seq=self._update_seq)
        card.container.children = tuple(segment_widgets)

        with card.output:
            card.output.clear_output(wait=True)
            display(card.container)

        card.debouncer()

    def _run_card_update(self, card_id: Hashable) -> None:
        card = self._simple_cards.get(card_id)
        if card is None:
            return

        ctx = card.pending_ctx or self.InfoChangeContext(reason="manual", trigger=None, t=time.time(), seq=self._update_seq)
        for seg in card.segments:
            if isinstance(seg, self._StaticSegment):
                continue
            try:
                text = seg.fn(self._figure_owner, ctx)
                if text is None:
                    text = ""
                elif not isinstance(text, str):
                    text = str(text)
            except Exception as exc:
                text = self._format_segment_error(exc)
            if text != seg.last_text:
                seg.widget.value = text
                seg.last_text = text

    def _format_segment_error(self, exc: Exception) -> str:
        lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        payload = "".join(lines)
        capped = "\n".join(payload.splitlines()[:20])
        safe = html.escape(capped)
        return (
            '<pre style="max-height: 12em; overflow:auto; white-space: pre-wrap; margin:0;">'
            f"{safe}"
            "</pre>"
        )

    @property
    def _figure_owner(self) -> Any:
        owner = getattr(self, "__figure_owner", None)
        if owner is None:
            raise RuntimeError("InfoPanelManager owner figure not set")
        return owner

    def bind_figure(self, fig: Any) -> None:
        """Bind the owning Figure instance for dynamic callable execution."""
        setattr(self, "__figure_owner", fig)

    def snapshot(self) -> tuple[InfoCardSnapshot, ...]:
        """Return immutable snapshots of all simple info cards.

        Static text segments are captured verbatim.  Dynamic (callable)
        segments are stored as the placeholder string ``"<dynamic>"``.

        Returns
        -------
        tuple[InfoCardSnapshot, ...]
        """
        results: list[InfoCardSnapshot] = []
        for card in self._simple_cards.values():
            segs: list[str] = []
            for seg in card.segments:
                if isinstance(seg, self._StaticSegment):
                    segs.append(seg.text)
                else:
                    segs.append("<dynamic>")
            results.append(InfoCardSnapshot(id=card.id, segments=tuple(segs), view_id=card.view_id))
        return tuple(results)


# =============================================================================
